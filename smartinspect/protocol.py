# SmartInspect Protocol
# Handles TCP connection, packet transmission, backlog buffering, and auto-reconnection

"""
Protocol module for SmartInspect communication.
Handles TCP connections with support for:
- Backlog buffering (queuing packets when disconnected)
- Auto-reconnect with time-gating
- WSL host auto-detection
- Event callbacks
"""

import socket
import threading
import time
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable, Dict, Any, List
from queue import Queue, Empty

from .formatter import BinaryFormatter
from .enums import PacketType

# Version and protocol constants
CLIENT_VERSION = "1.0.0"
CLIENT_BANNER = f"SmartInspect Python Library v{CLIENT_VERSION}\n"
DEFAULT_TIMEOUT = 30.0  # seconds
ANSWER_SIZE = 2


def detect_wsl_host() -> Optional[str]:
    """
    Detect the Windows host IP when running in WSL.
    Returns the Windows host IP or None if not in WSL.
    """
    # Check if we're in WSL
    try:
        with open("/proc/version", "r") as f:
            version = f.read().lower()
            if "microsoft" not in version and "wsl" not in version:
                return None
    except (FileNotFoundError, IOError):
        return None

    # Try WSL2 method first (resolv.conf nameserver)
    try:
        with open("/etc/resolv.conf", "r") as f:
            for line in f:
                if line.strip().startswith("nameserver"):
                    ip = line.strip().split()[1]
                    # Validate it's a private IP (likely WSL2)
                    if ip.startswith(("172.", "192.168.", "10.")):
                        return ip
    except (FileNotFoundError, IOError):
        pass

    # Try WSL1 method (host.docker.internal or host gateway)
    try:
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        match = re.search(r"via\s+(\d+\.\d+\.\d+\.\d+)", result.stdout)
        if match:
            return match.group(1)
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    return None


@dataclass
class PacketQueueItem:
    """Item in the packet queue."""

    packet: Dict[str, Any]
    next: Optional["PacketQueueItem"] = None
    previous: Optional["PacketQueueItem"] = None


class PacketQueue:
    """
    FIFO queue for backlog buffering.
    Port of C# PacketQueue.cs with size-based trimming.
    """

    OVERHEAD = 24  # bytes per queue item (memory overhead)

    def __init__(self):
        self._backlog = 2048 * 1024  # Default 2MB
        self._size = 0
        self._count = 0
        self._head: Optional[PacketQueueItem] = None
        self._tail: Optional[PacketQueueItem] = None
        self._lock = threading.Lock()
        self.on_packet_dropped: Optional[Callable[[int], None]] = None

    @property
    def backlog(self) -> int:
        """Maximum queue size in bytes."""
        return self._backlog

    @backlog.setter
    def backlog(self, value: int) -> None:
        with self._lock:
            self._backlog = value
            self._resize()

    @property
    def count(self) -> int:
        """Current number of packets in queue."""
        return self._count

    @property
    def size(self) -> int:
        """Current size of queue in bytes."""
        return self._size

    @property
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return self._count == 0

    def clear(self) -> None:
        """Remove all packets from the queue."""
        with self._lock:
            while self._pop_unsafe() is not None:
                pass

    def pop(self) -> Optional[Dict[str, Any]]:
        """Remove and return the oldest packet."""
        with self._lock:
            return self._pop_unsafe()

    def _pop_unsafe(self) -> Optional[Dict[str, Any]]:
        """Pop without lock (internal use)."""
        if self._head is None:
            return None

        item = self._head
        packet = item.packet
        self._head = item.next

        if self._head is not None:
            self._head.previous = None
        else:
            self._tail = None

        self._count -= 1
        self._size -= self._get_packet_size(packet) + self.OVERHEAD

        return packet

    def push(self, packet: Dict[str, Any]) -> None:
        """Add a packet to the queue."""
        with self._lock:
            item = PacketQueueItem(packet=packet)

            if self._tail is None:
                self._tail = item
                self._head = item
            else:
                self._tail.next = item
                item.previous = self._tail
                self._tail = item

            self._count += 1
            self._size += self._get_packet_size(packet) + self.OVERHEAD
            self._resize()

    def _resize(self) -> None:
        """Trim oldest packets until size is within backlog limit."""
        dropped_count = 0
        while self._backlog < self._size:
            if self._pop_unsafe() is None:
                self._size = 0
                break
            dropped_count += 1

        if dropped_count > 0 and self.on_packet_dropped:
            self.on_packet_dropped(dropped_count)

    def _get_packet_size(self, packet: Dict[str, Any]) -> int:
        """Estimate packet size in bytes."""
        if not packet:
            return 0

        size = 64  # Base packet overhead

        for key in ("title", "app_name", "session_name", "host_name", "content", "channel"):
            value = packet.get(key)
            if value:
                size += len(str(value).encode("utf-8"))

        data = packet.get("data")
        if data:
            if isinstance(data, bytes):
                size += len(data)
            else:
                size += len(str(data).encode("utf-8"))

        return size

    def get_all(self) -> List[Dict[str, Any]]:
        """Get all packets from queue (draining it)."""
        packets = []
        while True:
            packet = self.pop()
            if packet is None:
                break
            packets.append(packet)
        return packets


class TcpProtocol:
    """
    TcpProtocol - handles TCP connection to SmartInspect Console.

    Features:
    - Auto-reconnect with time-gating
    - Backlog buffering for disconnected state
    - Event callbacks (on_error, on_connect, on_disconnect)
    - Thread-safe packet sending
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4228,
        timeout: float = DEFAULT_TIMEOUT,
        app_name: str = "Python App",
        host_name: Optional[str] = None,
        room: str = "default",
        # Callbacks
        on_error: Optional[Callable[[Exception], None]] = None,
        on_connect: Optional[Callable[[str], None]] = None,
        on_disconnect: Optional[Callable[[], None]] = None,
        # Reconnect settings
        reconnect: bool = True,
        reconnect_interval: float = 3.0,  # seconds
        # Backlog settings
        backlog_enabled: bool = True,
        backlog_queue: int = 2048,  # KB
        backlog_keep_open: bool = True,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.app_name = app_name
        self.host_name = host_name or socket.gethostname()
        self.room = room

        # Event callbacks
        self.on_error = on_error
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect

        # Reconnect settings
        self.reconnect = reconnect
        self.reconnect_interval = reconnect_interval
        self._last_reconnect_time = 0.0

        # Backlog settings
        self.backlog_enabled = backlog_enabled
        self._queue = PacketQueue()
        self._queue.backlog = backlog_queue * 1024  # Convert KB to bytes
        self._queue.on_packet_dropped = self._on_backlog_overflow
        self._keep_open = not backlog_enabled or backlog_keep_open

        # Internal state
        self._socket: Optional[socket.socket] = None
        self._connected = False
        self._failed = False
        self._formatter = BinaryFormatter()
        self._lock = threading.Lock()
        self._connect_in_progress = False

    @property
    def connected(self) -> bool:
        """Check if connected."""
        return self._connected

    @property
    def failed(self) -> bool:
        """Check if in failed state."""
        return self._failed

    def _on_backlog_overflow(self, count: int) -> None:
        """Called when packets are dropped from backlog."""
        if self.on_error:
            self.on_error(Exception(f"Backlog overflow: {count} packets dropped"))

    def build_log_header_content(self) -> str:
        """Build LogHeader content string."""
        return f"hostname={self.host_name}\r\nappname={self.app_name}\r\nroom={self.room}\r\n"

    def connect(self) -> None:
        """
        Connect to SmartInspect Console.
        Non-blocking - starts connection in background thread.
        """
        with self._lock:
            if self._connected or self._connect_in_progress:
                return
            self._connect_in_progress = True

        # Start connection in background
        thread = threading.Thread(target=self._background_connect, daemon=True)
        thread.start()

    def _background_connect(self) -> None:
        """Background connection (fire and forget)."""
        try:
            self._internal_connect()
            self._connected = True
            self._failed = False

            # Flush any buffered packets
            if self.backlog_enabled:
                self._flush_queue()

        except Exception as e:
            self._failed = True
            if self.on_error:
                self.on_error(e)
        finally:
            self._connect_in_progress = False

    def _internal_connect(self) -> str:
        """Low-level connect (creates socket and performs handshake)."""
        with self._lock:
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None

            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self.timeout)
            self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

            try:
                self._socket.connect((self.host, self.port))
            except socket.error as e:
                self._socket = None
                raise ConnectionError(f"Failed to connect to {self.host}:{self.port}: {e}")

            # Read server banner
            server_banner = b""
            while True:
                try:
                    char = self._socket.recv(1)
                    if not char:
                        raise ConnectionError("Server closed connection during handshake")
                    server_banner += char
                    if char == b"\n":
                        break
                except socket.timeout:
                    raise ConnectionError("Timeout reading server banner during handshake")

            # Send client banner
            self._socket.sendall(CLIENT_BANNER.encode("ascii"))

            # Remove timeout for ongoing connection - use keepalive instead
            self._socket.settimeout(None)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

            self._connected = True

            # Send LogHeader
            self._send_log_header()

            if self.on_connect:
                self.on_connect(server_banner.decode("ascii").strip())

            return server_banner.decode("ascii").strip()

    def _send_log_header(self) -> None:
        """Send the initial LogHeader packet after connection."""
        packet = {
            "packet_type": PacketType.LOG_HEADER,
            "content": self.build_log_header_content(),
        }
        self._internal_write_packet(packet)

    def disconnect(self) -> None:
        """Disconnect from SmartInspect Console."""
        with self._lock:
            self._queue.clear()
            self._internal_disconnect()

    def _internal_disconnect(self) -> None:
        """Low-level disconnect."""
        if self._socket:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

        was_connected = self._connected
        self._connected = False

        if was_connected and self.on_disconnect:
            self.on_disconnect()

    def _reset(self) -> None:
        """Reset connection state."""
        self._internal_disconnect()

    def _try_reconnect(self) -> None:
        """Attempt reconnection with time-gating."""
        if not self.reconnect or self._connect_in_progress:
            return

        current_time = time.time()
        if current_time - self._last_reconnect_time < self.reconnect_interval:
            return  # Too soon, skip

        self._last_reconnect_time = current_time

        # Start reconnection in background
        thread = threading.Thread(target=self._background_connect, daemon=True)
        thread.start()

    def write_packet(self, packet: Dict[str, Any]) -> None:
        """
        Write a packet to the connection.
        If disconnected and backlog is enabled, queues the packet.
        """
        if not self._connected:
            if not self.reconnect:
                return

            if self.backlog_enabled:
                self._queue.push(packet)
                if self._keep_open:
                    self._try_reconnect()
            return

        # Connected - send directly
        try:
            with self._lock:
                self._internal_write_packet(packet)
        except Exception as e:
            self._reset()
            if self.backlog_enabled:
                self._queue.push(packet)
            if self.on_error:
                self.on_error(e)

    def _internal_write_packet(self, packet: Dict[str, Any]) -> None:
        """Internal write (no locking, assumes locked)."""
        if not self._socket:
            raise ConnectionError("Socket not available")

        formatted = self._formatter.format(packet)
        if not formatted:
            return

        self._socket.sendall(formatted)

        # Read ACK (2 bytes)
        try:
            ack = self._socket.recv(ANSWER_SIZE)
            if len(ack) != ANSWER_SIZE:
                raise ConnectionError(f"Server ACK incomplete: expected {ANSWER_SIZE} bytes, got {len(ack)}")
        except socket.timeout:
            raise ConnectionError("Timeout waiting for server ACK")

    def _flush_queue(self) -> None:
        """Flush all queued packets."""
        packets = self._queue.get_all()
        for packet in packets:
            try:
                with self._lock:
                    self._internal_write_packet(packet)
            except Exception as e:
                # Re-queue remaining packets and stop
                self._queue.push(packet)
                for remaining in packets[packets.index(packet) + 1 :]:
                    self._queue.push(remaining)
                self._reset()
                if self.on_error:
                    self.on_error(e)
                break

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    def get_queue_stats(self) -> Dict[str, int]:
        """Get queue statistics."""
        return {
            "backlog_count": self._queue.count,
            "backlog_size": self._queue.size,
        }

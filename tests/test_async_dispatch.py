import threading
import time

from smartinspect.enums import PacketType
from smartinspect.protocol import TcpProtocol


def _build_packet():
    return {
        "packet_type": PacketType.LOG_ENTRY,
        "title": "hello",
        "app_name": "test-app",
        "session_name": "Main",
        "host_name": "localhost",
        "data": b"",
    }


def test_async_write_packet_is_non_blocking():
    protocol = TcpProtocol(
        reconnect=False,
        backlog_enabled=False,
        async_enabled=True,
        async_queue=1024,
        async_throttle=False,
    )

    protocol._connected = True
    protocol._socket = object()
    send_done = threading.Event()

    def slow_send(packet):
        time.sleep(0.08)
        send_done.set()

    protocol._internal_write_packet = slow_send

    start = time.perf_counter()
    protocol.write_packet(_build_packet())
    elapsed = time.perf_counter() - start

    assert elapsed < 0.03
    assert send_done.wait(1.0)
    protocol.disconnect()


def test_sync_write_packet_blocks_caller_thread():
    protocol = TcpProtocol(
        reconnect=False,
        backlog_enabled=False,
        async_enabled=False,
    )

    protocol._connected = True
    protocol._socket = object()

    def slow_send(packet):
        time.sleep(0.06)

    protocol._internal_write_packet = slow_send

    start = time.perf_counter()
    protocol.write_packet(_build_packet())
    elapsed = time.perf_counter() - start

    assert elapsed >= 0.05
    protocol.disconnect()

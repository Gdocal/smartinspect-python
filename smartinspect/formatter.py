# SmartInspect Binary Formatter
# Handles serialization of packets into binary format

"""
Binary formatter for serializing packets to SmartInspect wire format.
Matches the C# BinaryFormatter implementation.
"""

import struct
from datetime import datetime
from typing import Optional, Dict, Any, Union

from .enums import PacketType, DELPHI_EPOCH_DAYS_OFFSET, Color, SI_DEFAULT_COLOR_VALUE


class BinaryFormatter:
    """
    BinaryFormatter - serializes packets to SmartInspect binary format.

    Packet format:
    [packet_type: int16] [data_size: int32] [data: bytes]
    """

    def __init__(self):
        self.stream: bytes = b""
        self.size: int = 0

    @staticmethod
    def write_int16(value: int) -> bytes:
        """Write a 16-bit signed integer (little endian)."""
        return struct.pack("<h", value)

    @staticmethod
    def write_int32(value: int) -> bytes:
        """Write a 32-bit signed integer (little endian)."""
        # Truncate to 32 bits first (for large values like Python thread IDs)
        value = value & 0xFFFFFFFF
        # Handle unsigned values that need to be written as signed
        if value > 0x7FFFFFFF:
            value = value - 0x100000000
        return struct.pack("<i", value)

    @staticmethod
    def write_uint32(value: int) -> bytes:
        """Write a 32-bit unsigned integer (little endian) - used for color."""
        return struct.pack("<I", value & 0xFFFFFFFF)

    @staticmethod
    def write_double(value: float) -> bytes:
        """Write a 64-bit double (little endian)."""
        return struct.pack("<d", value)

    @staticmethod
    def encode_string(value: Optional[str]) -> Optional[bytes]:
        """Encode string to UTF-8 bytes."""
        if value is None:
            return None
        return value.encode("utf-8")

    @staticmethod
    def date_to_timestamp(dt: datetime) -> float:
        """
        Convert Python datetime to SmartInspect timestamp (OLE Automation Date).
        OLE Automation Date is days since December 30, 1899 as a double.
        """
        # Get timestamp in seconds since Unix epoch
        timestamp = dt.timestamp()
        # Convert to days since Unix epoch
        days_since_unix = timestamp / 86400.0
        # Add offset to OLE epoch
        return days_since_unix + DELPHI_EPOCH_DAYS_OFFSET

    @staticmethod
    def color_to_int(color: Union[Color, Dict[str, int], None]) -> int:
        """
        Convert color to 32-bit integer (BGRA format for little-endian storage).
        """
        if color is None:
            return SI_DEFAULT_COLOR_VALUE

        if isinstance(color, Color):
            return color.to_int()

        if isinstance(color, dict):
            r = color.get("r", 0)
            g = color.get("g", 0)
            b = color.get("b", 0)
            a = color.get("a", 255)
            return ((r) | (g << 8) | (b << 16) | (a << 24)) & 0xFFFFFFFF

        return SI_DEFAULT_COLOR_VALUE

    def compile_log_header(self, packet: Dict[str, Any]) -> bytes:
        """Compile a LogHeader packet."""
        content_bytes = self.encode_string(packet.get("content", ""))
        parts = [self.write_int32(len(content_bytes) if content_bytes else 0)]
        if content_bytes:
            parts.append(content_bytes)
        return b"".join(parts)

    def compile_log_entry(self, packet: Dict[str, Any]) -> bytes:
        """
        Compile a LogEntry packet.

        LogEntry binary format:
        [logEntryType(4)] [viewerId(4)]
        [appNameLen(4)] [sessionNameLen(4)] [titleLen(4)] [hostNameLen(4)] [dataLen(4)]
        [processId(4)] [threadId(4)] [timestamp(8)] [color(4)]
        [appName] [sessionName] [title] [hostName] [data]
        """
        app_name_bytes = self.encode_string(packet.get("app_name", ""))
        session_name_bytes = self.encode_string(packet.get("session_name", ""))
        title_bytes = self.encode_string(packet.get("title", ""))
        host_name_bytes = self.encode_string(packet.get("host_name", ""))
        data_bytes = packet.get("data")

        timestamp = self.date_to_timestamp(packet.get("timestamp", datetime.now()))
        color_int = self.color_to_int(packet.get("color"))

        parts = [
            self.write_int32(packet.get("log_entry_type", 0)),
            self.write_int32(packet.get("viewer_id", 0)),
            self.write_int32(len(app_name_bytes) if app_name_bytes else 0),
            self.write_int32(len(session_name_bytes) if session_name_bytes else 0),
            self.write_int32(len(title_bytes) if title_bytes else 0),
            self.write_int32(len(host_name_bytes) if host_name_bytes else 0),
            self.write_int32(len(data_bytes) if data_bytes else 0),
            self.write_int32(packet.get("process_id", 0)),
            self.write_int32(packet.get("thread_id", 0)),
            self.write_double(timestamp),
            self.write_uint32(color_int),
        ]

        if app_name_bytes:
            parts.append(app_name_bytes)
        if session_name_bytes:
            parts.append(session_name_bytes)
        if title_bytes:
            parts.append(title_bytes)
        if host_name_bytes:
            parts.append(host_name_bytes)
        if data_bytes:
            parts.append(data_bytes)

        return b"".join(parts)

    def compile_watch(self, packet: Dict[str, Any]) -> bytes:
        """
        Compile a Watch packet.

        Watch binary format v2 (with group):
        [nameLen(4)] [valueLen(4)] [watchType(4)] [timestamp(8)] [groupLen(4)]
        [name] [value] [group]
        """
        name_bytes = self.encode_string(packet.get("name", ""))
        value_bytes = self.encode_string(packet.get("value", ""))
        group_bytes = self.encode_string(packet.get("group", ""))
        timestamp = self.date_to_timestamp(packet.get("timestamp", datetime.now()))

        parts = [
            self.write_int32(len(name_bytes) if name_bytes else 0),
            self.write_int32(len(value_bytes) if value_bytes else 0),
            self.write_int32(packet.get("watch_type", 0)),
            self.write_double(timestamp),
            self.write_int32(len(group_bytes) if group_bytes else 0),
        ]

        if name_bytes:
            parts.append(name_bytes)
        if value_bytes:
            parts.append(value_bytes)
        if group_bytes:
            parts.append(group_bytes)

        return b"".join(parts)

    def compile_process_flow(self, packet: Dict[str, Any]) -> bytes:
        """
        Compile a ProcessFlow packet.

        ProcessFlow binary format:
        [processFlowType(4)] [titleLen(4)] [hostNameLen(4)]
        [processId(4)] [threadId(4)] [timestamp(8)]
        [title] [hostName]
        """
        title_bytes = self.encode_string(packet.get("title", ""))
        host_name_bytes = self.encode_string(packet.get("host_name", ""))
        timestamp = self.date_to_timestamp(packet.get("timestamp", datetime.now()))

        parts = [
            self.write_int32(packet.get("process_flow_type", 0)),
            self.write_int32(len(title_bytes) if title_bytes else 0),
            self.write_int32(len(host_name_bytes) if host_name_bytes else 0),
            self.write_int32(packet.get("process_id", 0)),
            self.write_int32(packet.get("thread_id", 0)),
            self.write_double(timestamp),
        ]

        if title_bytes:
            parts.append(title_bytes)
        if host_name_bytes:
            parts.append(host_name_bytes)

        return b"".join(parts)

    def compile_control_command(self, packet: Dict[str, Any]) -> bytes:
        """
        Compile a ControlCommand packet.

        ControlCommand binary format:
        [controlCommandType(4)] [dataLen(4)] [data]
        """
        data_bytes = packet.get("data")

        parts = [
            self.write_int32(packet.get("control_command_type", 0)),
            self.write_int32(len(data_bytes) if data_bytes else 0),
        ]

        if data_bytes:
            parts.append(data_bytes)

        return b"".join(parts)

    def compile_stream(self, packet: Dict[str, Any]) -> bytes:
        """
        Compile a Stream packet.

        Stream binary format v3 (with group):
        [channelLen(4)] [dataLen(4)] [typeLen(4)] [timestamp(8)] [groupLen(4)]
        [channel] [data] [type] [group]
        """
        channel_bytes = self.encode_string(packet.get("channel", ""))
        data_bytes = self.encode_string(packet.get("data", ""))
        type_bytes = self.encode_string(packet.get("stream_type", ""))
        group_bytes = self.encode_string(packet.get("group", ""))
        timestamp = self.date_to_timestamp(packet.get("timestamp", datetime.now()))

        parts = [
            self.write_int32(len(channel_bytes) if channel_bytes else 0),
            self.write_int32(len(data_bytes) if data_bytes else 0),
            self.write_int32(len(type_bytes) if type_bytes else 0),
            self.write_double(timestamp),
            self.write_int32(len(group_bytes) if group_bytes else 0),
        ]

        if channel_bytes:
            parts.append(channel_bytes)
        if data_bytes:
            parts.append(data_bytes)
        if type_bytes:
            parts.append(type_bytes)
        if group_bytes:
            parts.append(group_bytes)

        return b"".join(parts)

    def compile(self, packet: Dict[str, Any]) -> int:
        """Compile a packet based on its type. Returns total size including header."""
        packet_type = packet.get("packet_type")

        if packet_type == PacketType.LOG_HEADER:
            self.stream = self.compile_log_header(packet)
        elif packet_type == PacketType.LOG_ENTRY:
            self.stream = self.compile_log_entry(packet)
        elif packet_type == PacketType.WATCH:
            self.stream = self.compile_watch(packet)
        elif packet_type == PacketType.PROCESS_FLOW:
            self.stream = self.compile_process_flow(packet)
        elif packet_type == PacketType.CONTROL_COMMAND:
            self.stream = self.compile_control_command(packet)
        elif packet_type == PacketType.STREAM:
            self.stream = self.compile_stream(packet)
        else:
            self.stream = b""

        self.size = len(self.stream)
        return self.size + 6  # +6 for packet header (2 bytes type + 4 bytes size)

    def format(self, packet: Dict[str, Any]) -> bytes:
        """
        Format a packet into a complete binary buffer ready to send.
        Format: [packetType(2)] [dataSize(4)] [data]
        """
        self.compile(packet)

        if self.size > 0:
            return b"".join([
                self.write_int16(packet.get("packet_type", 0)),
                self.write_int32(self.size),
                self.stream,
            ])
        return b""

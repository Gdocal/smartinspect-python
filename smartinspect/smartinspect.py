# SmartInspect Main Class
# Central configuration and connection management

"""
SmartInspect - main class for managing logging.
Provides connection management, session handling, and convenience proxy methods.
"""

import configparser
import os
import re
import socket
from datetime import datetime
from typing import Optional, Dict, Any, Union

from .enums import Level, PacketType
from .protocol import TcpProtocol, detect_wsl_host
from .session import Session


class SmartInspect:
    """
    SmartInspect - main class for managing logging.

    Example usage:
        si = SmartInspect("MyApp")
        si.connect(host="127.0.0.1", port=4228)

        si.log_message("Hello, SmartInspect!")
        si.disconnect()
    """

    def __init__(self, app_name: str = "Python App"):
        self.app_name = app_name
        self.host_name = socket.gethostname()
        self.room = "default"
        self.enabled = False
        self.level = Level.DEBUG
        self.default_level = Level.MESSAGE

        self.protocol: Optional[TcpProtocol] = None
        self._sessions: Dict[str, Session] = {}
        self._connection_options: Optional[Dict[str, Any]] = None
        self._variables: Dict[str, str] = {}
        self.connections: str = ""

        self.main_session = Session(self, "Main")
        self._sessions["Main"] = self.main_session

    def connect(
        self,
        host: Optional[str] = None,
        port: int = 4228,
        timeout: float = 30.0,
        room: Optional[str] = None,
        reconnect: bool = True,
        reconnect_interval: float = 3.0,
        backlog_enabled: bool = True,
        backlog_queue: int = 2048,
        backlog_keep_open: bool = True,
        backlog_flush_on: Union[int, str] = Level.ERROR,
        async_enabled: bool = True,
        async_queue: int = 2048,
        async_throttle: bool = False,
        async_clear_on_disconnect: bool = False,
        on_error: Optional[callable] = None,
        on_connect: Optional[callable] = None,
        on_disconnect: Optional[callable] = None,
        connection_string: Optional[str] = None,
    ) -> "SmartInspect":
        """Connect to SmartInspect server."""
        if connection_string:
            connection_string = self._expand_variables(connection_string)
            self.connections = connection_string
            options = self.parse_connection_string(connection_string)
            host = options.get("host", host)
            port = options.get("port", port)
            timeout = options.get("timeout", timeout)
            room = options.get("room", room)
            reconnect = options.get("reconnect", reconnect)
            reconnect_interval = options.get("reconnect_interval", reconnect_interval)
            backlog_enabled = options.get("backlog_enabled", backlog_enabled)
            backlog_queue = options.get("backlog_queue", backlog_queue)
            backlog_keep_open = options.get("backlog_keep_open", backlog_keep_open)
            backlog_flush_on = options.get("backlog_flush_on", backlog_flush_on)
            async_enabled = options.get("async_enabled", async_enabled)
            async_queue = options.get("async_queue", async_queue)
            async_throttle = options.get("async_throttle", async_throttle)
            async_clear_on_disconnect = options.get("async_clear_on_disconnect", async_clear_on_disconnect)

        self._connection_options = {
            "host": host,
            "port": port,
            "timeout": timeout,
            "room": room,
            "reconnect": reconnect,
            "reconnect_interval": reconnect_interval,
            "backlog_enabled": backlog_enabled,
            "backlog_queue": backlog_queue,
            "backlog_keep_open": backlog_keep_open,
            "backlog_flush_on": backlog_flush_on,
            "async_enabled": async_enabled,
            "async_queue": async_queue,
            "async_throttle": async_throttle,
            "async_clear_on_disconnect": async_clear_on_disconnect,
            "on_error": on_error,
            "on_connect": on_connect,
            "on_disconnect": on_disconnect,
        }

        if room:
            self.room = room

        if host is None:
            wsl_host = detect_wsl_host()
            host = wsl_host if wsl_host else "127.0.0.1"

        self.protocol = TcpProtocol(
            host=host,
            port=port,
            timeout=timeout,
            app_name=self.app_name,
            host_name=self.host_name,
            room=self.room,
            on_error=on_error,
            on_connect=on_connect,
            on_disconnect=on_disconnect,
            reconnect=reconnect,
            reconnect_interval=reconnect_interval,
            backlog_enabled=backlog_enabled,
            backlog_queue=backlog_queue,
            backlog_keep_open=backlog_keep_open,
            backlog_flush_on=self._parse_level(backlog_flush_on),
            async_enabled=async_enabled,
            async_queue=async_queue,
            async_throttle=async_throttle,
            async_clear_on_disconnect=async_clear_on_disconnect,
        )

        self.enabled = True
        self.protocol.connect()
        return self

    def parse_connection_string(self, conn_str: str) -> Dict[str, Any]:
        """Parse connection string like tcp(host=...,port=...)."""
        options: Dict[str, Any] = {}
        match = re.match(r"tcp\(([^)]+)\)", conn_str, re.IGNORECASE)
        if not match:
            return options

        for pair in match.group(1).split(","):
            eq_index = pair.find("=")
            if eq_index == -1:
                continue

            key = pair[:eq_index].strip().lower()
            value = pair[eq_index + 1 :].strip()

            if key == "host":
                options["host"] = value
            elif key == "port":
                options["port"] = int(value)
            elif key == "timeout":
                options["timeout"] = float(value)
            elif key == "room":
                options["room"] = value
            elif key == "reconnect":
                options["reconnect"] = self._parse_boolean(value)
            elif key == "reconnect.interval":
                options["reconnect_interval"] = self._parse_timespan_seconds(value)
            elif key == "backlog.enabled":
                options["backlog_enabled"] = self._parse_boolean(value)
            elif key == "backlog.queue":
                options["backlog_queue"] = self._parse_size_kb(value)
            elif key == "backlog.keepopen":
                options["backlog_keep_open"] = self._parse_boolean(value)
            elif key == "backlog.flushon":
                options["backlog_flush_on"] = self._parse_level(value)
            elif key == "backlog":
                size = self._parse_size_kb(value)
                if size > 0:
                    options["backlog_enabled"] = True
                    options["backlog_queue"] = size
                else:
                    options["backlog_enabled"] = False
            elif key == "flushon":
                options["backlog_flush_on"] = self._parse_level(value)
            elif key == "keepopen":
                options["backlog_keep_open"] = self._parse_boolean(value)
            elif key == "async.enabled":
                options["async_enabled"] = self._parse_boolean(value)
            elif key == "async.queue":
                options["async_queue"] = self._parse_size_kb(value)
            elif key == "async.throttle":
                options["async_throttle"] = self._parse_boolean(value)
            elif key == "async.clearondisconnect":
                options["async_clear_on_disconnect"] = self._parse_boolean(value)

        return options

    @staticmethod
    def _parse_boolean(value: str) -> bool:
        return str(value).strip().lower() in ("true", "1", "yes")

    @staticmethod
    def _parse_level(value: Union[int, str]) -> int:
        if isinstance(value, int):
            return value
        mapping = {
            "debug": Level.DEBUG,
            "verbose": Level.VERBOSE,
            "message": Level.MESSAGE,
            "warning": Level.WARNING,
            "error": Level.ERROR,
            "fatal": Level.FATAL,
            "control": Level.CONTROL,
        }
        return int(mapping.get(str(value).strip().lower(), Level.ERROR))

    @staticmethod
    def _parse_timespan_seconds(value: Union[int, float, str]) -> float:
        if isinstance(value, (int, float)):
            return float(value) / 1000.0
        text = str(value).strip().lower()
        if text.endswith("ms"):
            return float(text[:-2].strip()) / 1000.0
        if text.endswith("s"):
            return float(text[:-1].strip())
        return float(text) / 1000.0

    @staticmethod
    def _parse_size_kb(value: Union[int, float, str]) -> int:
        if isinstance(value, (int, float)):
            return int(value)
        text = str(value).strip().lower()
        if text.endswith("kb"):
            return int(float(text[:-2].strip()))
        if text.endswith("mb"):
            return int(float(text[:-2].strip()) * 1024)
        if text.endswith("gb"):
            return int(float(text[:-2].strip()) * 1024 * 1024)
        return int(float(text))

    def _expand_variables(self, value: str) -> str:
        text = str(value)

        def repl_brace(match):
            key = match.group(1)
            return self._variables.get(key, match.group(0))

        def repl_pct(match):
            key = match.group(1)
            return self._variables.get(key, match.group(0))

        text = re.sub(r"\$\{([^}]+)\}", repl_brace, text)
        text = re.sub(r"%([^%]+)%", repl_pct, text)
        return text

    @staticmethod
    def _read_configuration_values(file_name: str) -> Dict[str, str]:
        if not file_name or not os.path.exists(file_name):
            return {}

        with open(file_name, "r", encoding="utf-8") as f:
            raw = f.read()

        parser = configparser.ConfigParser()
        try:
            parser.read_string(raw)
        except configparser.MissingSectionHeaderError:
            parser.read_string("[smartinspect]\n" + raw)

        values: Dict[str, str] = {}
        for section in parser.sections():
            for key, val in parser.items(section):
                values[key.lower()] = val
        return values

    def disconnect(self) -> None:
        if self.protocol:
            self.protocol.disconnect()
            self.protocol = None
        self.enabled = False

    def is_connected(self) -> bool:
        return self.protocol is not None and self.protocol.is_connected()

    def send_packet(self, packet: Dict[str, Any]) -> None:
        if not self.enabled or not self.protocol:
            return
        try:
            self.protocol.write_packet(packet)
        except Exception:
            pass

    def get_queue_stats(self) -> Dict[str, int]:
        if self.protocol:
            return self.protocol.get_queue_stats()
        return {"backlog_count": 0, "backlog_size": 0, "async_count": 0, "async_size": 0}

    def get_session(self, name: str) -> Session:
        if name not in self._sessions:
            session = Session(self, name)
            self._sessions[name] = session
        return self._sessions[name]

    def add_session(self, session_name: str, store: bool = False) -> Session:
        """C# parity: AddSession(name[, store])."""
        if session_name is None:
            return None
        session = Session(self, session_name)
        if store:
            self._sessions[session_name] = session
        return session

    def delete_session(self, session_or_name: Union[str, Session]) -> None:
        """Delete session by name or instance."""
        if isinstance(session_or_name, Session):
            name = session_or_name.name
        else:
            name = str(session_or_name)
        if name != "Main":
            self._sessions.pop(name, None)

    def set_level(self, level: Union[int, str]) -> None:
        self.level = self._parse_level(level)

    def set_enabled(self, enabled: bool) -> None:
        if enabled == self.enabled:
            return
        if enabled:
            self.enabled = True
            if self._connection_options and not self.is_connected():
                self.connect(**self._connection_options)
        else:
            self.enabled = False
            if self.protocol:
                self.protocol.disconnect()
                self.protocol = None

    # ==================== C# SmartInspect public method parity ====================

    def dispatch(self, caption: str, action: int, state: Any) -> None:
        if caption is None:
            return
        self.send_control_command(
            {
                "command_type": int(action),
                "data": {"caption": str(caption), "action": int(action), "state": state},
            }
        )

    def dispose(self) -> None:
        self.disconnect()

    def get_variable(self, key: str) -> Optional[str]:
        if key is None:
            return None
        return self._variables.get(str(key))

    def load_configuration(self, file_name: str) -> None:
        values = self._read_configuration_values(file_name)
        if not values:
            return

        app_name = values.get("appname")
        if app_name is not None:
            self.app_name = app_name

        if "level" in values:
            self.set_level(values["level"])

        if "defaultlevel" in values:
            self.default_level = self._parse_level(values["defaultlevel"])

        has_enabled = "enabled" in values
        enabled_value = self._parse_boolean(values.get("enabled", "false")) if has_enabled else None

        if "connections" in values:
            self.connections = self._expand_variables(values["connections"])
            if not has_enabled:
                self.load_connections(file_name, do_not_enable=True)
            elif enabled_value:
                self.load_connections(file_name, do_not_enable=False)
            else:
                self.set_enabled(False)
                self.load_connections(file_name, do_not_enable=True)

    def load_connections(self, file_name: str, do_not_enable: bool = False) -> None:
        values = self._read_configuration_values(file_name)
        connections = values.get("connections")
        if not connections:
            return

        connections = self._expand_variables(connections)
        self.connections = connections
        parsed = self.parse_connection_string(connections)

        self._connection_options = {
            "host": parsed.get("host"),
            "port": parsed.get("port", 4228),
            "timeout": parsed.get("timeout", 30.0),
            "room": parsed.get("room"),
            "reconnect": parsed.get("reconnect", True),
            "reconnect_interval": parsed.get("reconnect_interval", 3.0),
            "backlog_enabled": parsed.get("backlog_enabled", True),
            "backlog_queue": parsed.get("backlog_queue", 2048),
            "backlog_keep_open": parsed.get("backlog_keep_open", True),
            "backlog_flush_on": parsed.get("backlog_flush_on", Level.ERROR),
            "async_enabled": parsed.get("async_enabled", True),
            "async_queue": parsed.get("async_queue", 2048),
            "async_throttle": parsed.get("async_throttle", False),
            "async_clear_on_disconnect": parsed.get("async_clear_on_disconnect", False),
            "on_error": None,
            "on_connect": None,
            "on_disconnect": None,
        }

        if do_not_enable:
            return

        self.connect(connection_string=connections)

    def now(self) -> datetime:
        return datetime.now()

    def send_control_command(self, control_command: Any) -> None:
        packet = self._packet_from_object(control_command)
        if "command_type" not in packet and isinstance(control_command, int):
            packet["command_type"] = int(control_command)
        packet["packet_type"] = PacketType.CONTROL_COMMAND
        self.send_packet(packet)

    def send_log_entry(self, log_entry: Any) -> None:
        packet = self._packet_from_object(log_entry)
        packet["packet_type"] = PacketType.LOG_ENTRY
        self.send_packet(packet)

    def send_process_flow(self, process_flow: Any) -> None:
        packet = self._packet_from_object(process_flow)
        packet["packet_type"] = PacketType.PROCESS_FLOW
        self.send_packet(packet)

    def send_watch(self, watch: Any) -> None:
        packet = self._packet_from_object(watch)
        packet["packet_type"] = PacketType.WATCH
        self.send_packet(packet)

    def send_stream_packet(self, stream_packet: Any) -> None:
        packet = self._packet_from_object(stream_packet)
        packet["packet_type"] = PacketType.STREAM
        self.send_packet(packet)

    def set_variable(self, key: str, value: str) -> None:
        if key is None or value is None:
            return
        self._variables[str(key)] = str(value)

    def unset_variable(self, key: str) -> None:
        if key is None:
            return
        self._variables.pop(str(key), None)

    def _packet_from_object(self, packet: Any) -> Dict[str, Any]:
        if isinstance(packet, dict):
            return dict(packet)
        data: Dict[str, Any] = {}
        for key in dir(packet):
            if key.startswith("_"):
                continue
            try:
                value = getattr(packet, key)
            except Exception:
                continue
            if callable(value):
                continue
            data[key] = value
        return data

    def __getattr__(self, name: str):
        """Forward unknown members to main session for convenience parity."""
        if hasattr(self.main_session, name):
            return getattr(self.main_session, name)
        raise AttributeError(f"{self.__class__.__name__!s} has no attribute {name!r}")


# Singleton instance (like SiAuto in C#)
_default_instance: Optional[SmartInspect] = None


def get_default() -> SmartInspect:
    """Get the default SmartInspect instance."""
    global _default_instance
    if _default_instance is None:
        _default_instance = SmartInspect("Python App")
    return _default_instance


def get_main_session() -> Session:
    """Get the main session from the default instance."""
    return get_default().main_session

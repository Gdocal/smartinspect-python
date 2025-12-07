# SmartInspect Main Class
# Central configuration and connection management

"""
SmartInspect - main class for managing logging.
Provides connection management, session handling, and convenience proxy methods.
"""

import re
import socket
from typing import Optional, Dict, Any, Union

from .enums import Level
from .protocol import TcpProtocol, detect_wsl_host
from .session import Session


class SmartInspect:
    """
    SmartInspect - main class for managing logging.

    Example usage:
        si = SmartInspect("MyApp")
        si.connect(host="127.0.0.1", port=4228)

        # Use main session
        si.log_message("Hello, SmartInspect!")
        si.log_object("User", {"name": "John", "age": 30})

        # Or get named sessions
        auth_session = si.get_session("Auth")
        auth_session.log_message("User logged in")

        si.disconnect()
    """

    def __init__(self, app_name: str = "Python App"):
        self.app_name = app_name
        self.host_name = socket.gethostname()
        self.room = "default"  # Room for log isolation (multi-project support)
        self.enabled = False
        self.level = Level.DEBUG
        self.default_level = Level.MESSAGE

        self.protocol: Optional[TcpProtocol] = None
        self._sessions: Dict[str, Session] = {}

        # Create default session
        self.main_session = Session(self, "Main")
        self._sessions["Main"] = self.main_session

    def connect(
        self,
        host: Optional[str] = None,
        port: int = 4228,
        timeout: float = 30.0,
        room: Optional[str] = None,
        # Reconnect options
        reconnect: bool = True,
        reconnect_interval: float = 3.0,
        # Backlog options
        backlog_enabled: bool = True,
        backlog_queue: int = 2048,  # KB
        backlog_keep_open: bool = True,
        # Callbacks
        on_error: Optional[callable] = None,
        on_connect: Optional[callable] = None,
        on_disconnect: Optional[callable] = None,
        # Or use connection string
        connection_string: Optional[str] = None,
    ) -> "SmartInspect":
        """
        Connect to SmartInspect Console.

        Args:
            host: TCP host (auto-detects for WSL if not specified)
            port: TCP port (default: 4228)
            timeout: Connection timeout in seconds (default: 30)
            room: Log room name for isolation (default: 'default')
            reconnect: Enable auto-reconnect (default: True)
            reconnect_interval: Min time between reconnects in seconds (default: 3)
            backlog_enabled: Enable packet buffering when disconnected (default: True)
            backlog_queue: Max backlog size in KB (default: 2048)
            backlog_keep_open: Keep connection open (default: True)
            on_error: Callback for errors
            on_connect: Callback when connected
            on_disconnect: Callback when disconnected
            connection_string: Connection string like "tcp(host=localhost,port=4228)"

        Returns:
            self for chaining
        """
        # Parse connection string if provided
        if connection_string:
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

        # Set room
        if room:
            self.room = room

        # Auto-detect WSL host if not specified
        if host is None:
            wsl_host = detect_wsl_host()
            host = wsl_host if wsl_host else "127.0.0.1"

        # Create protocol
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
        )

        # Enable BEFORE connect to allow backlog buffering
        self.enabled = True

        # Start connection (non-blocking)
        self.protocol.connect()

        return self

    def parse_connection_string(self, conn_str: str) -> Dict[str, Any]:
        """
        Parse a connection string like "tcp(host=localhost,port=4228,room=myproject)".

        Supports options:
        - host, port, timeout, room
        - reconnect, reconnect.interval
        - backlog.enabled, backlog.queue, backlog.keepopen
        """
        options: Dict[str, Any] = {}

        # Match tcp(options) format
        match = re.match(r"tcp\(([^)]+)\)", conn_str, re.IGNORECASE)
        if not match:
            return options

        pairs = match.group(1).split(",")

        for pair in pairs:
            eq_index = pair.find("=")
            if eq_index == -1:
                continue

            key = pair[:eq_index].strip().lower()
            value = pair[eq_index + 1 :].strip()

            # Basic options
            if key == "host":
                options["host"] = value
            elif key == "port":
                options["port"] = int(value)
            elif key == "timeout":
                options["timeout"] = float(value)
            elif key == "room":
                options["room"] = value

            # Reconnect options
            elif key == "reconnect":
                options["reconnect"] = self._parse_boolean(value)
            elif key == "reconnect.interval":
                options["reconnect_interval"] = float(value) / 1000  # ms to seconds

            # Backlog options
            elif key == "backlog.enabled":
                options["backlog_enabled"] = self._parse_boolean(value)
            elif key == "backlog.queue":
                options["backlog_queue"] = int(value)
            elif key == "backlog.keepopen":
                options["backlog_keep_open"] = self._parse_boolean(value)
            elif key == "backlog":
                size = int(value)
                if size > 0:
                    options["backlog_enabled"] = True
                    options["backlog_queue"] = size
                else:
                    options["backlog_enabled"] = False

        return options

    @staticmethod
    def _parse_boolean(value: str) -> bool:
        """Parse boolean from string."""
        return value.lower() in ("true", "1", "yes")

    def disconnect(self) -> None:
        """Disconnect from SmartInspect Console."""
        if self.protocol:
            self.protocol.disconnect()
            self.protocol = None
        self.enabled = False

    def is_connected(self) -> bool:
        """Check if connected."""
        return self.protocol is not None and self.protocol.is_connected()

    def send_packet(self, packet: Dict[str, Any]) -> None:
        """
        Send a packet.
        In backlog mode, packets may be queued for later delivery.
        """
        if not self.enabled or not self.protocol:
            return

        try:
            self.protocol.write_packet(packet)
        except Exception:
            pass  # Errors are handled by protocol callbacks

    def get_queue_stats(self) -> Dict[str, int]:
        """Get queue statistics for monitoring."""
        if self.protocol:
            return self.protocol.get_queue_stats()
        return {"backlog_count": 0, "backlog_size": 0}

    def get_session(self, name: str) -> Session:
        """Get or create a session."""
        if name not in self._sessions:
            session = Session(self, name)
            self._sessions[name] = session
        return self._sessions[name]

    def add_session(self, name: str) -> Session:
        """Add a new session."""
        return self.get_session(name)

    def delete_session(self, name: str) -> None:
        """Delete a session."""
        if name != "Main":
            self._sessions.pop(name, None)

    def set_level(self, level: Union[int, str]) -> None:
        """Set the global log level."""
        if isinstance(level, str):
            level_map = {
                "debug": Level.DEBUG,
                "verbose": Level.VERBOSE,
                "message": Level.MESSAGE,
                "warning": Level.WARNING,
                "error": Level.ERROR,
                "fatal": Level.FATAL,
            }
            self.level = level_map.get(level.lower(), Level.DEBUG)
        else:
            self.level = level

    def set_enabled(self, enabled: bool) -> None:
        """Enable/disable logging."""
        self.enabled = enabled

    # ==================== Convenience proxy methods to main session ====================

    def log_message(self, *args):
        self.main_session.log_message(*args)

    def log_debug(self, *args):
        self.main_session.log_debug(*args)

    def log_verbose(self, *args):
        self.main_session.log_verbose(*args)

    def log_warning(self, *args):
        self.main_session.log_warning(*args)

    def log_error(self, *args):
        self.main_session.log_error(*args)

    def log_fatal(self, *args):
        self.main_session.log_fatal(*args)

    def log_exception(self, *args, **kwargs):
        self.main_session.log_exception(*args, **kwargs)

    def log_object(self, *args, **kwargs):
        self.main_session.log_object(*args, **kwargs)

    def log_array(self, *args, **kwargs):
        self.main_session.log_array(*args, **kwargs)

    def log_dictionary(self, *args, **kwargs):
        self.main_session.log_dictionary(*args, **kwargs)

    def log_table(self, *args, **kwargs):
        self.main_session.log_table(*args, **kwargs)

    def log_text(self, *args, **kwargs):
        self.main_session.log_text(*args, **kwargs)

    def log_json(self, *args, **kwargs):
        self.main_session.log_json(*args, **kwargs)

    def log_html(self, *args, **kwargs):
        self.main_session.log_html(*args, **kwargs)

    def log_xml(self, *args, **kwargs):
        self.main_session.log_xml(*args, **kwargs)

    def log_sql(self, *args, **kwargs):
        self.main_session.log_sql(*args, **kwargs)

    def log_javascript(self, *args, **kwargs):
        self.main_session.log_javascript(*args, **kwargs)

    def log_python(self, *args, **kwargs):
        self.main_session.log_python(*args, **kwargs)

    def log_binary(self, *args, **kwargs):
        self.main_session.log_binary(*args, **kwargs)

    def log_value(self, *args, **kwargs):
        self.main_session.log_value(*args, **kwargs)

    def log_string(self, *args, **kwargs):
        self.main_session.log_string(*args, **kwargs)

    def log_int(self, *args, **kwargs):
        self.main_session.log_int(*args, **kwargs)

    def log_number(self, *args, **kwargs):
        self.main_session.log_number(*args, **kwargs)

    def log_bool(self, *args, **kwargs):
        self.main_session.log_bool(*args, **kwargs)

    def log_datetime(self, *args, **kwargs):
        self.main_session.log_datetime(*args, **kwargs)

    def log_separator(self):
        self.main_session.log_separator()

    def log_colored(self, *args, **kwargs):
        self.main_session.log_colored(*args, **kwargs)

    def add_checkpoint(self, *args, **kwargs):
        self.main_session.add_checkpoint(*args, **kwargs)

    def inc_counter(self, *args, **kwargs):
        self.main_session.inc_counter(*args, **kwargs)

    def dec_counter(self, *args, **kwargs):
        self.main_session.dec_counter(*args, **kwargs)

    def watch(self, *args, **kwargs):
        self.main_session.watch(*args, **kwargs)

    def watch_string(self, *args, **kwargs):
        self.main_session.watch_string(*args, **kwargs)

    def watch_int(self, *args, **kwargs):
        self.main_session.watch_int(*args, **kwargs)

    def watch_float(self, *args, **kwargs):
        self.main_session.watch_float(*args, **kwargs)

    def watch_bool(self, *args, **kwargs):
        self.main_session.watch_bool(*args, **kwargs)

    def enter_method(self, *args, **kwargs):
        self.main_session.enter_method(*args, **kwargs)

    def leave_method(self, *args, **kwargs):
        self.main_session.leave_method(*args, **kwargs)

    def track_method(self, *args, **kwargs):
        return self.main_session.track_method(*args, **kwargs)

    def enter_process(self, *args, **kwargs):
        self.main_session.enter_process(*args, **kwargs)

    def leave_process(self, *args, **kwargs):
        self.main_session.leave_process(*args, **kwargs)

    def enter_thread(self, *args, **kwargs):
        self.main_session.enter_thread(*args, **kwargs)

    def leave_thread(self, *args, **kwargs):
        self.main_session.leave_thread(*args, **kwargs)

    def clear_all(self):
        self.main_session.clear_all()

    def clear_log(self):
        self.main_session.clear_log()

    def clear_watches(self):
        self.main_session.clear_watches()

    def clear_auto_views(self):
        self.main_session.clear_auto_views()

    def clear_process_flow(self):
        self.main_session.clear_process_flow()

    def log_assert(self, *args, **kwargs):
        self.main_session.log_assert(*args, **kwargs)

    def log_conditional(self, *args, **kwargs):
        self.main_session.log_conditional(*args, **kwargs)

    def log_system(self, *args, **kwargs):
        self.main_session.log_system(*args, **kwargs)

    def log_memory(self, *args, **kwargs):
        self.main_session.log_memory(*args, **kwargs)

    def log_stack_trace(self, *args, **kwargs):
        self.main_session.log_stack_trace(*args, **kwargs)

    def log_environment(self, *args, **kwargs):
        self.main_session.log_environment(*args, **kwargs)

    def log_stream(self, *args, **kwargs):
        self.main_session.log_stream(*args, **kwargs)

    def time_start(self, *args, **kwargs):
        self.main_session.time_start(*args, **kwargs)

    def time_end(self, *args, **kwargs):
        self.main_session.time_end(*args, **kwargs)


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

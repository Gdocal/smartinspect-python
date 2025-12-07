# SmartInspect Session
# Main logging class with all logging methods

"""
Session class - provides all logging methods.
Port of C#/Node.js Session class with comprehensive logging capabilities.
"""

import os
import sys
import json
import platform
import threading
import traceback
import time
from datetime import datetime
from contextlib import contextmanager
from typing import Optional, Any, Dict, List, Union, Callable

from .enums import (
    Level,
    PacketType,
    LogEntryType,
    ViewerId,
    WatchType,
    ControlCommandType,
    ProcessFlowType,
    SourceId,
    Color,
    DEFAULT_COLOR,
)
from .contexts import (
    InspectorViewerContext,
    TableViewerContext,
    ListViewerContext,
    ValueListViewerContext,
    DataViewerContext,
    BinaryViewerContext,
    TextContext,
    SourceViewerContext,
    WebViewerContext,
)


class Session:
    """
    Session class - provides all logging methods.

    Each session has a name and can have its own level and color settings.
    Sessions are the primary interface for logging to SmartInspect Console.
    """

    def __init__(self, parent: "SmartInspect", name: str = "Main"):
        self.parent = parent
        self.name = name
        self.active = True
        self.level = Level.DEBUG
        self.color = DEFAULT_COLOR

        # Checkpoint and counter tracking
        self._checkpoint_counter = 0
        self._counters: Dict[str, int] = {}
        self._checkpoints: Dict[str, int] = {}

        # Timer tracking
        self._timers: Dict[str, float] = {}

    def is_on(self, level: Optional[int] = None) -> bool:
        """Check if logging is enabled at the given level."""
        if not self.active or not self.parent.enabled:
            return False
        if level is None:
            return True
        return level >= self.level and level >= self.parent.level

    def _get_process_id(self) -> int:
        """Get current process ID."""
        return os.getpid()

    def _get_thread_id(self) -> int:
        """Get current thread ID."""
        return threading.get_ident()

    def _send_log_entry(
        self,
        level: int,
        title: str,
        log_entry_type: int,
        viewer_id: int,
        color: Optional[Color] = None,
        data: Optional[bytes] = None,
    ) -> None:
        """Send a log entry packet."""
        if not self.is_on(level):
            return

        packet = {
            "packet_type": PacketType.LOG_ENTRY,
            "log_entry_type": log_entry_type,
            "viewer_id": viewer_id,
            "title": title,
            "app_name": self.parent.app_name,
            "session_name": self.name,
            "host_name": self.parent.host_name,
            "process_id": self._get_process_id(),
            "thread_id": self._get_thread_id(),
            "timestamp": datetime.now(),
            "color": color or self.color,
            "data": data,
        }

        self.parent.send_packet(packet)

    def _send_context(
        self,
        level: int,
        title: str,
        log_entry_type: int,
        ctx: Any,
    ) -> None:
        """Send a context with data."""
        if not self.is_on(level):
            return

        data = ctx.get_viewer_data()
        self._send_log_entry(level, title, log_entry_type, ctx.viewer_id, None, data)

    def _send_watch(
        self,
        level: int,
        name: str,
        value: str,
        watch_type: int,
    ) -> None:
        """Send a watch packet."""
        if not self.is_on(level):
            return

        packet = {
            "packet_type": PacketType.WATCH,
            "name": name,
            "value": value,
            "watch_type": watch_type,
            "timestamp": datetime.now(),
        }

        self.parent.send_packet(packet)

    def _send_process_flow(
        self,
        level: int,
        title: str,
        process_flow_type: int,
    ) -> None:
        """Send a process flow packet."""
        if not self.is_on(level):
            return

        packet = {
            "packet_type": PacketType.PROCESS_FLOW,
            "process_flow_type": process_flow_type,
            "title": title,
            "host_name": self.parent.host_name,
            "process_id": self._get_process_id(),
            "thread_id": self._get_thread_id(),
            "timestamp": datetime.now(),
        }

        self.parent.send_packet(packet)

    def _send_control_command(
        self,
        control_command_type: int,
        data: Optional[bytes] = None,
    ) -> None:
        """Send a control command packet."""
        packet = {
            "packet_type": PacketType.CONTROL_COMMAND,
            "control_command_type": control_command_type,
            "data": data,
        }

        self.parent.send_packet(packet)

    def _format_value(self, value: Any) -> str:
        """Format a single value for display."""
        if value is None:
            return "None"
        if isinstance(value, str):
            return value
        if isinstance(value, Exception):
            return f"{type(value).__name__}: {value}\n{''.join(traceback.format_exception(type(value), value, value.__traceback__))}"
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, indent=2, default=str)
            except Exception:
                return repr(value)
        return str(value)

    def _format_args(self, *args) -> str:
        """Format arguments for logging (Python-style)."""
        if not args:
            return ""
        if len(args) == 1:
            return self._format_value(args[0])

        # Check if first arg is a format string
        if isinstance(args[0], str) and "%" in args[0]:
            try:
                return args[0] % args[1:]
            except Exception:
                pass

        return " ".join(self._format_value(arg) for arg in args)

    def log_internal_error(self, title: str) -> None:
        """Log internal error."""
        self._send_log_entry(Level.ERROR, title, LogEntryType.INTERNAL_ERROR, ViewerId.TITLE)

    # ==================== Basic Logging Methods ====================

    def log_message(self, *args) -> None:
        """Log a message."""
        title = self._format_args(*args)
        self._send_log_entry(Level.MESSAGE, title, LogEntryType.MESSAGE, ViewerId.TITLE)

    def log_debug(self, *args) -> None:
        """Log a debug message."""
        title = self._format_args(*args)
        self._send_log_entry(Level.DEBUG, title, LogEntryType.DEBUG, ViewerId.TITLE)

    def log_verbose(self, *args) -> None:
        """Log a verbose message."""
        title = self._format_args(*args)
        self._send_log_entry(Level.VERBOSE, title, LogEntryType.VERBOSE, ViewerId.TITLE)

    def log_warning(self, *args) -> None:
        """Log a warning."""
        title = self._format_args(*args)
        self._send_log_entry(Level.WARNING, title, LogEntryType.WARNING, ViewerId.TITLE)

    def log_error(self, *args) -> None:
        """Log an error."""
        title = self._format_args(*args)
        self._send_log_entry(Level.ERROR, title, LogEntryType.ERROR, ViewerId.TITLE)

    def log_fatal(self, *args) -> None:
        """Log a fatal error."""
        title = self._format_args(*args)
        self._send_log_entry(Level.FATAL, title, LogEntryType.FATAL, ViewerId.TITLE)

    def log_separator(self) -> None:
        """Log a separator."""
        self._send_log_entry(self.parent.default_level, "", LogEntryType.SEPARATOR, ViewerId.TITLE)

    # ==================== Colored Logging ====================

    def log_colored(self, color: Union[Color, tuple], *args) -> None:
        """Log a colored message."""
        if isinstance(color, tuple):
            color = Color(*color)
        title = self._format_args(*args)
        self._send_log_entry(self.parent.default_level, title, LogEntryType.MESSAGE, ViewerId.TITLE, color)

    # ==================== Exception Logging ====================

    def log_exception(self, error: Exception, title: Optional[str] = None) -> None:
        """Log an exception/error with full traceback."""
        if not self.is_on(Level.ERROR):
            return

        if error is None:
            self.log_internal_error("log_exception: error argument is None")
            return

        error_title = title or str(error) or "Error"
        ctx = DataViewerContext()
        ctx.load_from_text(
            "".join(traceback.format_exception(type(error), error, error.__traceback__))
        )
        self._send_context(Level.ERROR, error_title, LogEntryType.ERROR, ctx)

    # ==================== Variable Logging ====================

    def log_string(self, name: str, value: str) -> None:
        """Log a string variable."""
        title = f'{name} = "{value}"'
        self._send_log_entry(self.parent.default_level, title, LogEntryType.VARIABLE_VALUE, ViewerId.TITLE)

    def log_int(self, name: str, value: int, include_hex: bool = False) -> None:
        """Log an integer variable."""
        title = f"{name} = {value}"
        if include_hex:
            title += f" (0x{value:08x})"
        self._send_log_entry(self.parent.default_level, title, LogEntryType.VARIABLE_VALUE, ViewerId.TITLE)

    def log_number(self, name: str, value: Union[int, float]) -> None:
        """Log a number variable."""
        title = f"{name} = {value}"
        self._send_log_entry(self.parent.default_level, title, LogEntryType.VARIABLE_VALUE, ViewerId.TITLE)

    def log_bool(self, name: str, value: bool) -> None:
        """Log a boolean variable."""
        title = f"{name} = {'True' if value else 'False'}"
        self._send_log_entry(self.parent.default_level, title, LogEntryType.VARIABLE_VALUE, ViewerId.TITLE)

    def log_datetime(self, name: str, value: datetime) -> None:
        """Log a date/time value."""
        title = f"{name} = {value.isoformat()}"
        self._send_log_entry(self.parent.default_level, title, LogEntryType.VARIABLE_VALUE, ViewerId.TITLE)

    def log_value(self, name: str, value: Any) -> None:
        """Log any value with its type."""
        if value is None:
            formatted = "None"
        elif isinstance(value, str):
            formatted = f'"{value}"'
        elif isinstance(value, bool):
            formatted = "True" if value else "False"
        elif isinstance(value, datetime):
            formatted = value.isoformat()
        elif isinstance(value, (dict, list)):
            formatted = json.dumps(value, default=str)
        else:
            formatted = str(value)

        title = f"{name} = {formatted}"
        self._send_log_entry(self.parent.default_level, title, LogEntryType.VARIABLE_VALUE, ViewerId.TITLE)

    # ==================== Object Logging ====================

    def log_object(self, title: str, obj: Any, include_private: bool = False) -> None:
        """Log an object with its properties."""
        if not self.is_on(self.parent.default_level):
            return

        if obj is None:
            self.log_internal_error("log_object: object argument is None")
            return

        ctx = InspectorViewerContext()

        try:
            type_name = type(obj).__name__
            ctx.start_group("General")
            ctx.append_key_value("Type", type_name)

            ctx.start_group("Properties")

            if isinstance(obj, dict):
                for key, value in sorted(obj.items()):
                    ctx.append_key_value(str(key), self._format_value(value))
            else:
                for attr in sorted(dir(obj)):
                    if not include_private and attr.startswith("_"):
                        continue
                    try:
                        value = getattr(obj, attr)
                        if callable(value):
                            continue
                        ctx.append_key_value(attr, self._format_value(value))
                    except Exception as e:
                        ctx.append_key_value(attr, f"<error: {e}>")

            self._send_context(self.parent.default_level, title, LogEntryType.OBJECT, ctx)
        except Exception as e:
            self.log_internal_error(f"log_object: {e}")

    # ==================== Collection Logging ====================

    def log_array(self, title: str, arr: List[Any]) -> None:
        """Log an array/list."""
        if not self.is_on(self.parent.default_level):
            return

        if arr is None:
            self.log_internal_error("log_array: array argument is None")
            return

        ctx = ListViewerContext()
        for item in arr:
            ctx.append_line(self._format_value(item))
        self._send_context(self.parent.default_level, title, LogEntryType.TEXT, ctx)

    def log_dictionary(self, title: str, d: Dict[Any, Any]) -> None:
        """Log a dictionary as key-value pairs."""
        if not self.is_on(self.parent.default_level):
            return

        if d is None:
            self.log_internal_error("log_dictionary: dict argument is None")
            return

        ctx = ValueListViewerContext()
        for key, value in d.items():
            ctx.append_key_value(self._format_value(key), self._format_value(value))
        self._send_context(self.parent.default_level, title, LogEntryType.TEXT, ctx)

    def log_table(self, title: str, data: List[Dict[str, Any]], columns: Optional[List[str]] = None) -> None:
        """Log a table (list of dictionaries)."""
        if not self.is_on(self.parent.default_level):
            return

        if not data or not isinstance(data, list) or len(data) == 0:
            self.log_internal_error("log_table: data is empty or not a list")
            return

        ctx = TableViewerContext()

        # Determine columns
        if not columns:
            columns = list(data[0].keys()) if isinstance(data[0], dict) else ["Value"]

        # Header
        ctx.append_header(", ".join(f'"{c}"' for c in columns))

        # Rows
        for row in data:
            ctx.begin_row()
            if isinstance(row, dict):
                for col in columns:
                    ctx.add_row_entry(row.get(col, ""))
            else:
                ctx.add_row_entry(row)
            ctx.end_row()

        self._send_context(self.parent.default_level, title, LogEntryType.DATABASE_RESULT, ctx)

    # ==================== Text/Source Logging ====================

    def log_text(self, title: str, text: str) -> None:
        """Log plain text."""
        if not self.is_on(self.parent.default_level):
            return

        ctx = TextContext(ViewerId.DATA)
        ctx.load_from_text(text)
        self._send_context(self.parent.default_level, title, LogEntryType.TEXT, ctx)

    def log_source(self, title: str, source: str, source_id: int) -> None:
        """Log source code with syntax highlighting."""
        if not self.is_on(self.parent.default_level):
            return

        ctx = SourceViewerContext(source_id)
        ctx.load_from_text(source)
        self._send_context(self.parent.default_level, title, LogEntryType.SOURCE, ctx)

    def log_html(self, title: str, html: str) -> None:
        """Log HTML content."""
        self.log_source(title, html, SourceId.HTML)

    def log_javascript(self, title: str, code: str) -> None:
        """Log JavaScript source."""
        self.log_source(title, code, SourceId.JAVASCRIPT)

    def log_sql(self, title: str, sql: str) -> None:
        """Log SQL source."""
        self.log_source(title, sql, SourceId.SQL)

    def log_python(self, title: str, code: str) -> None:
        """Log Python source."""
        self.log_source(title, code, SourceId.PYTHON)

    def log_xml(self, title: str, xml: str) -> None:
        """Log XML source."""
        self.log_source(title, xml, SourceId.XML)

    def log_json(self, title: str, data: Union[str, Dict, List]) -> None:
        """Log JSON (pretty printed)."""
        if not self.is_on(self.parent.default_level):
            return

        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                pass

        if isinstance(data, (dict, list)):
            json_str = json.dumps(data, indent=2, default=str)
        else:
            json_str = str(data)

        self.log_source(title, json_str, SourceId.JAVASCRIPT)

    # ==================== Binary Logging ====================

    def log_binary(self, title: str, data: bytes) -> None:
        """Log binary data (hex dump)."""
        if not self.is_on(self.parent.default_level):
            return

        if data is None:
            self.log_internal_error("log_binary: data argument is None")
            return

        ctx = BinaryViewerContext()
        ctx.append_bytes(data)
        self._send_context(self.parent.default_level, title, LogEntryType.BINARY, ctx)

    # ==================== File Logging ====================

    def log_text_file(self, file_path: str, title: Optional[str] = None) -> None:
        """Log a text file."""
        if not self.is_on(self.parent.default_level):
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.log_text(title or os.path.basename(file_path), content)
        except Exception as e:
            self.log_internal_error(f"log_text_file: {e}")

    def log_binary_file(self, file_path: str, title: Optional[str] = None) -> None:
        """Log a binary file."""
        if not self.is_on(self.parent.default_level):
            return

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.log_binary(title or os.path.basename(file_path), content)
        except Exception as e:
            self.log_internal_error(f"log_binary_file: {e}")

    # ==================== Checkpoint/Counter ====================

    def add_checkpoint(self, name: Optional[str] = None, details: Optional[str] = None) -> None:
        """Add a checkpoint."""
        if not self.is_on(self.parent.default_level):
            return

        if name:
            count = self._checkpoints.get(name, 0) + 1
            self._checkpoints[name] = count
            title = f"{name} #{count}"
            if details:
                title += f" ({details})"
        else:
            self._checkpoint_counter += 1
            title = f"Checkpoint #{self._checkpoint_counter}"

        self._send_log_entry(self.parent.default_level, title, LogEntryType.CHECKPOINT, ViewerId.TITLE)

    def reset_checkpoint(self, name: Optional[str] = None) -> None:
        """Reset checkpoint counter."""
        if name:
            self._checkpoints.pop(name, None)
        else:
            self._checkpoint_counter = 0

    def inc_counter(self, name: str) -> None:
        """Increment a counter."""
        if not self.is_on(self.parent.default_level):
            return

        value = self._counters.get(name, 0) + 1
        self._counters[name] = value
        self._send_watch(self.parent.default_level, name, str(value), WatchType.INTEGER)

    def dec_counter(self, name: str) -> None:
        """Decrement a counter."""
        if not self.is_on(self.parent.default_level):
            return

        value = self._counters.get(name, 0) - 1
        self._counters[name] = value
        self._send_watch(self.parent.default_level, name, str(value), WatchType.INTEGER)

    def reset_counter(self, name: str) -> None:
        """Reset a counter."""
        self._counters.pop(name, None)

    # ==================== Watch Variables ====================

    def watch_string(self, name: str, value: str) -> None:
        """Watch a string value."""
        self._send_watch(self.parent.default_level, name, value, WatchType.STRING)

    def watch_int(self, name: str, value: int) -> None:
        """Watch an integer value."""
        self._send_watch(self.parent.default_level, name, str(value), WatchType.INTEGER)

    def watch_float(self, name: str, value: float) -> None:
        """Watch a float value."""
        self._send_watch(self.parent.default_level, name, str(value), WatchType.FLOAT)

    def watch_bool(self, name: str, value: bool) -> None:
        """Watch a boolean value."""
        self._send_watch(self.parent.default_level, name, "True" if value else "False", WatchType.BOOLEAN)

    def watch(self, name: str, value: Any) -> None:
        """Watch any value."""
        if isinstance(value, str):
            watch_type = WatchType.STRING
            str_value = value
        elif isinstance(value, bool):
            watch_type = WatchType.BOOLEAN
            str_value = "True" if value else "False"
        elif isinstance(value, int):
            watch_type = WatchType.INTEGER
            str_value = str(value)
        elif isinstance(value, float):
            watch_type = WatchType.FLOAT
            str_value = str(value)
        elif isinstance(value, datetime):
            watch_type = WatchType.TIMESTAMP
            str_value = value.isoformat()
        else:
            watch_type = WatchType.OBJECT
            str_value = self._format_value(value)

        self._send_watch(self.parent.default_level, name, str_value, watch_type)

    # ==================== Method Tracking ====================

    def enter_method(self, method_name: str) -> None:
        """Enter a method."""
        if not self.is_on(self.parent.default_level):
            return

        self._send_log_entry(self.parent.default_level, method_name, LogEntryType.ENTER_METHOD, ViewerId.TITLE)
        self._send_process_flow(self.parent.default_level, method_name, ProcessFlowType.ENTER_METHOD)

    def leave_method(self, method_name: str) -> None:
        """Leave a method."""
        if not self.is_on(self.parent.default_level):
            return

        self._send_log_entry(self.parent.default_level, method_name, LogEntryType.LEAVE_METHOD, ViewerId.TITLE)
        self._send_process_flow(self.parent.default_level, method_name, ProcessFlowType.LEAVE_METHOD)

    @contextmanager
    def track_method(self, method_name: str):
        """Context manager for tracking method execution."""
        self.enter_method(method_name)
        try:
            yield
        finally:
            self.leave_method(method_name)

    # ==================== Process/Thread Flow ====================

    def enter_process(self, process_name: Optional[str] = None) -> None:
        """Enter a process."""
        if not self.is_on(self.parent.default_level):
            return

        name = process_name or self.parent.app_name
        self._send_process_flow(self.parent.default_level, name, ProcessFlowType.ENTER_PROCESS)
        self._send_process_flow(self.parent.default_level, "Main Thread", ProcessFlowType.ENTER_THREAD)

    def leave_process(self, process_name: Optional[str] = None) -> None:
        """Leave a process."""
        if not self.is_on(self.parent.default_level):
            return

        name = process_name or self.parent.app_name
        self._send_process_flow(self.parent.default_level, "Main Thread", ProcessFlowType.LEAVE_THREAD)
        self._send_process_flow(self.parent.default_level, name, ProcessFlowType.LEAVE_PROCESS)

    def enter_thread(self, thread_name: str) -> None:
        """Enter a thread."""
        if not self.is_on(self.parent.default_level):
            return

        self._send_process_flow(self.parent.default_level, thread_name, ProcessFlowType.ENTER_THREAD)

    def leave_thread(self, thread_name: str) -> None:
        """Leave a thread."""
        if not self.is_on(self.parent.default_level):
            return

        self._send_process_flow(self.parent.default_level, thread_name, ProcessFlowType.LEAVE_THREAD)

    # ==================== Control Commands ====================

    def clear_all(self) -> None:
        """Clear all logs."""
        if self.is_on():
            self._send_control_command(ControlCommandType.CLEAR_ALL)

    def clear_log(self) -> None:
        """Clear the log view."""
        if self.is_on():
            self._send_control_command(ControlCommandType.CLEAR_LOG)

    def clear_watches(self) -> None:
        """Clear watches."""
        if self.is_on():
            self._send_control_command(ControlCommandType.CLEAR_WATCHES)

    def clear_auto_views(self) -> None:
        """Clear auto views."""
        if self.is_on():
            self._send_control_command(ControlCommandType.CLEAR_AUTO_VIEWS)

    def clear_process_flow(self) -> None:
        """Clear process flow."""
        if self.is_on():
            self._send_control_command(ControlCommandType.CLEAR_PROCESS_FLOW)

    # ==================== Stream Data ====================

    def log_stream(self, channel: str, data: Any, stream_type: Optional[str] = None) -> None:
        """
        Send stream data to a named channel.
        Streams are lightweight, high-frequency data channels for metrics, timeseries, etc.

        Args:
            channel: Channel name (e.g., 'metrics', 'cpu', 'memory')
            data: Data to send (will be JSON stringified if object)
            stream_type: Optional type identifier (e.g., 'json', 'text', 'metric')
        """
        if not self.is_on(self.parent.default_level):
            return

        if isinstance(data, str):
            data_str = data
        else:
            try:
                data_str = json.dumps(data, default=str)
            except Exception:
                data_str = str(data)

        packet = {
            "packet_type": PacketType.STREAM,
            "channel": channel,
            "data": data_str,
            "stream_type": stream_type or "",
            "timestamp": datetime.now(),
        }

        self.parent.send_packet(packet)

    # ==================== Assert ====================

    def log_assert(self, condition: bool, message: str) -> None:
        """Log an assertion."""
        if not self.is_on(Level.ERROR):
            return

        if not condition:
            self._send_log_entry(Level.ERROR, message, LogEntryType.ASSERT, ViewerId.TITLE)

    # ==================== Conditional Logging ====================

    def log_conditional(self, condition: bool, *args) -> None:
        """Log conditionally."""
        if not self.is_on(self.parent.default_level):
            return

        if condition:
            title = self._format_args(*args)
            self._send_log_entry(self.parent.default_level, title, LogEntryType.CONDITIONAL, ViewerId.TITLE)

    # ==================== System Info ====================

    def log_system(self, title: str = "System Information") -> None:
        """Log system information."""
        if not self.is_on(self.parent.default_level):
            return

        ctx = InspectorViewerContext()

        ctx.start_group("System")
        ctx.append_key_value("Platform", sys.platform)
        ctx.append_key_value("Architecture", platform.machine())
        ctx.append_key_value("OS", platform.system())
        ctx.append_key_value("OS Release", platform.release())
        ctx.append_key_value("Hostname", platform.node())

        ctx.start_group("Python")
        ctx.append_key_value("Version", platform.python_version())
        ctx.append_key_value("Implementation", platform.python_implementation())
        ctx.append_key_value("PID", os.getpid())
        ctx.append_key_value("CWD", os.getcwd())

        ctx.start_group("Memory")
        try:
            import psutil

            mem = psutil.Process().memory_info()
            ctx.append_key_value("RSS", f"{mem.rss // 1024 // 1024} MB")
            ctx.append_key_value("VMS", f"{mem.vms // 1024 // 1024} MB")
        except ImportError:
            ctx.append_key_value("Note", "Install psutil for memory info")

        ctx.start_group("CPU")
        ctx.append_key_value("Count", os.cpu_count() or "Unknown")
        ctx.append_key_value("Processor", platform.processor() or "Unknown")

        self._send_context(self.parent.default_level, title, LogEntryType.SYSTEM, ctx)

    def log_memory(self, title: str = "Memory Usage") -> None:
        """Log memory usage."""
        if not self.is_on(self.parent.default_level):
            return

        ctx = InspectorViewerContext()

        try:
            import psutil

            process = psutil.Process()
            mem = process.memory_info()

            ctx.start_group("Process Memory")
            ctx.append_key_value("RSS", f"{mem.rss // 1024 // 1024} MB")
            ctx.append_key_value("VMS", f"{mem.vms // 1024 // 1024} MB")

            ctx.start_group("System Memory")
            sys_mem = psutil.virtual_memory()
            ctx.append_key_value("Total", f"{sys_mem.total // 1024 // 1024} MB")
            ctx.append_key_value("Available", f"{sys_mem.available // 1024 // 1024} MB")
            ctx.append_key_value("Used", f"{sys_mem.used // 1024 // 1024} MB")
            ctx.append_key_value("Percent", f"{sys_mem.percent}%")
        except ImportError:
            ctx.start_group("Note")
            ctx.append_key_value("Info", "Install psutil for detailed memory info")

        self._send_context(self.parent.default_level, title, LogEntryType.MEMORY_STATISTIC, ctx)

    def log_stack_trace(self, title: str = "Current Stack Trace") -> None:
        """Log current stack trace."""
        if not self.is_on(self.parent.default_level):
            return

        stack = "".join(traceback.format_stack()[:-1])

        ctx = TextContext(ViewerId.DATA)
        ctx.load_from_text(stack)
        self._send_context(self.parent.default_level, title, LogEntryType.TEXT, ctx)

    def log_environment(self, title: str = "Environment Variables") -> None:
        """Log environment variables."""
        if not self.is_on(self.parent.default_level):
            return

        ctx = ValueListViewerContext()
        for key in sorted(os.environ.keys()):
            ctx.append_key_value(key, os.environ[key])

        self._send_context(self.parent.default_level, title, LogEntryType.TEXT, ctx)

    # ==================== Performance Timing ====================

    def time_start(self, name: str) -> None:
        """Start a timer."""
        self._timers[name] = time.perf_counter()
        self.log_message(f'Timer "{name}" started')

    def time_end(self, name: str) -> None:
        """End a timer and log the duration."""
        if name not in self._timers:
            self.log_warning(f'Timer "{name}" not found')
            return

        start = self._timers.pop(name)
        duration_ms = (time.perf_counter() - start) * 1000

        self.watch_float(name, duration_ms)
        self.log_message(f'Timer "{name}": {duration_ms:.3f}ms')

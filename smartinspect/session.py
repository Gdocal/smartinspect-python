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
from decimal import Decimal
from datetime import datetime
from contextlib import contextmanager
from typing import Optional, Any, Dict, List, Union

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
    parse_color,
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
from .context_api import SiContext, AsyncContext


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

    @staticmethod
    def _is_level_value(value: Any) -> bool:
        return isinstance(value, (int, Level))

    def _parse_level_and_args(self, args: tuple, default_level: int) -> tuple:
        """
        Parse optional leading level argument (C# overload style).
        Returns (level, remaining_args_tuple).
        """
        if args and self._is_level_value(args[0]):
            return int(args[0]), tuple(args[1:])
        return int(default_level), args

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
        inline_context: Optional[Any] = None,
    ) -> None:
        """Send a log entry packet."""
        if not self.is_on(level):
            return

        ctx = SiContext.get_merged_context(inline_context)
        correlation_id = None
        operation_name = None
        operation_depth = AsyncContext.operation_depth()
        if ctx:
            correlation_id = ctx.get("_traceId")
            operation_name = ctx.get("_spanName")

        if correlation_id is None:
            correlation_id = AsyncContext.correlation_id()
        if operation_name is None:
            operation_name = AsyncContext.operation_name()

        packet = {
            "packet_type": PacketType.LOG_ENTRY,
            "level": level,
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
            "correlation_id": correlation_id,
            "operation_name": operation_name,
            "operation_depth": operation_depth,
            "ctx": ctx,
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
        group: str = "",
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """Send a watch packet."""
        if not self.is_on(level):
            return

        packet = {
            "packet_type": PacketType.WATCH,
            "level": level,
            "name": name,
            "value": value,
            "watch_type": watch_type,
            "timestamp": datetime.now(),
            "group": group,
            "labels": labels,
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
            "level": level,
            "process_flow_type": process_flow_type,
            "title": title,
            "host_name": self.parent.host_name,
            "process_id": self._get_process_id(),
            "thread_id": self._get_thread_id(),
            "timestamp": datetime.now(),
            "correlation_id": AsyncContext.correlation_id(),
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
            "level": Level.CONTROL,
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

    def log_message_ctx(self, title: str, context: Any) -> None:
        """Log message with inline context tags."""
        self._send_log_entry(
            Level.MESSAGE,
            title,
            LogEntryType.MESSAGE,
            ViewerId.TITLE,
            inline_context=context,
        )

    def log_warning_ctx(self, title: str, context: Any) -> None:
        """Log warning with inline context tags."""
        self._send_log_entry(
            Level.WARNING,
            title,
            LogEntryType.WARNING,
            ViewerId.TITLE,
            inline_context=context,
        )

    def log_error_ctx(self, title: str, context: Any) -> None:
        """Log error with inline context tags."""
        self._send_log_entry(
            Level.ERROR,
            title,
            LogEntryType.ERROR,
            ViewerId.TITLE,
            inline_context=context,
        )

    def log_debug_ctx(self, title: str, context: Any) -> None:
        """Log debug message with inline context tags."""
        self._send_log_entry(
            Level.DEBUG,
            title,
            LogEntryType.DEBUG,
            ViewerId.TITLE,
            inline_context=context,
        )

    def log_verbose_ctx(self, title: str, context: Any) -> None:
        """Log verbose message with inline context tags."""
        self._send_log_entry(
            Level.VERBOSE,
            title,
            LogEntryType.VERBOSE,
            ViewerId.TITLE,
            inline_context=context,
        )

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

    def log_separator(self, *args) -> None:
        """Log a separator (supports optional leading level)."""
        level, rem = self._parse_level_and_args(args, self.parent.default_level)
        if rem:
            raise TypeError("log_separator() expects () or (level)")
        self._send_log_entry(level, "", LogEntryType.SEPARATOR, ViewerId.TITLE)

    # ==================== Colored Logging ====================

    def log_colored(self, *args) -> None:
        """
        Log a colored message.

        Supports:
        - (color, *message_args)
        - (level, color, *message_args)

        Color can be: hex string '#FF6432', tuple (255,100,50), Color object, or dict.
        """
        if args and self._is_level_value(args[0]) and len(args) >= 2:
            level = int(args[0])
            rem = args[1:]
        else:
            level = int(self.parent.default_level)
            rem = args

        if not rem:
            raise TypeError("log_colored() expects (color, *args) or (level, color, *args)")

        color = rem[0]
        parsed_color = parse_color(color)
        title = self._format_args(*rem[1:])
        self._send_log_entry(level, title, LogEntryType.MESSAGE, ViewerId.TITLE, parsed_color)

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

    def log_string(self, *args) -> None:
        """Log a string variable. Supports C#-style overload with optional level."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 2:
            raise TypeError("log_string() expects (name, value) or (level, name, value)")
        name, value = args
        title = f'{name} = "{value}"'
        self._send_log_entry(level, title, LogEntryType.VARIABLE_VALUE, ViewerId.TITLE)

    def log_int(self, *args) -> None:
        """Log an integer variable. Supports optional level/include_hex overloads."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) not in (2, 3):
            raise TypeError(
                "log_int() expects (name, value[, include_hex]) or (level, name, value[, include_hex])"
            )
        name = args[0]
        value = int(args[1])
        include_hex = bool(args[2]) if len(args) == 3 else False
        title = f"{name} = {value}"
        if include_hex:
            title += f" (0x{value:08x})"
        self._send_log_entry(level, title, LogEntryType.VARIABLE_VALUE, ViewerId.TITLE)

    def log_number(self, *args) -> None:
        """Log a numeric variable. Supports optional level overload."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 2:
            raise TypeError("log_number() expects (name, value) or (level, name, value)")
        name, value = args
        title = f"{name} = {value}"
        self._send_log_entry(level, title, LogEntryType.VARIABLE_VALUE, ViewerId.TITLE)

    def log_bool(self, *args) -> None:
        """Log a boolean variable. Supports optional level overload."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 2:
            raise TypeError("log_bool() expects (name, value) or (level, name, value)")
        name, value = args
        title = f"{name} = {'True' if value else 'False'}"
        self._send_log_entry(level, title, LogEntryType.VARIABLE_VALUE, ViewerId.TITLE)

    def log_datetime(self, *args) -> None:
        """Log a date/time value. Supports optional level overload."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 2:
            raise TypeError("log_datetime() expects (name, value) or (level, name, value)")
        name, value = args
        if not isinstance(value, datetime):
            raise TypeError("log_datetime() value must be datetime")
        title = f"{name} = {value.isoformat()}"
        self._send_log_entry(level, title, LogEntryType.VARIABLE_VALUE, ViewerId.TITLE)

    def log_date_time(self, *args) -> None:
        """C# alias for log_datetime()."""
        self.log_datetime(*args)

    def log_value(self, *args) -> None:
        """Log any value with its type. Supports optional level overload."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 2:
            raise TypeError("log_value() expects (name, value) or (level, name, value)")
        name, value = args
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
        self._send_log_entry(level, title, LogEntryType.VARIABLE_VALUE, ViewerId.TITLE)

    def log_decimal(self, *args) -> None:
        """C# decimal overload parity."""
        self.log_number(*args)

    def log_double(self, *args) -> None:
        """C# double overload parity."""
        self.log_number(*args)

    def log_float(self, *args) -> None:
        """C# float overload parity."""
        self.log_number(*args)

    def log_long(self, *args) -> None:
        """C# long overload parity with optional include_hex support."""
        self.log_int(*args)

    def log_short(self, *args) -> None:
        """C# short overload parity with optional include_hex support."""
        self.log_int(*args)

    def log_byte(self, *args) -> None:
        """C# byte overload parity with optional include_hex support."""
        self.log_int(*args)

    def log_char(self, *args) -> None:
        """C# char overload parity."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 2:
            raise TypeError("log_char() expects (name, value) or (level, name, value)")
        name, value = args
        text = value if isinstance(value, str) else chr(int(value))
        title = f"{name} = '{text}'"
        self._send_log_entry(level, title, LogEntryType.VARIABLE_VALUE, ViewerId.TITLE)

    # ==================== Object Logging ====================

    def _format_title_with_values(self, title_fmt: Any, values: Any) -> str:
        """Format title using C#-style format arguments when possible."""
        title_fmt = str(title_fmt)
        if isinstance(values, (list, tuple)):
            try:
                return title_fmt.format(*values)
            except Exception:
                return f"{title_fmt} {values}"
        return f"{title_fmt} {values}"

    @staticmethod
    def _normalize_tabular_data(value: Any) -> List[Dict[str, Any]]:
        """Best-effort conversion of many table-like objects to list[dict]."""
        if value is None:
            return []

        if isinstance(value, list):
            if not value:
                return []
            if isinstance(value[0], dict):
                return [dict(row) for row in value]
            return [{"Value": row} for row in value]

        if isinstance(value, tuple):
            return [{"Value": row} for row in value]

        if isinstance(value, dict):
            return [{str(k): v for k, v in value.items()}]

        to_dict = getattr(value, "to_dict", None)
        if callable(to_dict):
            try:
                records = to_dict(orient="records")
                if isinstance(records, list):
                    return [dict(r) if isinstance(r, dict) else {"Value": r} for r in records]
            except Exception:
                pass

        rows = getattr(value, "rows", None)
        columns = getattr(value, "columns", None)
        if rows is not None and columns is not None:
            try:
                col_names = [str(c) for c in columns]
                out = []
                for row in rows:
                    out.append({col_names[i]: row[i] if i < len(row) else "" for i in range(len(col_names))})
                return out
            except Exception:
                pass

        return [{"Value": str(value)}]

    def _resolve_file_args(self, args: tuple, method_name: str) -> tuple:
        """Parse file args from either (file) / (title,file) or (file,title)."""
        if len(args) == 1:
            file_path = str(args[0])
            title = os.path.basename(file_path)
            return title, file_path

        if len(args) != 2:
            raise TypeError(f"{method_name}() expects (file_name) or (title, file_name)")

        first, second = str(args[0]), str(args[1])
        first_exists = os.path.exists(first)
        second_exists = os.path.exists(second)

        if first_exists and not second_exists:
            return second, first
        if second_exists and not first_exists:
            return first, second
        return first, second

    def log_object(self, *args, **kwargs) -> None:
        """Log an object with its properties (supports C# overloads)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        include_private = kwargs.pop("include_private", kwargs.pop("non_public", False))
        if kwargs:
            raise TypeError(f"Unexpected keyword arguments: {', '.join(kwargs.keys())}")

        if len(args) == 2:
            title, obj = args
        elif len(args) == 3:
            title, obj, include_private = args
        else:
            raise TypeError(
                "log_object() expects (title, object[, include_private]) or "
                "(level, title, object[, include_private])"
            )

        if not self.is_on(level):
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
                    if not include_private and str(attr).startswith("_"):
                        continue
                    try:
                        value = getattr(obj, attr)
                        if callable(value):
                            continue
                        ctx.append_key_value(str(attr), self._format_value(value))
                    except Exception as e:
                        ctx.append_key_value(str(attr), f"<error: {e}>")

            self._send_context(level, str(title), LogEntryType.OBJECT, ctx)
        except Exception as e:
            self.log_internal_error(f"log_object: {e}")

    def log_assigned(self, *args) -> None:
        """C# alias for object logging."""
        self.log_object(*args)

    # ==================== Collection Logging ====================

    def log_array(self, *args) -> None:
        """Log an array/list (supports C# overloads)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 2:
            raise TypeError("log_array() expects (title, array) or (level, title, array)")

        title, arr = args
        if not self.is_on(level):
            return

        if arr is None:
            self.log_internal_error("log_array: array argument is None")
            return

        ctx = ListViewerContext()
        for item in arr:
            ctx.append_line(self._format_value(item))
        self._send_context(level, str(title), LogEntryType.TEXT, ctx)

    def log_collection(self, *args) -> None:
        """C# parity collection logger."""
        self.log_array(*args)

    def log_enumerable(self, *args) -> None:
        """C# parity enumerable logger."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 2:
            raise TypeError("log_enumerable() expects (title, enumerable) or (level, title, enumerable)")
        title, enumerable = args
        self.log_array(level, title, list(enumerable) if enumerable is not None else [])

    def log_dictionary(self, *args) -> None:
        """Log a dictionary as key-value pairs (supports C# overloads)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 2:
            raise TypeError("log_dictionary() expects (title, dict) or (level, title, dict)")

        title, d = args
        if not self.is_on(level):
            return

        if d is None:
            self.log_internal_error("log_dictionary: dict argument is None")
            return

        ctx = ValueListViewerContext()
        for key, value in d.items():
            ctx.append_key_value(self._format_value(key), self._format_value(value))
        self._send_context(level, str(title), LogEntryType.TEXT, ctx)

    def log_table(self, *args) -> None:
        """Log a table (list of dictionaries), with optional leading level."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) not in (2, 3):
            raise TypeError("log_table() expects (title, data[, columns]) or (level, title, data[, columns])")

        title = args[0]
        data = args[1]
        columns = args[2] if len(args) == 3 else None

        if not self.is_on(level):
            return

        if not data or not isinstance(data, list) or len(data) == 0:
            self.log_internal_error("log_table: data is empty or not a list")
            return

        ctx = TableViewerContext()

        if not columns:
            columns = list(data[0].keys()) if isinstance(data[0], dict) else ["Value"]

        ctx.append_header(", ".join(f'"{c}"' for c in columns))

        for row in data:
            ctx.begin_row()
            if isinstance(row, dict):
                for col in columns:
                    ctx.add_row_entry(row.get(col, ""))
            else:
                ctx.add_row_entry(row)
            ctx.end_row()

        self._send_context(level, str(title), LogEntryType.DATABASE_RESULT, ctx)

    def log_data_table(self, *args) -> None:
        """C# parity logger for DataTable-like objects."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) == 1:
            table = args[0]
            title = getattr(table, "name", "DataTable")
        elif len(args) == 2:
            title, table = args
        else:
            raise TypeError("log_data_table() expects (table) or (title, table) or leading level")

        rows = self._normalize_tabular_data(table)
        self.log_table(level, str(title), rows)

    def log_data_view(self, *args) -> None:
        """C# parity logger for DataView-like objects."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) == 1:
            data_view = args[0]
            title = getattr(data_view, "name", "DataView")
        elif len(args) == 2:
            title, data_view = args
        else:
            raise TypeError("log_data_view() expects (data_view) or (title, data_view) or leading level")

        rows = self._normalize_tabular_data(data_view)
        self.log_table(level, str(title), rows)

    def log_data_table_schema(self, *args) -> None:
        """C# parity logger for DataTable schema."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) == 1:
            table = args[0]
            title = f"{getattr(table, 'name', 'DataTable')} schema"
        elif len(args) == 2:
            title, table = args
        else:
            raise TypeError(
                "log_data_table_schema() expects (table) or (title, table) or leading level"
            )

        columns = getattr(table, "columns", None)
        schema_rows: List[Dict[str, Any]] = []
        if columns is not None:
            try:
                for col in columns:
                    schema_rows.append({"Column": str(col), "Type": type(col).__name__})
            except Exception:
                schema_rows = [{"Schema": str(columns)}]
        else:
            schema_rows = [{"Schema": str(table)}]

        self.log_table(level, str(title), schema_rows)

    def log_data_set(self, *args) -> None:
        """C# parity logger for DataSet-like objects."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 1:
            raise TypeError("log_data_set() expects (data_set) or (level, data_set)")

        data_set = args[0]
        title = getattr(data_set, "name", "DataSet")
        ctx = InspectorViewerContext()
        ctx.start_group("General")
        ctx.append_key_value("Type", type(data_set).__name__)

        tables = getattr(data_set, "tables", None)
        if tables is not None:
            ctx.start_group("Tables")
            try:
                for table in tables:
                    table_name = getattr(table, "name", type(table).__name__)
                    row_count = getattr(table, "row_count", None)
                    if row_count is None:
                        rows = getattr(table, "rows", None)
                        row_count = len(rows) if rows is not None else "Unknown"
                    ctx.append_key_value(str(table_name), str(row_count))
            except Exception:
                ctx.append_key_value("Value", str(tables))
        else:
            ctx.start_group("Value")
            ctx.append_key_value("Data", str(data_set))

        self._send_context(level, str(title), LogEntryType.DATABASE_RESULT, ctx)

    def log_data_set_schema(self, *args) -> None:
        """C# parity logger for DataSet schema."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 1:
            raise TypeError("log_data_set_schema() expects (data_set) or (level, data_set)")

        data_set = args[0]
        title = f"{getattr(data_set, 'name', 'DataSet')} schema"
        ctx = InspectorViewerContext()
        ctx.start_group("General")
        ctx.append_key_value("Type", type(data_set).__name__)

        tables = getattr(data_set, "tables", None)
        if tables is not None:
            for table in tables:
                table_name = getattr(table, "name", type(table).__name__)
                ctx.start_group(str(table_name))
                columns = getattr(table, "columns", None)
                if columns is None:
                    ctx.append_key_value("Columns", "Unknown")
                else:
                    try:
                        for col in columns:
                            ctx.append_key_value(str(col), type(col).__name__)
                    except Exception:
                        ctx.append_key_value("Columns", str(columns))

        self._send_context(level, str(title), LogEntryType.DATABASE_STRUCTURE, ctx)

    # ==================== Text/Source Logging ====================

    def log_text(self, *args) -> None:
        """Log plain text (supports C# overloads)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 2:
            raise TypeError("log_text() expects (title, text) or (level, title, text)")

        title, text = args
        if not self.is_on(level):
            return

        ctx = TextContext(ViewerId.DATA)
        ctx.load_from_text(str(text))
        self._send_context(level, str(title), LogEntryType.TEXT, ctx)

    def log_string_builder(self, *args) -> None:
        """C# parity for StringBuilder logging."""
        self.log_text(*args)

    def log_source(self, *args) -> None:
        """Log source code with syntax highlighting (supports C# overloads)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 3:
            raise TypeError("log_source() expects (title, source, source_id) or (level, title, source, source_id)")

        title, source, source_id = args
        if not self.is_on(level):
            return

        ctx = SourceViewerContext(int(source_id))
        ctx.load_from_text(str(source))
        self._send_context(level, str(title), LogEntryType.SOURCE, ctx)

    def log_html(self, *args) -> None:
        """Log HTML content (supports optional leading level)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 2:
            raise TypeError("log_html() expects (title, html) or (level, title, html)")
        title, html = args
        self.log_source(level, title, html, SourceId.HTML)

    def log_javascript(self, title: str, code: str) -> None:
        """Log JavaScript source."""
        self.log_source(title, code, SourceId.JAVASCRIPT)

    def log_sql(self, *args) -> None:
        """Log SQL source (supports optional leading level)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 2:
            raise TypeError("log_sql() expects (title, sql) or (level, title, sql)")
        title, sql = args
        self.log_source(level, title, sql, SourceId.SQL)

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

    def log_binary(self, *args) -> None:
        """Log binary data (hex dump), supports C# offset/count overloads."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) not in (2, 4):
            raise TypeError(
                "log_binary() expects (title, data) or (title, data, offset, count) "
                "with optional leading level"
            )

        title = args[0]
        buffer = args[1]

        if buffer is None:
            self.log_internal_error("log_binary: data argument is None")
            return

        if isinstance(buffer, str):
            data = buffer.encode("utf-8")
        elif isinstance(buffer, bytearray):
            data = bytes(buffer)
        elif isinstance(buffer, bytes):
            data = buffer
        else:
            try:
                data = bytes(buffer)
            except Exception:
                data = str(buffer).encode("utf-8", errors="replace")

        if len(args) == 4:
            offset = int(args[2])
            count = int(args[3])
            if offset < 0:
                offset = 0
            if count < 0:
                count = 0
            data = data[offset : offset + count]

        if not self.is_on(level):
            return

        ctx = BinaryViewerContext()
        ctx.append_bytes(data)
        self._send_context(level, str(title), LogEntryType.BINARY, ctx)

    def _as_binary_bytes(self, value: Any) -> bytes:
        """Best-effort conversion for image/icon payloads."""
        if value is None:
            return b""
        if isinstance(value, bytes):
            return value
        if isinstance(value, bytearray):
            return bytes(value)
        if isinstance(value, str):
            return value.encode("utf-8", errors="replace")

        save = getattr(value, "save", None)
        if callable(save):
            try:
                from io import BytesIO

                bio = BytesIO()
                save(bio)
                return bio.getvalue()
            except Exception:
                pass

        read = getattr(value, "read", None)
        if callable(read):
            try:
                data = read()
                if isinstance(data, str):
                    return data.encode("utf-8", errors="replace")
                return bytes(data)
            except Exception:
                pass

        return str(value).encode("utf-8", errors="replace")

    def log_bitmap(self, *args) -> None:
        """C# parity bitmap logging."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 2:
            raise TypeError("log_bitmap() expects (title, bitmap) or (level, title, bitmap)")
        title, bitmap = args
        self.log_binary(level, title, self._as_binary_bytes(bitmap))

    def log_icon(self, *args) -> None:
        """C# parity icon logging."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 2:
            raise TypeError("log_icon() expects (title, icon) or (level, title, icon)")
        title, icon = args
        self.log_binary(level, title, self._as_binary_bytes(icon))

    # ==================== File Logging ====================

    def log_text_file(self, *args) -> None:
        """Log a text file (supports C# overloads)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        title, file_path = self._resolve_file_args(args, "log_text_file")

        if not self.is_on(level):
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.log_text(level, title, content)
        except Exception as e:
            self.log_internal_error(f"log_text_file: {e}")

    def log_binary_file(self, *args) -> None:
        """Log a binary file (supports C# overloads)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        title, file_path = self._resolve_file_args(args, "log_binary_file")

        if not self.is_on(level):
            return

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.log_binary(level, title, content)
        except Exception as e:
            self.log_internal_error(f"log_binary_file: {e}")

    def log_bitmap_file(self, *args) -> None:
        """C# parity bitmap file logger."""
        self.log_binary_file(*args)

    def log_icon_file(self, *args) -> None:
        """C# parity icon file logger."""
        self.log_binary_file(*args)

    def log_jpeg_file(self, *args) -> None:
        """C# parity jpeg file logger."""
        self.log_binary_file(*args)

    def log_metafile_file(self, *args) -> None:
        """C# parity metafile logger."""
        self.log_binary_file(*args)

    def log_bitmap_stream(self, *args) -> None:
        """C# parity bitmap stream logger."""
        self.log_binary_stream(*args)

    def log_icon_stream(self, *args) -> None:
        """C# parity icon stream logger."""
        self.log_binary_stream(*args)

    def log_jpeg_stream(self, *args) -> None:
        """C# parity jpeg stream logger."""
        self.log_binary_stream(*args)

    def log_metafile_stream(self, *args) -> None:
        """C# parity metafile stream logger."""
        self.log_binary_stream(*args)

    # ==================== Checkpoint/Counter ====================

    def add_checkpoint(self, *args) -> None:
        """Add a checkpoint (supports C# overloads)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) > 2:
            raise TypeError(
                "add_checkpoint() expects (), (name), (name, details) with optional leading level"
            )

        name = args[0] if len(args) >= 1 else None
        details = args[1] if len(args) == 2 else None

        if not self.is_on(level):
            return

        if name:
            count = self._checkpoints.get(str(name), 0) + 1
            self._checkpoints[str(name)] = count
            title = f"{name} #{count}"
            if details:
                title += f" ({details})"
        else:
            self._checkpoint_counter += 1
            title = f"Checkpoint #{self._checkpoint_counter}"

        self._send_log_entry(level, title, LogEntryType.CHECKPOINT, ViewerId.TITLE)

    def reset_checkpoint(self, name: Optional[str] = None) -> None:
        """Reset checkpoint counter."""
        if name:
            self._checkpoints.pop(name, None)
        else:
            self._checkpoint_counter = 0

    def inc_counter(self, *args) -> None:
        """Increment a counter (supports optional leading level)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 1:
            raise TypeError("inc_counter() expects (name) or (level, name)")

        name = str(args[0])
        if not self.is_on(level):
            return

        value = self._counters.get(name, 0) + 1
        self._counters[name] = value
        self._send_watch(level, name, str(value), WatchType.INTEGER)

    def dec_counter(self, *args) -> None:
        """Decrement a counter (supports optional leading level)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 1:
            raise TypeError("dec_counter() expects (name) or (level, name)")

        name = str(args[0])
        if not self.is_on(level):
            return

        value = self._counters.get(name, 0) - 1
        self._counters[name] = value
        self._send_watch(level, name, str(value), WatchType.INTEGER)

    def reset_counter(self, name: str) -> None:
        """Reset a counter."""
        self._counters.pop(name, None)

    # ==================== Watch Variables ====================

    def watch_string(self, *args) -> None:
        """Watch a string value (supports C# overloads)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) not in (2, 3):
            raise TypeError("watch_string() expects (name, value[, group]) with optional leading level")
        name, value = args[0], args[1]
        group = args[2] if len(args) == 3 else ""
        self._send_watch(level, str(name), str(value), WatchType.STRING, str(group))

    def watch_int(self, *args) -> None:
        """Watch an integer value (supports include_hex/group overloads)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) not in (2, 3, 4):
            raise TypeError(
                "watch_int() expects (name, value[, group|include_hex[, group]]) with optional leading level"
            )

        name = str(args[0])
        value = int(args[1])
        include_hex = False
        group = ""

        if len(args) == 3:
            if isinstance(args[2], bool):
                include_hex = bool(args[2])
            else:
                group = str(args[2])
        elif len(args) == 4:
            include_hex = bool(args[2])
            group = str(args[3])

        text = str(value)
        if include_hex:
            text = f"{text} (0x{value:08x})"

        self._send_watch(level, name, text, WatchType.INTEGER, group)

    def watch_float(self, *args) -> None:
        """Watch a float value (supports optional leading level)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) not in (2, 3):
            raise TypeError("watch_float() expects (name, value[, group]) with optional leading level")
        name, value = args[0], args[1]
        group = args[2] if len(args) == 3 else ""
        self._send_watch(level, str(name), str(value), WatchType.FLOAT, str(group))

    def watch_bool(self, *args) -> None:
        """Watch a boolean value (supports optional leading level)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) not in (2, 3):
            raise TypeError("watch_bool() expects (name, value[, group]) with optional leading level")
        name, value = args[0], args[1]
        group = args[2] if len(args) == 3 else ""
        self._send_watch(level, str(name), "True" if value else "False", WatchType.BOOLEAN, str(group))

    def watch(self, *args) -> None:
        """Watch any value (supports optional leading level)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) not in (2, 3):
            raise TypeError("watch() expects (name, value[, group]) with optional leading level")

        name, value = args[0], args[1]
        group = args[2] if len(args) == 3 else ""

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

        self._send_watch(level, str(name), str_value, watch_type, str(group))

    def watch_with_labels(
        self,
        name: str,
        value: Any,
        labels: Dict[str, str],
        level: Optional[int] = None,
    ) -> None:
        """Watch value with Prometheus-style labels."""
        use_level = self.parent.default_level if level is None else int(level)
        if not isinstance(labels, dict):
            labels = {}

        if isinstance(value, bool):
            watch_type = WatchType.BOOLEAN
            str_value = "true" if value else "false"
        elif isinstance(value, int) and not isinstance(value, bool):
            watch_type = WatchType.INTEGER
            str_value = str(value)
        elif isinstance(value, (float, Decimal)):
            watch_type = WatchType.FLOAT
            str_value = str(value)
        elif isinstance(value, datetime):
            watch_type = WatchType.TIMESTAMP
            str_value = value.isoformat()
        else:
            watch_type = WatchType.STRING
            str_value = str(value)

        self._send_watch(use_level, name, str_value, watch_type, labels=labels)

    def metric(self, name: str) -> "MetricBuilder":
        """Create a fluent metric builder."""
        return MetricBuilder(self, name)

    # ==================== Method Tracking ====================

    def _resolve_method_name(self, args: tuple, method_name: str) -> str:
        if len(args) == 1:
            return str(args[0])

        if len(args) == 2:
            first, second = args
            if isinstance(second, (list, tuple)):
                return self._format_title_with_values(first, second)
            return f"{type(first).__name__}.{second}"

        if len(args) == 3:
            instance, title_fmt, values = args
            title = self._format_title_with_values(title_fmt, values)
            return f"{type(instance).__name__}.{title}"

        raise TypeError(
            f"{method_name}() expects (method), (instance, method), (fmt, args) or "
            "(instance, fmt, args) with optional leading level"
        )

    def enter_method(self, *args) -> None:
        """Enter a method (supports C# overloads)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        method_name = self._resolve_method_name(args, "enter_method")

        if not self.is_on(level):
            return

        self._send_log_entry(level, method_name, LogEntryType.ENTER_METHOD, ViewerId.TITLE)
        self._send_process_flow(level, method_name, ProcessFlowType.ENTER_METHOD)

    def leave_method(self, *args) -> None:
        """Leave a method (supports C# overloads)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        method_name = self._resolve_method_name(args, "leave_method")

        if not self.is_on(level):
            return

        self._send_log_entry(level, method_name, LogEntryType.LEAVE_METHOD, ViewerId.TITLE)
        self._send_process_flow(level, method_name, ProcessFlowType.LEAVE_METHOD)

    @contextmanager
    def track_method(self, *args):
        """Context manager for tracking method execution (supports C# overloads)."""
        level, rem = self._parse_level_and_args(args, self.parent.default_level)
        method_name = self._resolve_method_name(rem, "track_method")
        self.enter_method(level, method_name)
        try:
            yield
        finally:
            self.leave_method(level, method_name)

    # ==================== Process/Thread Flow ====================

    def _resolve_flow_name(self, args: tuple, default_name: str, method_name: str) -> str:
        if len(args) == 0:
            return default_name
        if len(args) == 1:
            return str(args[0])
        if len(args) == 2:
            return self._format_title_with_values(args[0], args[1])
        raise TypeError(
            f"{method_name}() expects (), (name), or (name_fmt, args) with optional leading level"
        )

    def enter_process(self, *args) -> None:
        """Enter a process (supports C# overloads)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        name = self._resolve_flow_name(args, self.parent.app_name, "enter_process")

        if not self.is_on(level):
            return

        self._send_process_flow(level, name, ProcessFlowType.ENTER_PROCESS)
        self._send_process_flow(level, "Main Thread", ProcessFlowType.ENTER_THREAD)

    def leave_process(self, *args) -> None:
        """Leave a process (supports C# overloads)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        name = self._resolve_flow_name(args, self.parent.app_name, "leave_process")

        if not self.is_on(level):
            return

        self._send_process_flow(level, "Main Thread", ProcessFlowType.LEAVE_THREAD)
        self._send_process_flow(level, name, ProcessFlowType.LEAVE_PROCESS)

    def enter_thread(self, *args) -> None:
        """Enter a thread (supports C# overloads)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        name = self._resolve_flow_name(args, "Main Thread", "enter_thread")

        if not self.is_on(level):
            return

        self._send_process_flow(level, name, ProcessFlowType.ENTER_THREAD)

    def leave_thread(self, *args) -> None:
        """Leave a thread (supports C# overloads)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        name = self._resolve_flow_name(args, "Main Thread", "leave_thread")

        if not self.is_on(level):
            return

        self._send_process_flow(level, name, ProcessFlowType.LEAVE_THREAD)

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

    def log_stream(self, *args, **kwargs) -> None:
        """
        Send stream data to a named channel.
        Streams are lightweight, high-frequency data channels for metrics, timeseries, etc.

        Args:
            level: Optional log level as first positional arg or keyword
            channel: Channel name (e.g., 'metrics', 'cpu', 'memory')
            data: Data to send (will be JSON stringified if object)
            stream_type: Optional type identifier (e.g., 'json', 'text', 'metric')
            group: Optional group for organizing stream channels
        """
        level = kwargs.pop("level", self.parent.default_level)
        stream_type = kwargs.pop("stream_type", "")
        group = kwargs.pop("group", "")
        channel = kwargs.pop("channel", None)
        data = kwargs.pop("data", None)

        if kwargs:
            raise TypeError(f"Unexpected keyword arguments: {', '.join(kwargs.keys())}")

        pos = list(args)
        if pos and isinstance(pos[0], (int, Level)):
            level = int(pos.pop(0))
        else:
            level = int(level)

        if channel is None and pos:
            channel = pos.pop(0)
        if data is None and pos:
            data = pos.pop(0)
        if pos:
            stream_type = pos.pop(0)
        if pos:
            group = pos.pop(0)
        if pos:
            raise TypeError("Too many positional arguments for log_stream")

        if channel is None:
            raise TypeError("log_stream() missing required argument: 'channel'")
        if data is None:
            raise TypeError("log_stream() missing required argument: 'data'")

        if not self.is_on(level):
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
            "level": level,
            "channel": channel,
            "data": data_str,
            "stream_type": stream_type,
            "group": group,
            "timestamp": datetime.now(),
        }

        self.parent.send_packet(packet)

    # ==================== Assert ====================

    def log_assert(self, condition: bool, *args) -> None:
        """Log an assertion (supports title format overload)."""
        if not self.is_on(Level.ERROR):
            return

        if len(args) == 0:
            raise TypeError("log_assert() expects condition and title")
        if len(args) == 1:
            message = str(args[0])
        elif len(args) == 2 and isinstance(args[1], (list, tuple)):
            message = self._format_title_with_values(args[0], args[1])
        else:
            try:
                message = str(args[0]).format(*args[1:])
            except Exception:
                message = self._format_args(*args)

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

    def log_system(self, *args) -> None:
        """Log system information (supports optional leading level/title)."""
        level, rem = self._parse_level_and_args(args, self.parent.default_level)
        if len(rem) > 1:
            raise TypeError("log_system() expects (), (title), (level), or (level, title)")
        title = str(rem[0]) if rem else "System Information"

        if not self.is_on(level):
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

        self._send_context(level, title, LogEntryType.SYSTEM, ctx)

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

    def log_stack_trace(self, *args) -> None:
        """Log stack trace (supports optional leading level and explicit trace object)."""
        level, rem = self._parse_level_and_args(args, self.parent.default_level)

        if len(rem) == 0:
            title = "Current Stack Trace"
            stack_text = "".join(traceback.format_stack()[:-1])
        elif len(rem) == 1:
            title = str(rem[0])
            stack_text = "".join(traceback.format_stack()[:-1])
        elif len(rem) == 2:
            title = str(rem[0])
            stack_text = str(rem[1])
        else:
            raise TypeError(
                "log_stack_trace() expects (), (title), (level, title), or (title, stack_trace) with optional level"
            )

        if not self.is_on(level):
            return

        ctx = TextContext(ViewerId.DATA)
        ctx.load_from_text(stack_text)
        self._send_context(level, title, LogEntryType.TEXT, ctx)

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


    # ==================== C# Parity Helpers ====================

    def reset_callstack(self, *args) -> None:
        """Reset call stack (C# parity)."""
        level, _ = self._parse_level_and_args(args, self.parent.default_level)
        self._send_log_entry(level, "", LogEntryType.RESET_CALLSTACK, ViewerId.TITLE)

    def reset_color(self) -> None:
        """Reset session color to default."""
        self.color = DEFAULT_COLOR

    def log_object_value(self, *args) -> None:
        """C# alias for variable/object value logging."""
        self.log_value(*args)

    def watch_byte(self, *args) -> None:
        self.watch_int(*args)

    def watch_short(self, *args) -> None:
        self.watch_int(*args)

    def watch_long(self, *args) -> None:
        self.watch_int(*args)

    def watch_double(self, *args) -> None:
        self.watch_float(*args)

    def watch_decimal(self, *args) -> None:
        self.watch_float(*args)

    def watch_char(self, *args) -> None:
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) < 2:
            raise TypeError("watch_char() expects name,value")
        name, value = args[0], args[1]
        group = args[2] if len(args) > 2 else ""
        char_value = value if isinstance(value, str) else chr(int(value))
        self._send_watch(level, name, char_value, WatchType.CHAR, group)

    def watch_datetime(self, *args) -> None:
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) < 2:
            raise TypeError("watch_datetime() expects name,value")
        name, value = args[0], args[1]
        group = args[2] if len(args) > 2 else ""
        if isinstance(value, datetime):
            text = value.isoformat()
        else:
            text = str(value)
        self._send_watch(level, name, text, WatchType.TIMESTAMP, group)

    def watch_date_time(self, *args) -> None:
        self.watch_datetime(*args)

    def watch_object(self, *args) -> None:
        self.watch(*args)

    def send_custom_control_command(self, *args) -> None:
        """Send custom control command (C# parity)."""
        level, args = self._parse_level_and_args(args, Level.CONTROL)
        if len(args) < 1:
            raise TypeError("send_custom_control_command() expects command_type[, data]")
        cmd = int(args[0])
        data = args[1] if len(args) > 1 else None
        if self.is_on(level):
            self._send_control_command(cmd, data)

    def send_custom_log_entry(self, *args) -> None:
        """Send custom log entry packet (C# parity)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) < 4:
            raise TypeError("send_custom_log_entry() expects title, log_entry_type, viewer_id[, data]")
        title = args[0]
        lt = int(args[1])
        vi = int(args[2])
        data = args[3] if len(args) > 3 else None
        self._send_log_entry(level, title, lt, vi, data=data)

    def send_custom_process_flow(self, *args) -> None:
        """Send custom process flow packet (C# parity)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) < 2:
            raise TypeError("send_custom_process_flow() expects title, process_flow_type")
        self._send_process_flow(level, args[0], int(args[1]))

    def send_custom_watch(self, *args) -> None:
        """Send custom watch packet (C# parity)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) < 3:
            raise TypeError("send_custom_watch() expects name, value, watch_type")
        self._send_watch(level, args[0], str(args[1]), int(args[2]))

    def send_watch(self, level: int, watch: Any) -> None:
        """Send a pre-constructed watch (used by metric extensions)."""
        if not self.is_on(level):
            return

        if isinstance(watch, dict):
            packet = dict(watch)
            packet.setdefault("packet_type", PacketType.WATCH)
            packet.setdefault("timestamp", datetime.now())
            packet.setdefault("level", level)
            self.parent.send_packet(packet)
            return

        if hasattr(watch, "name") and hasattr(watch, "value"):
            wt = getattr(watch, "watch_type", WatchType.STRING)
            grp = getattr(watch, "group", "")
            labels = getattr(watch, "labels", None)
            self._send_watch(level, watch.name, str(watch.value), int(wt), grp, labels)
            return

        raise TypeError("send_watch() expects dict-like or object with name/value")

    def log_custom_context(self, *args) -> None:
        """Log custom viewer context (C# parity)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 3:
            raise TypeError("log_custom_context() expects title, log_entry_type, context")
        title, log_entry_type, ctx = args
        if ctx is None:
            self.log_internal_error("log_custom_context: ctx argument is None")
            return
        if not self.is_on(level):
            return
        self._send_context(level, title, int(log_entry_type), ctx)

    def log_custom_text(self, *args) -> None:
        """Log custom text with explicit type/viewer (C# parity)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 4:
            raise TypeError("log_custom_text() expects title, text, log_entry_type, viewer_id")
        title, text, log_entry_type, viewer_id = args
        ctx = TextContext(int(viewer_id))
        ctx.load_from_text(str(text))
        self._send_context(level, title, int(log_entry_type), ctx)

    def log_custom_file(self, *args) -> None:
        """Log custom file (C# parity)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) == 3:
            file_name, log_entry_type, viewer_id = args
            title = os.path.basename(file_name)
        elif len(args) == 4:
            title, file_name, log_entry_type, viewer_id = args
        else:
            raise TypeError(
                "log_custom_file() expects (file_name, log_entry_type, viewer_id) or "
                "(title, file_name, log_entry_type, viewer_id)"
            )

        try:
            viewer = int(viewer_id)
            with open(file_name, "rb") as f:
                data = f.read()
            if viewer in (ViewerId.TITLE, ViewerId.DATA, ViewerId.WEB):
                text = data.decode("utf-8", errors="replace")
                self.log_custom_text(level, title, text, int(log_entry_type), viewer)
            else:
                ctx = BinaryViewerContext()
                ctx.append_bytes(data)
                self._send_context(level, title, int(log_entry_type), ctx)
        except Exception as e:
            self.log_internal_error(f"log_custom_file: {e}")

    def log_custom_reader(self, *args) -> None:
        """Log from text reader (C# parity)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 4:
            raise TypeError("log_custom_reader() expects title, reader, log_entry_type, viewer_id")
        title, reader, log_entry_type, viewer_id = args
        try:
            text = reader.read()
            self.log_custom_text(level, title, text, int(log_entry_type), int(viewer_id))
        except Exception as e:
            self.log_internal_error(f"log_custom_reader: {e}")

    def log_custom_stream(self, *args) -> None:
        """Log from binary stream (C# parity)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 4:
            raise TypeError("log_custom_stream() expects title, stream, log_entry_type, viewer_id")
        title, stream, log_entry_type, viewer_id = args
        try:
            data = stream.read()
            if isinstance(data, str):
                data = data.encode("utf-8")
            if not isinstance(data, (bytes, bytearray)):
                data = bytes(data)

            viewer = int(viewer_id)
            if viewer in (ViewerId.TITLE, ViewerId.DATA, ViewerId.WEB):
                text = data.decode("utf-8", errors="replace")
                self.log_custom_text(level, title, text, int(log_entry_type), viewer)
            else:
                ctx = BinaryViewerContext()
                ctx.append_bytes(bytes(data))
                self._send_context(level, title, int(log_entry_type), ctx)
        except Exception as e:
            self.log_internal_error(f"log_custom_stream: {e}")

    def log_source_file(self, *args) -> None:
        """Log source from file (C# parity)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) == 2:
            file_name, source_id = args
            title = os.path.basename(file_name)
        elif len(args) == 3:
            title, file_name, source_id = args
        else:
            raise TypeError(
                "log_source_file() expects (file_name, source_id) or (title, file_name, source_id)"
            )

        try:
            with open(file_name, "r", encoding="utf-8") as f:
                text = f.read()
            self.log_source(level, title, text, int(source_id))
        except Exception as e:
            self.log_internal_error(f"log_source_file: {e}")

    def log_source_reader(self, *args) -> None:
        """Log source from reader (C# parity)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 3:
            raise TypeError("log_source_reader() expects title, reader, source_id")
        title, reader, source_id = args
        try:
            self.log_source(level, title, reader.read(), int(source_id))
        except Exception as e:
            self.log_internal_error(f"log_source_reader: {e}")

    def log_source_stream(self, *args) -> None:
        """Log source from stream (C# parity)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 3:
            raise TypeError("log_source_stream() expects title, stream, source_id")
        title, stream, source_id = args
        try:
            data = stream.read()
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="replace")
            self.log_source(level, title, str(data), int(source_id))
        except Exception as e:
            self.log_internal_error(f"log_source_stream: {e}")

    def log_html_file(self, *args) -> None:
        """Log html file (C# parity)."""
        self.log_source_file(*args, SourceId.HTML)

    def log_html_reader(self, *args) -> None:
        """Log html reader (C# parity)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 2:
            raise TypeError("log_html_reader() expects title, reader")
        self.log_source_reader(level, args[0], args[1], SourceId.HTML)

    def log_html_stream(self, *args) -> None:
        """Log html stream (C# parity)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 2:
            raise TypeError("log_html_stream() expects title, stream")
        self.log_source_stream(level, args[0], args[1], SourceId.HTML)

    def log_text_reader(self, *args) -> None:
        """Log text from reader (C# parity)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 2:
            raise TypeError("log_text_reader() expects title, reader")
        title, reader = args
        try:
            self.log_text(level, title, reader.read())
        except Exception as e:
            self.log_internal_error(f"log_text_reader: {e}")

    def log_text_stream(self, *args) -> None:
        """Log text from stream (C# parity)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 2:
            raise TypeError("log_text_stream() expects title, stream")
        title, stream = args
        try:
            data = stream.read()
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="replace")
            self.log_text(level, title, str(data))
        except Exception as e:
            self.log_internal_error(f"log_text_stream: {e}")

    def log_reader(self, *args) -> None:
        """Generic reader alias (C# parity)."""
        self.log_text_reader(*args)

    def log_binary_stream(self, *args) -> None:
        """Log binary from stream (C# parity)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if len(args) != 2:
            raise TypeError("log_binary_stream() expects title, stream")
        title, stream = args
        try:
            data = stream.read()
            if isinstance(data, str):
                data = data.encode("utf-8")
            self.log_binary(level, title, bytes(data))
        except Exception as e:
            self.log_internal_error(f"log_binary_stream: {e}")

    def log_app_domain(self, *args) -> None:
        """.NET-specific API placeholder. Logs basic runtime info."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        title = args[0] if args else "AppDomain"
        self.log_system(level, title)

    def log_current_app_domain(self, *args) -> None:
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        title = args[0] if args else "Current AppDomain"
        self.log_system(level, title)

    def log_thread(self, *args) -> None:
        """Log thread details (C# parity)."""
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        if not args:
            raise TypeError("log_thread() expects title[, thread]")
        title = args[0]
        thread_obj = args[1] if len(args) > 1 else threading.current_thread()
        ctx = ValueListViewerContext()
        ctx.append_key_value("Name", getattr(thread_obj, "name", ""))
        ctx.append_key_value("Ident", str(getattr(thread_obj, "ident", "")))
        ctx.append_key_value("Daemon", str(getattr(thread_obj, "daemon", "")))
        self._send_context(level, title, LogEntryType.TEXT, ctx)

    def log_current_thread(self, *args) -> None:
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        title = args[0] if args else "Current Thread"
        self.log_thread(level, title, threading.current_thread())

    def log_current_stack_trace(self, *args) -> None:
        level, args = self._parse_level_and_args(args, self.parent.default_level)
        title = args[0] if args else "Current stack trace"
        self.log_stack_trace(level, title)


    def thread_exception_handler(self, sender: Any, exc: Exception) -> None:
        self.log_exception(exc, "Thread exception")

    def unhandled_exception_handler(self, sender: Any, exc: Exception) -> None:
        self.log_exception(exc, "Unhandled exception")


class MetricBuilder:
    """Fluent API for labeled metrics."""

    def __init__(self, session: Session, name: str):
        self._session = session
        self._name = name
        self._labels: Dict[str, str] = {}
        self._level: Optional[int] = None

    def with_label(self, key: str, value: Any) -> "MetricBuilder":
        self._labels[str(key)] = "" if value is None else str(value)
        return self

    def for_instance(self, instance: str) -> "MetricBuilder":
        return self.with_label("instance", instance)

    def with_level(self, level: int) -> "MetricBuilder":
        self._level = int(level)
        return self

    def set(self, value: Any) -> None:
        self._session.watch_with_labels(
            self._name,
            value,
            labels=self._labels,
            level=self._level,
        )

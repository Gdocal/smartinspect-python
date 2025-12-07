# SmartInspect Logging Handler
# Integration with Python's standard logging module

"""
SmartInspectHandler - integrates SmartInspect with Python's logging module.

Example usage:
    import logging
    from smartinspect import SmartInspect, SmartInspectHandler

    # Create SmartInspect instance
    si = SmartInspect("MyApp")
    si.connect(host="127.0.0.1")

    # Add SmartInspect handler to logger
    logger = logging.getLogger("myapp")
    handler = SmartInspectHandler(si)
    logger.addHandler(handler)

    # Log normally
    logger.info("Hello, world!")
    logger.error("Something went wrong", exc_info=True)
"""

import logging
import traceback
from datetime import datetime
from typing import Optional

from .enums import Level, LogEntryType, ViewerId
from .smartinspect import SmartInspect


class SmartInspectHandler(logging.Handler):
    """
    A logging handler that sends log records to SmartInspect Console.

    This handler integrates with Python's standard logging module,
    allowing you to use familiar logging patterns while getting
    the benefits of SmartInspect visualization.
    """

    def __init__(self, si: SmartInspect, level: int = logging.NOTSET):
        """
        Initialize the handler.

        Args:
            si: SmartInspect instance to use for logging
            level: Minimum logging level
        """
        super().__init__(level)
        self.si = si

    def _map_level_to_si_level(self, record_level: int) -> int:
        """Map Python logging level to SmartInspect level."""
        if record_level >= logging.CRITICAL:
            return Level.FATAL
        if record_level >= logging.ERROR:
            return Level.ERROR
        if record_level >= logging.WARNING:
            return Level.WARNING
        if record_level >= logging.INFO:
            return Level.MESSAGE
        if record_level >= logging.DEBUG:
            return Level.DEBUG
        return Level.VERBOSE

    def _map_level_to_si_entry_type(self, record_level: int) -> int:
        """Map Python logging level to SmartInspect entry type."""
        if record_level >= logging.CRITICAL:
            return LogEntryType.FATAL
        if record_level >= logging.ERROR:
            return LogEntryType.ERROR
        if record_level >= logging.WARNING:
            return LogEntryType.WARNING
        if record_level >= logging.INFO:
            return LogEntryType.MESSAGE
        if record_level >= logging.DEBUG:
            return LogEntryType.DEBUG
        return LogEntryType.VERBOSE

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record.

        Args:
            record: The log record to emit
        """
        try:
            si_level = self._map_level_to_si_level(record.levelno)

            # Check if logging is enabled for this level
            if not self.si.enabled:
                return

            # Get session based on logger name
            session = self.si.get_session(record.name)

            # Get timestamp
            timestamp = datetime.fromtimestamp(record.created)

            # Determine entry type and format message
            si_entry_type = self._map_level_to_si_entry_type(record.levelno)
            title = self.format(record)
            data_bytes: Optional[bytes] = None
            viewer_id = ViewerId.TITLE

            # Handle exceptions
            if record.exc_info:
                title = record.getMessage()
                exc_type, exc_value, exc_traceback = record.exc_info
                if exc_type is not None:
                    exc_text = "".join(
                        traceback.format_exception(exc_type, exc_value, exc_traceback)
                    )
                    data_bytes = exc_text.encode("utf-8")
                    viewer_id = ViewerId.DATA
                    si_entry_type = LogEntryType.ERROR
                    if si_level < Level.ERROR:
                        si_level = Level.ERROR

            # Send log entry
            session._send_log_entry(
                level=si_level,
                title=title,
                log_entry_type=si_entry_type,
                viewer_id=viewer_id,
                color=None,
                data=data_bytes,
            )

        except Exception:
            self.handleError(record)

    def close(self) -> None:
        """Close the handler."""
        try:
            # Don't disconnect the SmartInspect instance here
            # as it may be shared with other handlers or code
            pass
        finally:
            super().close()


class SmartInspectLoggerAdapter(logging.LoggerAdapter):
    """
    A logger adapter that adds SmartInspect-specific features.

    This adapter provides methods that map to SmartInspect functionality
    while still using the standard logging interface.
    """

    def __init__(self, logger: logging.Logger, si: SmartInspect, extra: Optional[dict] = None):
        """
        Initialize the adapter.

        Args:
            logger: The logger to adapt
            si: SmartInspect instance
            extra: Extra context to add to all log records
        """
        super().__init__(logger, extra or {})
        self.si = si

    def log_object(self, title: str, obj, level: int = logging.INFO) -> None:
        """Log an object with its properties."""
        self.si.log_object(title, obj)
        self.log(level, f"Object logged: {title}")

    def log_table(self, title: str, data, level: int = logging.INFO) -> None:
        """Log a table."""
        self.si.log_table(title, data)
        self.log(level, f"Table logged: {title}")

    def log_json(self, title: str, data, level: int = logging.INFO) -> None:
        """Log JSON data."""
        self.si.log_json(title, data)
        self.log(level, f"JSON logged: {title}")

    def watch(self, name: str, value) -> None:
        """Watch a value."""
        self.si.watch(name, value)

    def checkpoint(self, name: str = None) -> None:
        """Add a checkpoint."""
        self.si.add_checkpoint(name)

# SmartInspect Python Client Library
# Production-ready logging client for SmartInspect Console

"""
SmartInspect Python Client Library

A production-ready Python client for the SmartInspect logging console.
Provides structured logging with support for multiple data viewers,
method tracking, process flow visualization, and more.

Features:
- Object/Dictionary/Table logging with specialized viewers
- Method/Thread/Process flow tracking
- Source code logging with syntax highlighting (Python, SQL, JSON, XML, HTML)
- Binary data hex dump viewer
- Watch variables for real-time monitoring
- Checkpoints and counters
- Timer/performance tracking
- System info and memory logging
- Backlog buffering for disconnected state
- Auto-reconnect with time-gating
- WSL host auto-detection
- Integration with Python's logging module

Example usage:

    # Quick start
    from smartinspect import SmartInspect

    si = SmartInspect("MyApp")
    si.connect(host="127.0.0.1", port=4228)

    # Basic logging
    si.log_message("Hello, SmartInspect!")
    si.log_warning("This is a warning")
    si.log_error("This is an error")

    # Structured data
    si.log_object("User", {"name": "John", "age": 30})
    si.log_table("Users", [
        {"id": 1, "name": "John"},
        {"id": 2, "name": "Jane"}
    ])

    # Method tracking
    with si.track_method("my_function"):
        # ... your code ...
        pass

    # Watch variables
    si.watch("counter", 42)

    # Clean up
    si.disconnect()

Using with Python's logging module:

    import logging
    from smartinspect import SmartInspect, SmartInspectHandler

    si = SmartInspect("MyApp")
    si.connect(host="127.0.0.1")

    logger = logging.getLogger("myapp")
    logger.addHandler(SmartInspectHandler(si))
    logger.setLevel(logging.DEBUG)

    logger.info("Hello from standard logging!")
    logger.exception("Error occurred")
"""

__version__ = "1.0.0"
__author__ = "SmartInspect"

from .enums import (
    Level,
    PacketType,
    LogEntryType,
    ViewerId,
    WatchType,
    ControlCommandType,
    ProcessFlowType,
    SourceId,
    GraphicId,
    Color,
    Colors,
    DEFAULT_COLOR,
    SI_DEFAULT_COLOR_VALUE,
)

from .smartinspect import SmartInspect, get_default, get_main_session
from .session import Session
from .protocol import TcpProtocol, PacketQueue, detect_wsl_host
from .formatter import BinaryFormatter
from .contexts import (
    ViewerContext,
    TextContext,
    ListViewerContext,
    ValueListViewerContext,
    InspectorViewerContext,
    TableViewerContext,
    DataViewerContext,
    BinaryContext,
    BinaryViewerContext,
    SourceViewerContext,
    WebViewerContext,
    GraphicViewerContext,
)
from .handler import SmartInspectHandler, SmartInspectLoggerAdapter

__all__ = [
    # Version
    "__version__",
    # Main classes
    "SmartInspect",
    "Session",
    "TcpProtocol",
    "PacketQueue",
    "BinaryFormatter",
    # Enums
    "Level",
    "PacketType",
    "LogEntryType",
    "ViewerId",
    "WatchType",
    "ControlCommandType",
    "ProcessFlowType",
    "SourceId",
    "GraphicId",
    "Color",
    "Colors",
    "DEFAULT_COLOR",
    "SI_DEFAULT_COLOR_VALUE",
    # Contexts
    "ViewerContext",
    "TextContext",
    "ListViewerContext",
    "ValueListViewerContext",
    "InspectorViewerContext",
    "TableViewerContext",
    "DataViewerContext",
    "BinaryContext",
    "BinaryViewerContext",
    "SourceViewerContext",
    "WebViewerContext",
    "GraphicViewerContext",
    # Handler
    "SmartInspectHandler",
    "SmartInspectLoggerAdapter",
    # Convenience functions
    "get_default",
    "get_main_session",
    "detect_wsl_host",
]

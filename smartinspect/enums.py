# SmartInspect Enums
# Complete port of all C# enums for the SmartInspect protocol

"""
SmartInspect protocol enums and constants.
These match the C# SmartInspect library for wire compatibility.
"""

from enum import IntEnum
from typing import NamedTuple


class Level(IntEnum):
    """Log levels (matching C# Level enum)."""
    DEBUG = 0
    VERBOSE = 1
    MESSAGE = 2
    WARNING = 3
    ERROR = 4
    FATAL = 5
    CONTROL = 6


class PacketType(IntEnum):
    """Packet types sent over the wire."""
    CONTROL_COMMAND = 1
    LOG_ENTRY = 4
    WATCH = 5
    PROCESS_FLOW = 6
    LOG_HEADER = 7
    STREAM = 8


class LogEntryType(IntEnum):
    """Log entry types (matching C# LogEntryType enum)."""
    SEPARATOR = 0
    ENTER_METHOD = 1
    LEAVE_METHOD = 2
    RESET_CALLSTACK = 3
    MESSAGE = 100
    WARNING = 101  # 0x65
    ERROR = 102  # 0x66
    INTERNAL_ERROR = 103  # 0x67
    COMMENT = 104  # 0x68
    VARIABLE_VALUE = 105  # 0x69
    CHECKPOINT = 106  # 0x6a
    DEBUG = 107  # 0x6b
    VERBOSE = 108  # 0x6c
    FATAL = 109  # 0x6d
    CONDITIONAL = 110  # 0x6e
    ASSERT = 111  # 0x6f
    TEXT = 200  # 0xc8
    BINARY = 201  # 0xc9
    GRAPHIC = 202  # 0xca
    SOURCE = 203  # 0xcb
    OBJECT = 204  # 0xcc
    WEB_CONTENT = 205  # 0xcd
    SYSTEM = 206  # 0xce
    MEMORY_STATISTIC = 207  # 0xcf
    DATABASE_RESULT = 208  # 0xd0
    DATABASE_STRUCTURE = 209  # 0xd1


class ViewerId(IntEnum):
    """Viewer IDs for different visualization types."""
    NONE = -1
    TITLE = 0
    DATA = 1
    LIST = 2
    VALUE_LIST = 3
    INSPECTOR = 4
    TABLE = 5
    WEB = 100
    BINARY = 200
    HTML_SOURCE = 300
    JAVASCRIPT_SOURCE = 301  # 0x12d
    VBSCRIPT_SOURCE = 302  # 0x12e
    PERL_SOURCE = 303  # 0x12f
    SQL_SOURCE = 304  # 0x130
    INI_SOURCE = 305  # 0x131
    PYTHON_SOURCE = 306  # 0x132
    XML_SOURCE = 307  # 0x133
    BITMAP = 400
    JPEG = 401  # 0x191
    ICON = 402  # 0x192
    METAFILE = 403  # 0x193


class WatchType(IntEnum):
    """Watch variable types."""
    CHAR = 0
    STRING = 1
    INTEGER = 2
    FLOAT = 3
    BOOLEAN = 4
    ADDRESS = 5
    TIMESTAMP = 6
    OBJECT = 7


class ControlCommandType(IntEnum):
    """Control command types."""
    CLEAR_LOG = 0
    CLEAR_WATCHES = 1
    CLEAR_AUTO_VIEWS = 2
    CLEAR_ALL = 3
    CLEAR_PROCESS_FLOW = 4


class ProcessFlowType(IntEnum):
    """Process flow types for tracking execution flow."""
    ENTER_METHOD = 0
    LEAVE_METHOD = 1
    ENTER_THREAD = 2
    LEAVE_THREAD = 3
    ENTER_PROCESS = 4
    LEAVE_PROCESS = 5


class SourceId(IntEnum):
    """Source ID for different languages (for syntax highlighting)."""
    HTML = ViewerId.HTML_SOURCE
    JAVASCRIPT = ViewerId.JAVASCRIPT_SOURCE
    VBSCRIPT = ViewerId.VBSCRIPT_SOURCE
    PERL = ViewerId.PERL_SOURCE
    SQL = ViewerId.SQL_SOURCE
    INI = ViewerId.INI_SOURCE
    PYTHON = ViewerId.PYTHON_SOURCE
    XML = ViewerId.XML_SOURCE


class GraphicId(IntEnum):
    """Graphic ID for different image types."""
    BITMAP = ViewerId.BITMAP
    JPEG = ViewerId.JPEG
    ICON = ViewerId.ICON
    METAFILE = ViewerId.METAFILE


class Color(NamedTuple):
    """RGBA color representation."""
    r: int = 0
    g: int = 0
    b: int = 0
    a: int = 255

    def to_int(self) -> int:
        """Convert to SmartInspect color integer (BGRA format for little-endian)."""
        return ((self.r) |
                (self.g << 8) |
                (self.b << 16) |
                (self.a << 24)) & 0xFFFFFFFF


# Default color (triggers console's default theme color)
# This special value (0xFF000005) tells the console to use its theme color
DEFAULT_COLOR = Color(r=5, g=0, b=0, a=255)


class Colors:
    """Preset colors for log_colored().

    These colors are designed to work well as row backgrounds in both
    dark and light themes - muted, pleasant, and readable.
    """

    # Basic colors - muted versions that work as row backgrounds
    RED = Color(180, 80, 80)          # Muted coral red
    GREEN = Color(80, 150, 100)       # Soft forest green
    BLUE = Color(80, 120, 180)        # Soft steel blue
    YELLOW = Color(200, 180, 100)     # Muted gold
    ORANGE = Color(200, 130, 80)      # Muted terracotta
    PURPLE = Color(140, 100, 160)     # Soft lavender purple
    CYAN = Color(80, 160, 170)        # Muted teal
    PINK = Color(180, 130, 150)       # Dusty rose
    WHITE = Color(255, 255, 255)
    BLACK = Color(0, 0, 0)
    GRAY = Color(128, 128, 128)

    # Semantic colors - muted for readability
    SUCCESS = Color(90, 150, 110)     # Muted green
    WARNING = Color(190, 150, 80)     # Muted amber
    ERROR = Color(170, 90, 90)        # Muted red
    INFO = Color(90, 130, 160)        # Muted blue


def parse_color(color) -> Color:
    """
    Parse color from various formats to Color object.

    Supports:
    - Hex string: '#FF6432', '#FF6432FF', 'FF6432'
    - RGB tuple/list: (255, 100, 50) or [255, 100, 50, 255]
    - Color object: Color(255, 100, 50)
    - Dict: {'r': 255, 'g': 100, 'b': 50, 'a': 255}

    Args:
        color: Color in any supported format

    Returns:
        Color: Color namedtuple
    """
    if color is None:
        return DEFAULT_COLOR

    # Already a Color
    if isinstance(color, Color):
        return color

    # Tuple or list: (r, g, b) or (r, g, b, a)
    if isinstance(color, (tuple, list)):
        r = color[0] if len(color) > 0 else 0
        g = color[1] if len(color) > 1 else 0
        b = color[2] if len(color) > 2 else 0
        a = color[3] if len(color) > 3 else 255
        return Color(r, g, b, a)

    # Dict: {'r': ..., 'g': ..., 'b': ..., 'a': ...}
    if isinstance(color, dict):
        return Color(
            r=color.get('r', 0),
            g=color.get('g', 0),
            b=color.get('b', 0),
            a=color.get('a', 255)
        )

    # Hex string: '#FF6432', '#FF6432FF', 'FF6432'
    if isinstance(color, str):
        hex_str = color.lstrip('#')

        # Handle short hex: #F00 -> #FF0000
        if len(hex_str) == 3:
            hex_str = hex_str[0] * 2 + hex_str[1] * 2 + hex_str[2] * 2

        # Parse 6 or 8 character hex
        if len(hex_str) >= 6:
            try:
                r = int(hex_str[0:2], 16)
                g = int(hex_str[2:4], 16)
                b = int(hex_str[4:6], 16)
                a = int(hex_str[6:8], 16) if len(hex_str) >= 8 else 255
                return Color(r, g, b, a)
            except ValueError:
                pass

    return DEFAULT_COLOR


# Magic constant for default theme color in packet format
SI_DEFAULT_COLOR_VALUE = 0xFF000005

# Delphi/OLE Automation Date epoch offset
# Days between 1899-12-30 (OLE epoch) and 1970-01-01 (Unix epoch)
DELPHI_EPOCH_DAYS_OFFSET = 25569

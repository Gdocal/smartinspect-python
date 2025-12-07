# SmartInspect Viewer Contexts
# Different context types for formatting log data

"""
Viewer contexts for formatting structured data.
Each context type prepares data for a specific viewer in the SmartInspect Console.
"""

from typing import Optional, Any
from .enums import ViewerId

# UTF-8 BOM (Byte Order Mark) - required by SmartInspect for text data
BOM = bytes([0xEF, 0xBB, 0xBF])


def escape_line(line: Optional[str], to_escape: Optional[str] = None) -> str:
    """
    Escape line for list/value viewers.
    Replaces newlines with spaces and escapes specified characters.
    """
    if not line:
        return line or ""

    result = []
    prev_char = ""

    for ch in line:
        if ch in "\r\n":
            if prev_char not in "\r\n":
                result.append(" ")
        elif to_escape and ch in to_escape:
            result.append("\\")
            result.append(ch)
        else:
            result.append(ch)
        prev_char = ch

    return "".join(result)


def escape_csv_entry(entry: Optional[str]) -> str:
    """
    Escape CSV entry for table viewer.
    Wraps in quotes and escapes embedded quotes.
    """
    if not entry:
        return entry or ""

    result = ['"']
    for ch in entry:
        if ch.isspace():
            result.append(" ")
        elif ch == '"':
            result.append('""')
        else:
            result.append(ch)
    result.append('"')
    return "".join(result)


class ViewerContext:
    """Base ViewerContext class for all viewer types."""

    def __init__(self, viewer_id: int):
        self.viewer_id = viewer_id
        self.data = ""

    def get_viewer_data(self) -> bytes:
        """Get viewer data as bytes with UTF-8 BOM."""
        content = self.data.encode("utf-8")
        return BOM + content

    def append_text(self, text: Optional[str]) -> None:
        """Append text to the context."""
        if text is not None:
            self.data += text

    def append_line(self, line: Optional[str]) -> None:
        """Append a line with CRLF."""
        if line is not None:
            self.data += self.escape_line(line) + "\r\n"

    def escape_line(self, line: str) -> str:
        """Escape a line (override in subclasses)."""
        return line

    def reset(self) -> None:
        """Reset the data."""
        self.data = ""

    def load_from_text(self, text: str) -> None:
        """Load from text."""
        self.reset()
        self.append_text(text)


class TextContext(ViewerContext):
    """TextContext - basic text viewer."""

    def __init__(self, viewer_id: int = ViewerId.DATA):
        super().__init__(viewer_id)


class ListViewerContext(TextContext):
    """ListViewerContext - list viewer with line escaping."""

    def __init__(self, viewer_id: int = ViewerId.LIST):
        super().__init__(viewer_id)

    def escape_line(self, line: str) -> str:
        return escape_line(line, None)


class ValueListViewerContext(ListViewerContext):
    """ValueListViewerContext - key=value pairs."""

    def __init__(self, viewer_id: int = ViewerId.VALUE_LIST):
        super().__init__(viewer_id)

    def escape_item(self, item: str) -> str:
        return escape_line(item, "\\=")

    def append_key_value(self, key: Optional[str], value: Any) -> None:
        """Append a key-value pair."""
        if key is not None:
            self.append_text(self.escape_item(key))
            self.append_text("=")
            if value is not None:
                self.append_text(self.escape_item(str(value)))
            self.append_text("\r\n")


class InspectorViewerContext(ValueListViewerContext):
    """InspectorViewerContext - grouped key-value pairs."""

    def __init__(self):
        super().__init__(ViewerId.INSPECTOR)

    def escape_item(self, item: str) -> str:
        return escape_line(item, "\\=[]")

    def start_group(self, group: Optional[str]) -> None:
        """Start a new group."""
        if group is not None:
            self.append_text("[")
            self.append_text(self.escape_item(group))
            self.append_text("]\r\n")


class TableViewerContext(ListViewerContext):
    """TableViewerContext - CSV-like table data."""

    def __init__(self):
        super().__init__(ViewerId.TABLE)
        self.line_start = True

    def append_header(self, header: str) -> None:
        """Append header row."""
        self.append_line(header)
        self.append_line("")

    def begin_row(self) -> None:
        """Begin a new row."""
        self.line_start = True

    def end_row(self) -> None:
        """End current row."""
        self.append_line("")

    def add_row_entry(self, entry: Any) -> None:
        """Add entry to current row."""
        if entry is not None:
            if self.line_start:
                self.line_start = False
            else:
                self.append_text(", ")
            self.append_text(escape_csv_entry(str(entry)))


class DataViewerContext(TextContext):
    """DataViewerContext - raw data viewer."""

    def __init__(self):
        super().__init__(ViewerId.DATA)


class BinaryContext(ViewerContext):
    """BinaryContext - binary data viewer."""

    def __init__(self, viewer_id: int = ViewerId.BINARY):
        super().__init__(viewer_id)
        self.binary_data = b""

    def get_viewer_data(self) -> bytes:
        """Get viewer data (no BOM for binary)."""
        return self.binary_data

    def append_bytes(self, buffer: bytes, offset: int = 0, count: Optional[int] = None) -> None:
        """Append bytes."""
        if not buffer:
            return

        length = count if count is not None else len(buffer) - offset
        self.binary_data += buffer[offset : offset + length]

    def load_from_buffer(self, buffer: bytes) -> None:
        """Load from buffer."""
        self.binary_data = bytes(buffer)

    def reset(self) -> None:
        """Reset."""
        self.binary_data = b""


class BinaryViewerContext(BinaryContext):
    """BinaryViewerContext - hex dump viewer."""

    def __init__(self):
        super().__init__(ViewerId.BINARY)


class SourceViewerContext(TextContext):
    """SourceViewerContext - source code viewer with syntax highlighting."""

    def __init__(self, source_id: int):
        super().__init__(source_id)


class WebViewerContext(TextContext):
    """WebViewerContext - HTML content viewer."""

    def __init__(self):
        super().__init__(ViewerId.WEB)


class GraphicViewerContext(BinaryContext):
    """GraphicViewerContext - image viewer."""

    def __init__(self, graphic_id: int):
        super().__init__(graphic_id)

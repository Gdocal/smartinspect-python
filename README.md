# SmartInspect Python Client

A production-ready Python client for the SmartInspect logging console.

## Features

- **Object/Dictionary/Table logging** with specialized viewers
- **Method/Thread/Process flow tracking** for execution visualization
- **Source code logging** with syntax highlighting (Python, SQL, JSON, XML, HTML)
- **Binary data** hex dump viewer
- **Watch variables** for real-time monitoring
- **Checkpoints and counters** for execution tracking
- **Timer/performance tracking**
- **System info and memory logging**
- **Backlog buffering** for disconnected state
- **Auto-reconnect** with time-gating
- **WSL host auto-detection**
- **Integration** with Python's logging module

## Installation

```bash
pip install git+https://github.com/Gdocal/smartinspect-python.git
```

For memory monitoring features:
```bash
pip install "smartinspect[psutil] @ git+https://github.com/Gdocal/smartinspect-python.git"
```

## Quick Start

```python
from smartinspect import SmartInspect

# Create and connect
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

# Colored logging (use sparingly for important events)
from smartinspect import Colors
si.log_colored(Colors.SUCCESS, "Operation completed")
si.log_colored(Colors.WARNING, "Rate limit approaching")

# Clean up
si.disconnect()
```

## Preset Colors

```python
from smartinspect import Colors

# Use preset colors
si.log_colored(Colors.SUCCESS, "Done!")
si.log_colored(Colors.WARNING, "Caution")

# Or use hex string, tuple, or Color object
si.log_colored("#FF6432", "Hex color")
si.log_colored((255, 100, 50), "RGB tuple")
```

Available presets: `RED`, `GREEN`, `BLUE`, `YELLOW`, `ORANGE`, `PURPLE`, `CYAN`, `PINK`, `WHITE`, `BLACK`, `GRAY`, `SUCCESS`, `WARNING`, `ERROR`, `INFO`

## Using with Python's logging Module

```python
import logging
from smartinspect import SmartInspect, SmartInspectHandler

# Create SmartInspect instance
si = SmartInspect("MyApp")
si.connect(host="127.0.0.1")

# Add handler to logger
logger = logging.getLogger("myapp")
logger.addHandler(SmartInspectHandler(si))
logger.setLevel(logging.DEBUG)

# Log normally
logger.info("Hello from standard logging!")
logger.exception("Error occurred")
```

## Connection Options

```python
si.connect(
    host="127.0.0.1",          # TCP host (auto-detects WSL)
    port=4228,                  # TCP port
    room="myproject",           # Log room for isolation
    reconnect=True,             # Auto-reconnect on disconnect
    reconnect_interval=3.0,     # Seconds between reconnect attempts
    backlog_enabled=True,       # Buffer packets when disconnected
    backlog_queue=2048,         # Max backlog size in KB
    on_connect=lambda b: print(f"Connected: {b}"),
    on_disconnect=lambda: print("Disconnected"),
    on_error=lambda e: print(f"Error: {e}"),
)
```

Or use a connection string:
```python
si.connect(connection_string="tcp(host=localhost,port=4228,room=myproject,backlog=2048)")
```

## Session Management

```python
# Get named sessions for different components
auth_session = si.get_session("Auth")
db_session = si.get_session("Database")

auth_session.log_message("User logged in")
db_session.log_sql("Query", "SELECT * FROM users")
```

## Available Logging Methods

### Basic Logging
- `log_message(*args)` - Log a message
- `log_debug(*args)` - Log debug message
- `log_verbose(*args)` - Log verbose message
- `log_warning(*args)` - Log warning
- `log_error(*args)` - Log error
- `log_fatal(*args)` - Log fatal error
- `log_separator()` - Log a separator line
- `log_colored(color, *args)` - Log with color (use `Colors.SUCCESS`, `Colors.WARNING`, etc.)

### Structured Data
- `log_object(title, obj)` - Log object with properties
- `log_dictionary(title, dict)` - Log key-value pairs
- `log_table(title, data)` - Log tabular data
- `log_array(title, list)` - Log a list
- `log_json(title, data)` - Log JSON (pretty-printed)

### Source Code
- `log_python(title, code)` - Python with syntax highlighting
- `log_sql(title, code)` - SQL with syntax highlighting
- `log_javascript(title, code)` - JavaScript
- `log_html(title, code)` - HTML
- `log_xml(title, code)` - XML

### Binary Data
- `log_binary(title, data)` - Hex dump viewer

### Variables
- `log_value(name, value)` - Log any value
- `log_string(name, value)` - Log string
- `log_int(name, value)` - Log integer
- `log_bool(name, value)` - Log boolean

### Watch Variables
- `watch(name, value)` - Watch any value
- `watch_string(name, value)` - Watch string
- `watch_int(name, value)` - Watch integer
- `watch_float(name, value)` - Watch float
- `watch_bool(name, value)` - Watch boolean

### Method Tracking
- `enter_method(name)` - Enter a method
- `leave_method(name)` - Leave a method
- `track_method(name)` - Context manager for method tracking

### Process/Thread Flow
- `enter_process(name)` - Enter a process
- `leave_process(name)` - Leave a process
- `enter_thread(name)` - Enter a thread
- `leave_thread(name)` - Leave a thread

### Checkpoints & Counters
- `add_checkpoint(name, details)` - Add a checkpoint
- `inc_counter(name)` - Increment counter
- `dec_counter(name)` - Decrement counter

### Performance
- `time_start(name)` - Start a timer
- `time_end(name)` - End timer and log duration

### System Information
- `log_system()` - Log system information
- `log_memory()` - Log memory usage
- `log_environment()` - Log environment variables
- `log_stack_trace()` - Log current stack trace

### Stream Data
- `log_stream(channel, data, type)` - Send high-frequency data to a named channel

### Control Commands
- `clear_all()` - Clear all views
- `clear_log()` - Clear log view
- `clear_watches()` - Clear watches
- `clear_process_flow()` - Clear process flow

### Assertions
- `log_assert(condition, message)` - Log if condition is false
- `log_conditional(condition, *args)` - Log if condition is true

## WSL Support

The client automatically detects WSL environments and finds the Windows host IP:

```python
from smartinspect import detect_wsl_host

host = detect_wsl_host()  # Returns Windows host IP or None
```

## License

MIT

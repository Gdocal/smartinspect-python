# SmartInspect Python Client

A production-ready Python client for the SmartInspect logging console.

## Features

- **Object/Dictionary/Table logging** with specialized viewers
- **Method/Thread/Process flow tracking** for execution visualization
- **Source code logging** with syntax highlighting (Python, SQL, JSON, XML, HTML)
- **Binary data** hex dump viewer
- **Watch variables** for real-time monitoring
- **Labeled metrics** (Prometheus-style labels) via `watch_with_labels` and `metric(...)`
- **Checkpoints and counters** for execution tracking
- **Timer/performance tracking**
- **System info and memory logging**
- **Backlog buffering** for disconnected state
- **Async sender queue** so logging calls can return immediately
- **Context tags and trace correlation** (`SiContext`, `AsyncContext`, `*_ctx` logging methods)
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

# Preset colors (recommended)
si.log_colored(Colors.SUCCESS, "Done!")
si.log_colored(Colors.WARNING, "Caution")
si.log_colored(Colors.ERROR, "Failed!")

# Custom colors - multiple formats supported:
si.log_colored("#FF6432", "Hex string")
si.log_colored("#F00", "Short hex (red)")
si.log_colored((255, 100, 50), "RGB tuple")
```

**Presets:** `RED`, `GREEN`, `BLUE`, `YELLOW`, `ORANGE`, `PURPLE`, `CYAN`, `PINK`, `WHITE`, `BLACK`, `GRAY`, `SUCCESS`, `WARNING`, `ERROR`, `INFO`

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
    backlog_flush_on="error",   # Flush backlog on this level or above
    async_enabled=True,         # Non-blocking caller thread (background sender)
    async_queue=2048,           # Max async sender queue in KB
    async_throttle=False,       # If True, block when async queue is full
    async_clear_on_disconnect=False,  # If True, drop pending async packets on disconnect
    on_connect=lambda b: print(f"Connected: {b}"),
    on_disconnect=lambda: print("Disconnected"),
    on_error=lambda e: print(f"Error: {e}"),
)
```

`reconnect_interval` is in seconds in the Python API.

Or use a connection string:
```python
si.connect(
    connection_string=(
        "tcp(host=localhost,port=4228,room=myproject,"
        "backlog=2048,backlog.flushon=error,"
        "async.enabled=true,async.queue=2048,async.clearondisconnect=false)"
    )
)
```

In connection strings, `reconnect.interval` supports values like `3000`, `3000ms`, or `3s`.

### C# Configuration and Runtime Parity

The `SmartInspect` class now includes C#-parity runtime/configuration APIs:

- `set_variable(key, value)` / `get_variable(key)` / `unset_variable(key)`
- `load_connections(file_name, do_not_enable=False)`
- `load_configuration(file_name)`
- `now()`
- `dispatch(caption, action, state)`
- `send_control_command(packet_or_object)`
- `send_log_entry(packet_or_object)`
- `send_process_flow(packet_or_object)`
- `send_watch(packet_or_object)`
- `send_stream_packet(packet_or_object)`
- `dispose()`

Variables can be referenced in connection strings as `${key}` or `%key%`.


## Session Management

```python
# Get named sessions for different components
auth_session = si.get_session("Auth")
db_session = si.get_session("Database")

auth_session.log_message("User logged in")
db_session.log_sql("Query", "SELECT * FROM users")
```

## Available Logging Methods

Most session methods support C#-style overloads by accepting an optional leading `level` argument.
Additional C# parity helpers include metrics, stream helpers, context/tag helpers, data-table/data-set logging, bitmap/icon/jpeg/metafile logging aliases, and custom packet helper methods.


### Basic Logging
- `log_message(*args)` - Log a message
- `log_debug(*args)` - Log debug message
- `log_verbose(*args)` - Log verbose message
- `log_warning(*args)` - Log warning
- `log_error(*args)` - Log error
- `log_fatal(*args)` - Log fatal error
- `log_message_ctx(title, context)` - Log message with inline context tags
- `log_warning_ctx(title, context)` - Log warning with inline context tags
- `log_error_ctx(title, context)` - Log error with inline context tags
- `log_debug_ctx(title, context)` - Log debug with inline context tags
- `log_verbose_ctx(title, context)` - Log verbose with inline context tags
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
- `watch(name, value, group="")` - Watch any value
- `watch_string(name, value, group="")` - Watch string
- `watch_int(name, value, group="")` - Watch integer
- `watch_float(name, value, group="")` - Watch float
- `watch_bool(name, value, group="")` - Watch boolean
- `watch_with_labels(name, value, labels, level=None)` - Watch with labels for multi-dimensional metrics
- `metric(name)` - Fluent metric builder (`for_instance`, `with_label`, `with_level`, `set`)

The optional `group` parameter organizes watches in the web viewer:
```python
# Group watches by category
si.watch("cpu_usage", 45.2, group="Performance")
si.watch("memory_mb", 2048, group="Performance")
si.watch("active_users", 123, group="Stats")
si.watch("queue_size", 5, group="Stats")
```

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
- `log_stream(channel, data, stream_type="", group="")` - Send high-frequency data to a named channel
- `log_stream(level, channel, data, stream_type="", group="")` - Same with explicit level

```python
# Basic stream
si.log_stream("metrics", {"cpu": 45.2, "memory": 2048})

# With type identifier (shown in Type column)
si.log_stream("events", "User logged in", stream_type="text")

# With group for organizing streams in the viewer
si.log_stream("cpu_load", 45.2, stream_type="metric", group="Performance")
si.log_stream("memory", 2048, stream_type="metric", group="Performance")
si.log_stream("latency", 23.5, stream_type="metric", group="Network")
```

### Metrics (Labeled)

```python
# Direct labeled metric
si.watch_with_labels(
    "strategy_pnl",
    1250.50,
    {"instance": "BTC_trade", "env": "prod"},
)

# Fluent metric builder
si.metric("strategy_exit_reason") \
  .for_instance("BTC_trade") \
  .with_label("env", "prod") \
  .set("take_profit")
```

### Context and Trace Tags

```python
from smartinspect import SiContext, AsyncContext

with SiContext.scope({"requestId": "req-123", "userId": "john"}):
    si.log_message_ctx("Order created", {"orderId": "ord-77", "total": 420.5})

with AsyncContext.begin_correlation("CheckoutFlow"):
    with AsyncContext.begin_operation("ValidateCart"):
        si.log_debug("Validating cart")
```

`*_ctx` methods merge inline context with active `SiContext` scope, and packets include trace/correlation metadata when available.

Context utility exports:
- `SiContext.scope(...)`
- `SiContext.build().with_value(...).begin()`
- `AsyncContext.begin_correlation(...)`
- `AsyncContext.begin_operation(...)`

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

## Best Practices

### Lazy Initialization
When sessions are imported before `connect()`, use getters:
```python
_session = None
def get_session():
    global _session
    if _session is None:
        si.connect(...)
        _session = si.get_session("MySession")
    return _session
```

### Informative Titles
Put key info in title, details in object:
```python
log.log_json(f"QUERY '{query[:40]}' → {len(results)} results", {"query": query, "results": results})
```

## License

MIT

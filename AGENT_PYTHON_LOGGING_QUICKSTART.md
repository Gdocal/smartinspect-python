# SmartInspect Python Agent Quickstart

## Install

```bash
pip install "smartinspect @ git+https://github.com/Gdocal/smartinspect-python.git@main"
```

Pin in `pyproject.toml`:

```toml
dependencies = [
  "smartinspect @ git+https://github.com/Gdocal/smartinspect-python.git@<tag-or-commit>"
]
```

## Startup contract (required)

1. Agent generates `run_id`.
2. App prints `RUN_ID=<id>` once.
3. App puts `runId` into context for all logs.

```python
import uuid
from smartinspect import SmartInspect, SiContext

run_id = uuid.uuid4().hex
print(f"RUN_ID={run_id}")

si = SmartInspect("my-service")
si.connect(connection_string=(
    "tcp(host=127.0.0.1,port=4229,room=default,"
    "reconnect=true,backlog.enabled=true,async.enabled=true)"
))

with SiContext.scope(runId=run_id, service="my-service", env="dev"):
    si.log_message("service started")
```

## Config defaults to keep

Use non-blocking + reconnect-safe config:

```text
tcp(host=127.0.0.1,port=4229,room=default,reconnect=true,backlog.enabled=true,async.enabled=true)
```

Keep:
- `async.enabled=true` (do not block caller thread)
- `backlog.enabled=true` (buffer during disconnect)
- explicit `room`
- `disconnect()` on shutdown

## Levels (compact)

Severity low -> high:
- `debug(0)`, `verbose(1)`, `message(2)`, `warning(3)`, `error(4)`, `fatal(5)`
- `control(6)` is internal

Method mapping:
- `log_debug`, `log_verbose`, `log_message`, `log_warning`, `log_error`, `log_fatal`, `log_exception`

Helpers:
- `log_separator()` uses `default_level`; `log_separator(Level.DEBUG)` supported
- `log_colored(color, ...)` uses `default_level`
- `log_colored(Level.WARNING, color, ...)` supported

## Metrics, streams, context

Mapping:
- **Metrics tab** <- `watch_with_labels(...)`, `metric(...).set(...)`
- **Streams tab** <- `log_stream(...)`

```python
from smartinspect import AsyncContext

si.watch_with_labels("strategy_pnl", 1250.5, {"instance": "BTC_trade", "env": "prod"})
si.metric("strategy_exit_reason").for_instance("BTC_trade").with_label("env", "prod").set("take_profit")
si.log_stream("telemetry", {"cpu": 42.5, "mem": 1280}, stream_type="json", group="perf")

with SiContext.scope(runId=run_id, tenant="alpha", strategy="mean-reversion"):
    si.log_message_ctx("order created", {"orderId": "O-123"})

with AsyncContext.begin_correlation("CheckoutFlow"):
    with AsyncContext.begin_operation("ValidateCart"):
        si.log_debug("validating cart")
```

Notes:
- numeric watch values -> timeseries/histogram-style charts
- categorical watch values -> status/state style charts
- labels (`instance`, `env`, ...) -> split/filter metric series

## Query logs (minimal protocol)

Use only:
- `GET /api/logs/search`

Query params:
- `q`, `since` (`15m|2h|1d`), `from`, `to`, `limit` (`default=1000`, `max=10000`), `offset`, `order` (`asc|desc`), `room`

Query syntax:
- term: `timeout`
- field: `level:error,fatal`, `ctx.runId:${RUN_ID}`
- exclude: `-ctx.env:prod`
- group: `(timeout OR deadlock) level:error`

Use a small helper to avoid repeating curl flags:

```bash
search_logs () {
  local q="$1"
  local since="${2:-2h}"
  curl --get "http://localhost:5174/api/logs/search" \
    --data-urlencode "q=${q}" \
    --data-urlencode "since=${since}" \
    --data-urlencode "room=${ROOM:-default}" \
    --data-urlencode "limit=${LIMIT:-200}" \
    --data-urlencode "order=${ORDER:-desc}"
}
```

Common use:

```bash
search_logs "ctx.runId:${RUN_ID}"
search_logs "ctx.runId:${RUN_ID} level:error,fatal"
search_logs "ctx.runId:${RUN_ID} level:debug,verbose" "30m"
search_logs "ctx.runId:${RUN_ID} (timeout OR deadlock OR exception) -ctx.env:prod"

# paginate older slice
curl --get "http://localhost:5174/api/logs/search" \
  --data-urlencode "q=ctx.runId:${RUN_ID}" \
  --data-urlencode "since=2h" \
  --data-urlencode "room=${ROOM:-default}" \
  --data-urlencode "limit=200" \
  --data-urlencode "offset=200" \
  --data-urlencode "order=desc"
```

If `RUN_ID` is unknown:

```bash
search_logs "RUN_ID= service:my-service" "30m"
```

Then extract newest `RUN_ID=...` and continue with `ctx.runId:<id>`.

Hard rules:
- query by `ctx.runId:<id>` (except run-id discovery)
- always time-bound query (`since` or `from`+`to`)
- start with small `limit` and paginate with `offset`

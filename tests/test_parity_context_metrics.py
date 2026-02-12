import json
import struct
from datetime import datetime

from smartinspect.context_api import SiContext, AsyncContext
from smartinspect.enums import Level, PacketType, LogEntryType, ViewerId, WatchType, ProcessFlowType
from smartinspect.formatter import BinaryFormatter
from smartinspect.session import Session


class _DummyParent:
    def __init__(self):
        self.app_name = "TestApp"
        self.host_name = "TestHost"
        self.enabled = True
        self.level = Level.DEBUG
        self.default_level = Level.MESSAGE
        self.sent_packets = []

    def send_packet(self, packet):
        self.sent_packets.append(packet)


def test_log_message_ctx_merges_scope_and_inline_context():
    parent = _DummyParent()
    session = Session(parent, "Main")

    AsyncContext.clear()
    AsyncContext.new_correlation("Checkout")
    with SiContext.scope({"requestId": "req-1"}):
        session.log_message_ctx("Created order", {"orderId": "ord-7"})

    packet = parent.sent_packets[-1]
    assert packet["packet_type"] == PacketType.LOG_ENTRY
    assert packet["log_entry_type"] == LogEntryType.MESSAGE
    assert packet["ctx"]["requestId"] == "req-1"
    assert packet["ctx"]["orderId"] == "ord-7"
    assert packet["correlation_id"] is not None
    assert packet["operation_name"] == "Checkout"


def test_watch_with_labels_and_metric_builder():
    parent = _DummyParent()
    session = Session(parent, "Main")

    session.watch_with_labels("strategy_pnl", 1250.5, {"instance": "BTC", "env": "prod"})
    packet1 = parent.sent_packets[-1]
    assert packet1["packet_type"] == PacketType.WATCH
    assert packet1["watch_type"] == WatchType.FLOAT
    assert packet1["labels"]["instance"] == "BTC"

    session.metric("exit_reason").for_instance("BTC").with_label("env", "prod").set("tp")
    packet2 = parent.sent_packets[-1]
    assert packet2["packet_type"] == PacketType.WATCH
    assert packet2["watch_type"] == WatchType.STRING
    assert packet2["labels"]["instance"] == "BTC"
    assert packet2["labels"]["env"] == "prod"


def test_log_stream_accepts_level_as_first_argument():
    parent = _DummyParent()
    session = Session(parent, "Main")

    session.log_stream(Level.ERROR, "metrics", {"cpu": 42}, "json", "Perf")
    packet = parent.sent_packets[-1]
    assert packet["packet_type"] == PacketType.STREAM
    assert packet["level"] == Level.ERROR
    assert packet["channel"] == "metrics"
    assert packet["stream_type"] == "json"
    assert packet["group"] == "Perf"
    assert json.loads(packet["data"])["cpu"] == 42


def test_log_colored_accepts_optional_leading_level():
    parent = _DummyParent()
    session = Session(parent, "Main")

    session.log_colored(Level.WARNING, "#ff0000", "rate limit")
    packet = parent.sent_packets[-1]
    assert packet["packet_type"] == PacketType.LOG_ENTRY
    assert packet["level"] == Level.WARNING
    assert packet["title"] == "rate limit"

    session.log_colored("#00ff00", "ok")
    packet2 = parent.sent_packets[-1]
    assert packet2["packet_type"] == PacketType.LOG_ENTRY
    assert packet2["level"] == Level.MESSAGE
    assert packet2["title"] == "ok"


def test_binary_formatter_log_entry_v3_layout():
    formatter = BinaryFormatter()
    payload = {
        "packet_type": PacketType.LOG_ENTRY,
        "log_entry_type": LogEntryType.DEBUG,
        "viewer_id": ViewerId.TITLE,
        "app_name": "App",
        "session_name": "Main",
        "title": "Hello",
        "host_name": "Host",
        "correlation_id": "trace-1",
        "operation_name": "SpanA",
        "ctx": {"requestId": "req-2"},
        "data": b"abc",
        "process_id": 1,
        "thread_id": 2,
        "timestamp": datetime.now(),
        "operation_depth": 3,
    }
    data = formatter.compile_log_entry(payload)

    corr_len = struct.unpack_from("<i", data, 24)[0]
    op_len = struct.unpack_from("<i", data, 28)[0]
    ctx_len = struct.unpack_from("<i", data, 32)[0]
    op_depth = struct.unpack_from("<i", data, 60)[0]

    assert corr_len == len("trace-1".encode("utf-8"))
    assert op_len == len("SpanA".encode("utf-8"))
    assert ctx_len > 0
    assert op_depth == 3


def test_binary_formatter_watch_and_processflow_v3_layout():
    formatter = BinaryFormatter()

    watch_payload = {
        "packet_type": PacketType.WATCH,
        "name": "cpu",
        "value": "42",
        "watch_type": WatchType.INTEGER,
        "timestamp": datetime.now(),
        "group": "Perf",
        "labels": {"instance": "A"},
    }
    watch_data = formatter.compile_watch(watch_payload)
    labels_len = struct.unpack_from("<i", watch_data, 24)[0]
    assert labels_len > 0

    pf_payload = {
        "packet_type": PacketType.PROCESS_FLOW,
        "process_flow_type": ProcessFlowType.ENTER_METHOD,
        "title": "DoWork",
        "host_name": "Host",
        "correlation_id": "trace-2",
        "process_id": 1,
        "thread_id": 1,
        "timestamp": datetime.now(),
    }
    pf_data = formatter.compile_process_flow(pf_payload)
    corr_len = struct.unpack_from("<i", pf_data, 12)[0]
    assert corr_len == len("trace-2".encode("utf-8"))

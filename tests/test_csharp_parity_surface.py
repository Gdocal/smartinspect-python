import tempfile
from pathlib import Path

from smartinspect.enums import Level, PacketType
from smartinspect.session import Session
from smartinspect.smartinspect import SmartInspect


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


def test_session_overload_surface_parity_smoke():
    parent = _DummyParent()
    s = Session(parent, "Main")

    s.log_separator(Level.DEBUG)
    s.log_number(Level.DEBUG, "n", 12)
    s.log_binary(Level.MESSAGE, "bin", b"abcdef", 1, 3)
    s.log_text(Level.MESSAGE, "txt", "hello")
    s.log_source(Level.DEBUG, "src", "print(1)", 1)
    s.log_html(Level.DEBUG, "html", "<h1>x</h1>")
    s.log_sql(Level.DEBUG, "sql", "select 1")

    s.add_checkpoint(Level.DEBUG, "phase", "start")
    s.inc_counter(Level.DEBUG, "ctr")
    s.dec_counter(Level.DEBUG, "ctr")

    s.watch_string(Level.DEBUG, "s", "v", "g")
    s.watch_int(Level.DEBUG, "i", 3, True, "g")
    s.watch_float(Level.DEBUG, "f", 3.14, "g")
    s.watch_bool(Level.DEBUG, "b", True, "g")
    s.watch(Level.DEBUG, "o", {"k": 1}, "g")

    s.enter_method(Level.DEBUG, "MyClass", "Run")
    s.leave_method(Level.DEBUG, "MyClass", "Run")
    s.enter_process(Level.DEBUG, "Worker {0}", [1])
    s.leave_process(Level.DEBUG, "Worker {0}", [1])
    s.enter_thread(Level.DEBUG, "Thread {0}", [1])
    s.leave_thread(Level.DEBUG, "Thread {0}", [1])

    s.log_assert(False, "assert {0}", "failed")
    s.log_system(Level.DEBUG, "sys")
    s.log_stack_trace(Level.DEBUG, "trace")

    # Alias coverage
    s.log_collection(Level.DEBUG, "arr", [1, 2])
    s.log_enumerable(Level.DEBUG, "arr", (1, 2))
    s.log_string_builder(Level.DEBUG, "sb", "abc")
    s.log_bitmap(Level.DEBUG, "bmp", b"x")
    s.log_icon(Level.DEBUG, "ico", b"x")
    s.log_data_set(Level.DEBUG, {"name": "ds"})
    s.log_data_set_schema(Level.DEBUG, {"name": "ds"})
    s.log_data_table(Level.DEBUG, "tbl", [{"id": 1}])
    s.log_data_table_schema(Level.DEBUG, "tbl", {"columns": ["id"]})
    s.log_data_view(Level.DEBUG, "view", [{"id": 1}])


def test_smartinspect_csharp_runtime_methods_smoke():
    si = SmartInspect("Parity")

    si.set_variable("host", "127.0.0.1")
    assert si.get_variable("host") == "127.0.0.1"
    si.unset_variable("host")
    assert si.get_variable("host") is None

    si.send_log_entry({"packet_type": PacketType.LOG_ENTRY, "title": "x"})
    si.send_watch({"packet_type": PacketType.WATCH, "name": "w", "value": "1"})
    si.send_process_flow({"packet_type": PacketType.PROCESS_FLOW, "title": "pf"})
    si.send_stream_packet({"packet_type": PacketType.STREAM, "channel": "c", "data": "d"})
    si.send_control_command({"packet_type": PacketType.CONTROL_COMMAND, "command_type": 1})
    si.dispatch("tcp", 1, {"x": 1})
    assert si.now() is not None


def test_load_configuration_and_connections_parity():
    si = SmartInspect("ParityConfig")
    si.set_variable("room", "test-py")

    content = """
appname = NewName
level = debug
defaultlevel = message
enabled = false
connections = tcp(host=127.0.0.1,port=4229,room=${room},async.enabled=true)
""".strip()

    with tempfile.TemporaryDirectory() as td:
        cfg = Path(td) / "smartinspect.ini"
        cfg.write_text(content)

        si.load_configuration(str(cfg))

    assert si.app_name == "NewName"
    assert si.default_level == Level.MESSAGE
    assert si.connections.endswith("room=test-py,async.enabled=true)")

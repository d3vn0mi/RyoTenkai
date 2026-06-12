import ryotenkai
from unittest.mock import MagicMock


def test_module_imports():
    assert hasattr(ryotenkai, "load_config")


def test_get_jobs_returns_dict(mock_client):
    mock_client.jobs.list = {"0": "Exploit: multi/handler"}
    assert ryotenkai.get_jobs(mock_client) == {"0": "Exploit: multi/handler"}


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

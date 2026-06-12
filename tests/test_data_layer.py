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

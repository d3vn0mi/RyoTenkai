import ryotenkai
import json
import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock


def _args(**kw):
    """Build an argparse-like namespace with RPC attrs defaulting to None."""
    base = {"rpc_password": None, "rpc_server": None, "rpc_port": None, "rpc_ssl": None}
    base.update(kw)
    return SimpleNamespace(**base)


def _clear_env(monkeypatch):
    for k in ("RTK_RPC_PASSWORD", "RTK_RPC_SERVER", "RTK_RPC_PORT", "RTK_RPC_SSL"):
        monkeypatch.delenv(k, raising=False)


def test_parse_bool_variants():
    assert ryotenkai._parse_bool("True") is True
    assert ryotenkai._parse_bool("yes") is True
    assert ryotenkai._parse_bool("0") is False
    assert ryotenkai._parse_bool("off") is False
    assert ryotenkai._parse_bool(True) is True
    assert ryotenkai._parse_bool(None) is None


def test_resolve_conn_defaults_when_empty(monkeypatch):
    _clear_env(monkeypatch)
    assert ryotenkai.resolve_conn(_args(), {}) == ("msfrpc", "127.0.0.1", 55552, False)


def test_resolve_conn_config_over_default(monkeypatch):
    _clear_env(monkeypatch)
    cfg = {"rpc_password": "cfgpw", "rpc_server": "10.0.0.9",
           "rpc_port": "55559", "rpc_ssl": "True"}
    assert ryotenkai.resolve_conn(_args(), cfg) == ("cfgpw", "10.0.0.9", 55559, True)


def test_resolve_conn_env_over_config(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("RTK_RPC_PASSWORD", "envpw")
    monkeypatch.setenv("RTK_RPC_PORT", "7777")
    monkeypatch.setenv("RTK_RPC_SSL", "false")
    cfg = {"rpc_password": "cfgpw", "rpc_port": "55559", "rpc_ssl": "True"}
    pw, _, port, ssl = ryotenkai.resolve_conn(_args(), cfg)
    assert pw == "envpw"
    assert port == 7777
    assert ssl is False


def test_resolve_conn_cli_over_env(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("RTK_RPC_PASSWORD", "envpw")
    monkeypatch.setenv("RTK_RPC_SSL", "false")
    pw, _, _, ssl = ryotenkai.resolve_conn(
        _args(rpc_password="clipw", rpc_ssl=True), {})
    assert pw == "clipw"
    assert ssl is True


def test_resolve_conn_bad_port_raises(monkeypatch):
    _clear_env(monkeypatch)
    with pytest.raises(ValueError):
        ryotenkai.resolve_conn(_args(), {"rpc_port": "garbage"})


def test_parse_arguments_rpc_defaults_none(monkeypatch):
    monkeypatch.setattr("sys.argv", ["ryotenkai.py", "get_jobs"])
    args = ryotenkai.parse_arguments({})
    assert args.rpc_password is None
    assert args.rpc_server is None
    assert args.rpc_port is None
    assert args.rpc_ssl is None


def test_parse_arguments_ssl_flag_true(monkeypatch):
    monkeypatch.setattr("sys.argv", ["ryotenkai.py", "get_jobs", "--rpc-ssl"])
    args = ryotenkai.parse_arguments({})
    assert args.rpc_ssl is True


def test_parse_arguments_ssl_flag_false(monkeypatch):
    monkeypatch.setattr("sys.argv", ["ryotenkai.py", "get_jobs", "--no-rpc-ssl"])
    args = ryotenkai.parse_arguments({})
    assert args.rpc_ssl is False


def test_run_module_parses_timeout_flag(monkeypatch):
    monkeypatch.setattr("sys.argv", ["ryotenkai.py", "run_module", "multi/handler",
                                     "--option", "LHOST=1.2.3.4", "--timeout", "45"])
    args = ryotenkai.parse_arguments({})
    assert args.command == "run_module"
    assert args.timeout == 45


def test_run_module_timeout_defaults_from_config(monkeypatch):
    monkeypatch.setattr("sys.argv", ["ryotenkai.py", "run_module", "m",
                                     "--option", "X=Y"])
    args = ryotenkai.parse_arguments({"timeout": "25"})
    assert args.timeout == 25


def test_run_module_timeout_default_when_absent(monkeypatch):
    monkeypatch.setattr("sys.argv", ["ryotenkai.py", "run_module", "m",
                                     "--option", "X=Y"])
    args = ryotenkai.parse_arguments({})
    assert args.timeout == ryotenkai.CONSOLE_TIMEOUT


def test_main_get_jobs_prints_json(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["ryotenkai.py", "get_jobs"])
    monkeypatch.setattr(ryotenkai, "load_config", lambda *_a, **_k: {})
    fake = MagicMock()
    fake.jobs.list = {"0": "Exploit: multi/handler"}
    monkeypatch.setattr(ryotenkai, "make_client", lambda *a, **k: fake)
    ryotenkai.main()
    # Stdout must be parseable JSON (the Ansible-consumed contract), not just
    # contain the substring.
    data = json.loads(capsys.readouterr().out)
    assert data == {"0": "Exploit: multi/handler"}


def test_main_kill_session_prints_json(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["ryotenkai.py", "kill_session", "3"])
    monkeypatch.setattr(ryotenkai, "load_config", lambda *_a, **_k: {})
    fake = MagicMock()
    monkeypatch.setattr(ryotenkai, "make_client", lambda *a, **k: fake)
    ryotenkai.main()
    data = json.loads(capsys.readouterr().out)
    assert data["status"] == "success"
    assert "3" in data["message"]
    fake.sessions.session.assert_called_once_with("3")
    fake.sessions.session.return_value.stop.assert_called_once_with()


def test_main_is_callable():
    assert callable(ryotenkai.main)

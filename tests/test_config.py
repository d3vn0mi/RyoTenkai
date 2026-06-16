import ryotenkai
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

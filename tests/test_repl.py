from unittest.mock import MagicMock

import pytest

import ryotenkai


@pytest.fixture
def console():
    client = MagicMock()
    client.jobs.list = {}
    client.sessions.list = {}
    return ryotenkai.RtkConsole(client, conn_info={"rpc_server": "127.0.0.1",
                                                   "rpc_port": 55552, "rpc_ssl": True})


def test_prompt_changes_with_module(console):
    assert console.prompt_str() == "rtk > "
    console.dispatch("use exploit/multi/handler")
    assert console.prompt_str() == "rtk (exploit/multi/handler) > "


def test_use_set_run_builds_options(console, monkeypatch):
    captured = {}
    monkeypatch.setattr(ryotenkai, "run_exploit",
                        lambda client, mod, opts, regex=None: captured.update(mod=mod, opts=opts)
                        or {"status": "success", "raw_output": "ok"})
    console.dispatch("use exploit/multi/handler")
    console.dispatch("set LHOST 10.0.0.1")
    console.dispatch("set LPORT 4444")
    out, keep, action = console.dispatch("run")
    assert captured["mod"] == "exploit/multi/handler"
    assert captured["opts"] == {"LHOST": "10.0.0.1", "LPORT": "4444"}
    assert keep is True


def test_run_without_module_warns(console):
    out, keep, action = console.dispatch("run")
    assert "no module" in out.lower()


def test_jobs_kill_calls_data_layer(console):
    out, keep, action = console.dispatch("jobs -k 2")
    console.client.jobs.stop.assert_called_once_with("2")


def test_set_output_toggles_mode(console):
    console.dispatch("set output json")
    assert console.output_mode == "json"
    console.client.jobs.list = {"0": "handler"}
    out, _, _ = console.dispatch("jobs")
    assert out.strip().startswith("{")


def test_sessions_interact_returns_action(console):
    out, keep, action = console.dispatch("sessions -i 4")
    assert action == ("interact", "4")
    assert keep is True


def test_exit_stops_loop(console):
    out, keep, action = console.dispatch("exit")
    assert keep is False


def test_unknown_command(console):
    out, keep, action = console.dispatch("frobnicate")
    assert "unknown" in out.lower()
    assert keep is True

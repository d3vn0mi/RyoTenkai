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
    assert console.prompt_str() == "ryo > "
    console.dispatch("use exploit/multi/handler")
    assert console.prompt_str() == "ryo (exploit/multi/handler) > "


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


def test_dispatch_catches_handler_rpc_error(console, monkeypatch):
    def boom(client):
        raise ryotenkai.MsfRpcError("down")
    monkeypatch.setattr(ryotenkai, "get_job_details", boom)
    out, keep, action = console.dispatch("jobs")
    assert "rpc error" in out.lower()
    assert keep is True


def test_dispatch_catches_generic_error(console, monkeypatch):
    def boom(client):
        raise ValueError("boom")
    monkeypatch.setattr(ryotenkai, "get_job_details", boom)
    out, keep, action = console.dispatch("jobs")
    assert out.lower().startswith("[!] error")
    assert keep is True


def test_generate_success(console, monkeypatch):
    seen = {}

    def fake_gen(*a):
        seen["args"] = a
        return {"status": "success", "message": "Payload saved to out.elf"}

    monkeypatch.setattr(ryotenkai, "generate_payload", fake_gen)
    out, keep, action = console.dispatch(
        "generate elf linux/x64/meterpreter/reverse_tcp 10.0.0.1 4444 out.elf")
    assert seen["args"] == ("elf", "linux/x64/meterpreter/reverse_tcp",
                            "10.0.0.1", "4444", "out.elf")
    assert "Payload saved" in out


def test_generate_usage_error(console):
    out, keep, action = console.dispatch("generate elf p 1")
    assert "usage" in out.lower()


def test_set_output_invalid(console):
    out, keep, action = console.dispatch("set output xml")
    assert "json or table" in out
    assert console.output_mode == "table"


def test_interact_session_runs_commands(console, monkeypatch):
    sent = []
    monkeypatch.setattr(ryotenkai, "run_session_command",
                        lambda client, sid, cmd: sent.append((sid, cmd)) or f"out:{cmd}")
    inputs = iter(["whoami", "id", "background"])
    written = []

    def read_line():
        return next(inputs)

    console.interact_session("4", read_line=read_line, write_out=written.append)
    assert sent == [("4", "whoami"), ("4", "id")]
    assert any("out:whoami" in w for w in written)


def test_interact_session_exits_on_eof(console, monkeypatch):
    monkeypatch.setattr(ryotenkai, "run_session_command",
                        lambda *a, **k: "x")

    def read_line():
        raise EOFError

    # Should return without raising.
    console.interact_session("4", read_line=read_line, write_out=lambda *_: None)

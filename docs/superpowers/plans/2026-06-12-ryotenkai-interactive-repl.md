# RyoTenkai Interactive REPL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `msfconsole`-style interactive REPL to `ryotenkai.py` over the Metasploit RPC server, and refactor the file so its core logic is bug-free, optimized, and unit-tested.

**Architecture:** Reorganize `ryotenkai.py` into four layers inside one file — connection helper, pure data functions (return data, never print), a presentation layer (table vs JSON), and a `prompt_toolkit` REPL (`RtkConsole`). Non-interactive subcommands keep emitting JSON (Ansible contract). The REPL holds one persistent client and a stateful `use`/`set`/`run` module context, plus an interactive `sessions -i` sub-prompt.

**Tech Stack:** Python 3.8+, `pymetasploit3` (RPC), `prompt_toolkit` (REPL), `pytest` + `unittest.mock` (tests). No table dependency — internal formatter.

---

## Scope

In scope: `ryotenkai.py`, `requirements.txt`, new `tests/` directory. Out of scope: `ryotenkai_gui/` (Django), `agent.py`, `ryotenkai_c2.py`, `beacon.py`.

## File Structure

- **Modify** `ryotenkai.py` — all layers (single file, reorganized into sections).
- **Modify** `requirements.txt` — add `pymetasploit3`, `prompt_toolkit`, `pytest`.
- **Create** `tests/conftest.py` — pytest fixtures (`mock_client`).
- **Create** `tests/test_data_layer.py` — connection/data functions.
- **Create** `tests/test_format.py` — presentation layer.
- **Create** `tests/test_repl.py` — `RtkConsole.dispatch` and `interact_session`.

Public API defined by this plan (names are fixed — later tasks depend on them):

```
make_client(rpc_password, rpc_server, rpc_port, rpc_ssl) -> client
get_jobs(client) -> dict
get_sessions(client) -> dict
kill_job(client, job_id) -> dict
_read_console(console, timeout, interval) -> str
_read_session(session, timeout, interval, quiet_rounds) -> str
run_exploit(client, module_name, options, regex=None) -> dict
run_session_command(client, session_id, command) -> str
access_session(client, session_id, command_sequence) -> dict
generate_payload(fmt, payload, lhost, lport, output_file) -> dict
parse_options(option_args) -> dict
render_table(headers, rows) -> str
format_jobs(jobs) -> str
format_sessions(sessions) -> str
format_exploit_result(result) -> str
class RtkConsole: dispatch(line) -> (output:str, keep_going:bool, action)
                  interact_session(session_id, read_line, write_out) -> None
```

---

## Task 1: Test infrastructure + dependencies

**Files:**
- Modify: `requirements.txt`
- Create: `tests/conftest.py`
- Create: `tests/test_data_layer.py`

- [ ] **Step 1: Populate requirements.txt**

Replace the empty file with:

```
pymetasploit3
prompt_toolkit
pytest
```

- [ ] **Step 2: Install deps**

Run: `pip install -r requirements.txt`
Expected: `pymetasploit3`, `prompt_toolkit`, `pytest` install successfully.

- [ ] **Step 3: Write the mock-client fixture**

Create `tests/conftest.py`:

```python
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Make ryotenkai.py importable from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def mock_client():
    """A MagicMock MsfRpcClient. Tests set .jobs.list, .sessions.list, etc."""
    client = MagicMock()
    client.jobs.list = {}
    client.sessions.list = {}
    return client
```

- [ ] **Step 4: Write a smoke import test**

Create `tests/test_data_layer.py`:

```python
import ryotenkai


def test_module_imports():
    assert hasattr(ryotenkai, "load_config")
```

- [ ] **Step 5: Run the smoke test**

Run: `pytest tests/test_data_layer.py -v`
Expected: PASS (1 passed).

- [ ] **Step 6: Commit**

```bash
git add requirements.txt tests/conftest.py tests/test_data_layer.py
git commit -m "test: add pytest infra and deps for ryotenkai"
```

---

## Task 2: Connection + jobs/sessions data functions

Refactor `make_client`, `get_jobs`, `get_sessions` to return data (no printing), and add `kill_job`.

**Files:**
- Modify: `ryotenkai.py`
- Modify: `tests/test_data_layer.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_data_layer.py`:

```python
from unittest.mock import MagicMock


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_data_layer.py -v`
Expected: FAIL (`AttributeError`: module has no attribute `get_jobs`/`kill_job`/`make_client`, or old `get_jobs` prints/returns wrong shape).

- [ ] **Step 3: Implement in ryotenkai.py**

In `ryotenkai.py`, replace the existing `get_jobs` and `get_sessions` functions with the versions below, and add `make_client` and `kill_job` near them:

```python
def make_client(rpc_password, rpc_server, rpc_port, rpc_ssl):
    """Build a Metasploit RPC client."""
    return MsfRpcClient(rpc_password, server=rpc_server, port=rpc_port, ssl=rpc_ssl)


def get_jobs(client):
    """Return the dict of active Metasploit jobs."""
    return client.jobs.list


def get_sessions(client):
    """Return the dict of active Metasploit sessions."""
    return client.sessions.list


def kill_job(client, job_id):
    """Stop a running job by id."""
    client.jobs.stop(str(job_id))
    return {"status": "success", "message": f"Job {job_id} killed"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_data_layer.py -v`
Expected: PASS (all tests in file).

- [ ] **Step 5: Commit**

```bash
git add ryotenkai.py tests/test_data_layer.py
git commit -m "refactor: data-layer jobs/sessions return data; add make_client, kill_job"
```

---

## Task 3: Poll helpers + run_exploit + session command

Replace fixed `time.sleep` reads with bounded polling. `run_exploit` and the session path return data instead of printing.

**Files:**
- Modify: `ryotenkai.py`
- Modify: `tests/test_data_layer.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_data_layer.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_data_layer.py -v`
Expected: FAIL (`_read_console`/`_read_session`/`run_session_command` not defined; `run_exploit` prints instead of returning).

- [ ] **Step 3: Implement in ryotenkai.py**

Add polling constants near the top of `ryotenkai.py` (after imports):

```python
POLL_INTERVAL = 0.5
CONSOLE_TIMEOUT = 15
SESSION_TIMEOUT = 10
SESSION_QUIET_ROUNDS = 2
```

Add the poll helpers:

```python
def _read_console(console, timeout=CONSOLE_TIMEOUT, interval=POLL_INTERVAL):
    """Read a console, accumulating output until it is no longer busy or timeout."""
    deadline = time.monotonic() + timeout
    chunks = []
    while True:
        result = console.read()
        chunks.append(result.get("data", ""))
        if not result.get("busy", False):
            break
        if time.monotonic() >= deadline:
            break
        time.sleep(interval)
    return "".join(chunks)


def _read_session(session, timeout=SESSION_TIMEOUT, interval=POLL_INTERVAL,
                  quiet_rounds=SESSION_QUIET_ROUNDS):
    """Read a session, stopping after output goes quiet for `quiet_rounds` polls."""
    deadline = time.monotonic() + timeout
    chunks = []
    quiet = 0
    while True:
        data = session.read() or ""
        if data:
            chunks.append(data)
            quiet = 0
        else:
            quiet += 1
            if quiet >= quiet_rounds:
                break
        if time.monotonic() >= deadline:
            break
        time.sleep(interval)
    return "".join(chunks)
```

Replace the existing `run_exploit` body with:

```python
def run_exploit(client, module_name, options, regex=None):
    """Run a module via a console (`run -j`) and return structured output."""
    try:
        console = client.consoles.console()
        console.write(f"use {module_name}\n")
        for option, value in options.items():
            console.write(f"set {option} {value}\n")
        console.write("run -j\n")
        output = _read_console(console)

        filtered_output = None
        if regex:
            matches = re.findall(regex, output, re.DOTALL)
            filtered_output = "\n".join(matches)

        return {
            "status": "success",
            "module": module_name,
            "options": options,
            "raw_output": output,
            "filtered_output": filtered_output if filtered_output else "No match for regex",
        }
    except MsfRpcError as e:
        return {"status": "error", "message": f"Metasploit RPC error: {str(e)}"}
    except Exception as e:
        return {"status": "error", "message": f"An unexpected error occurred: {str(e)}"}
```

Replace the existing `access_session` and add `run_session_command`:

```python
def run_session_command(client, session_id, command):
    """Write one command to a session and return the polled output."""
    session = client.sessions.session(session_id)
    session.write(command + "\n")
    return _read_session(session)


def access_session(client, session_id, command_sequence):
    """Run a sequence of commands in a session; return the final result."""
    results = []
    for command in command_sequence:
        results.append(run_session_command(client, session_id, command))
    return {
        "session_id": session_id,
        "command_sequence": command_sequence,
        "final_result": results[-1] if results else "",
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_data_layer.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ryotenkai.py tests/test_data_layer.py
git commit -m "refactor: poll-until-idle reads; run_exploit/session funcs return data"
```

---

## Task 4: generate_payload + option parsing fix

`generate_payload` returns a dict. Add `parse_options` to fix the `OPTION=VALUE` vs space bug.

**Files:**
- Modify: `ryotenkai.py`
- Modify: `tests/test_data_layer.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_data_layer.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_data_layer.py -v`
Expected: FAIL (`parse_options` undefined; `generate_payload` prints instead of returning).

- [ ] **Step 3: Implement in ryotenkai.py**

Add `parse_options`:

```python
def parse_options(option_args):
    """Parse --option values. Accept OPTION=VALUE (preferred) or 'OPTION VALUE'."""
    options = {}
    for opt in option_args or []:
        if "=" in opt:
            key, value = opt.split("=", 1)
        else:
            key, value = opt.split(" ", 1)
        options[key.strip()] = value.strip()
    return options
```

Replace the existing `generate_payload` body with (note: param renamed `format` -> `fmt`):

```python
def generate_payload(fmt, payload, lhost, lport, output_file):
    """Generate a payload with msfvenom; return a structured result."""
    command = ["msfvenom", "-p", payload, f"LHOST={lhost}", f"LPORT={lport}",
               "-f", fmt, "-o", output_file]
    try:
        subprocess.run(command, check=True)
        return {
            "status": "success",
            "message": f"Payload saved to {output_file}",
            "details": {"format": fmt, "payload": payload, "lhost": lhost,
                        "lport": lport, "output_file": output_file},
        }
    except subprocess.CalledProcessError as e:
        return {"status": "error", "message": f"Failed to generate payload: {str(e)}"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_data_layer.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ryotenkai.py tests/test_data_layer.py
git commit -m "fix: OPTION=VALUE parsing; generate_payload returns data"
```

---

## Task 5: Presentation layer

Table formatter + per-kind formatters. No external table dependency.

**Files:**
- Modify: `ryotenkai.py`
- Create: `tests/test_format.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_format.py`:

```python
import ryotenkai


def test_render_table_basic():
    out = ryotenkai.render_table(["ID", "Name"], [["0", "handler"]])
    assert "ID" in out and "Name" in out and "handler" in out
    # Header, separator, one data row.
    assert len(out.splitlines()) == 3


def test_render_table_empty():
    assert ryotenkai.render_table(["ID"], []) == "(none)"


def test_format_jobs():
    out = ryotenkai.format_jobs({"0": "Exploit: multi/handler"})
    assert "0" in out and "multi/handler" in out


def test_format_sessions():
    out = ryotenkai.format_sessions(
        {"1": {"type": "meterpreter", "tunnel_peer": "10.0.0.5", "info": "WORKGROUP"}}
    )
    assert "meterpreter" in out and "10.0.0.5" in out


def test_format_exploit_result_success():
    out = ryotenkai.format_exploit_result({"status": "success", "raw_output": "PID 99"})
    assert "PID 99" in out


def test_format_exploit_result_error():
    out = ryotenkai.format_exploit_result({"status": "error", "message": "nope"})
    assert "nope" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_format.py -v`
Expected: FAIL (formatters undefined).

- [ ] **Step 3: Implement in ryotenkai.py**

```python
def render_table(headers, rows):
    """Render an aligned text table. Returns '(none)' for empty rows."""
    if not rows:
        return "(none)"
    str_rows = [[str(c) for c in row] for row in rows]
    cols = list(zip(*([headers] + str_rows)))
    widths = [max(len(c) for c in col) for col in cols]

    def fmt(row):
        return "  ".join(c.ljust(w) for c, w in zip(row, widths))

    lines = [fmt(headers), "  ".join("-" * w for w in widths)]
    lines += [fmt(row) for row in str_rows]
    return "\n".join(lines)


def format_jobs(jobs):
    rows = [[jid, name] for jid, name in (jobs or {}).items()]
    return render_table(["Job ID", "Module"], rows)


def format_sessions(sessions):
    rows = []
    for sid, info in (sessions or {}).items():
        info = info or {}
        rows.append([sid, info.get("type", ""), info.get("tunnel_peer", ""),
                     info.get("info", "")])
    return render_table(["ID", "Type", "Peer", "Info"], rows)


def format_exploit_result(result):
    if result.get("status") == "error":
        return f"[!] {result.get('message')}"
    return result.get("raw_output", "") or "[*] module started"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_format.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ryotenkai.py tests/test_format.py
git commit -m "feat: table/JSON presentation layer for ryotenkai"
```

---

## Task 6: REPL core (RtkConsole.dispatch + handlers)

The REPL class and its line dispatcher — no `prompt_toolkit` calls yet, so it is fully unit-testable.

**Files:**
- Modify: `ryotenkai.py`
- Create: `tests/test_repl.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_repl.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_repl.py -v`
Expected: FAIL (`RtkConsole` undefined).

- [ ] **Step 3: Implement RtkConsole in ryotenkai.py**

Add `import shlex` and `import os` to the imports at the top of the file (if not present), then add the class:

```python
class RtkConsole:
    """Interactive msfconsole-style REPL over a persistent RPC client."""

    HANDLERS = ("jobs", "sessions", "use", "set", "unset", "options", "run",
                "exploit", "back", "generate", "connect", "help", "?")

    def __init__(self, client, conn_info=None):
        self.client = client
        self.conn_info = conn_info or {}
        self.current_module = None
        self.module_options = {}
        self.output_mode = "table"

    def prompt_str(self):
        if self.current_module:
            return f"rtk ({self.current_module}) > "
        return "rtk > "

    def _emit(self, data, table_fn):
        if self.output_mode == "json":
            return json.dumps(data, indent=4)
        return table_fn(data)

    def dispatch(self, line):
        """Parse and execute one command. Returns (output, keep_going, action)."""
        line = (line or "").strip()
        if not line:
            return ("", True, None)
        try:
            parts = shlex.split(line)
        except ValueError as e:
            return (f"[!] parse error: {e}", True, None)
        cmd, cmd_args = parts[0], parts[1:]

        if cmd in ("exit", "quit"):
            return ("", False, None)
        if cmd == "sessions" and cmd_args and cmd_args[0] == "-i":
            if len(cmd_args) < 2:
                return ("[!] usage: sessions -i <id>", True, None)
            return ("", True, ("interact", cmd_args[1]))

        handler = {
            "jobs": self.do_jobs,
            "sessions": self.do_sessions,
            "use": self.do_use,
            "set": self.do_set,
            "unset": self.do_unset,
            "options": self.do_options,
            "run": self.do_run,
            "exploit": self.do_run,
            "back": self.do_back,
            "generate": self.do_generate,
            "connect": self.do_connect,
            "help": self.do_help,
            "?": self.do_help,
        }.get(cmd)
        if handler is None:
            return (f"[!] unknown command: {cmd} (try 'help')", True, None)
        try:
            return (handler(cmd_args), True, None)
        except MsfRpcError as e:
            return (f"[!] RPC error: {e}", True, None)
        except Exception as e:
            return (f"[!] error: {e}", True, None)

    # --- handlers (return a string) ---

    def do_jobs(self, args):
        if args and args[0] == "-k":
            if len(args) < 2:
                return "[!] usage: jobs -k <id>"
            return self._emit(kill_job(self.client, args[1]),
                              lambda d: d.get("message", ""))
        return self._emit(get_jobs(self.client), format_jobs)

    def do_sessions(self, args):
        return self._emit(get_sessions(self.client), format_sessions)

    def do_use(self, args):
        if not args:
            return "[!] usage: use <module>"
        self.current_module = args[0]
        self.module_options = {}
        return f"[*] using {args[0]}"

    def do_set(self, args):
        if len(args) >= 2 and args[0] == "output":
            mode = args[1].lower()
            if mode not in ("json", "table"):
                return "[!] output mode must be json or table"
            self.output_mode = mode
            return f"[*] output mode: {mode}"
        if len(args) < 2:
            return "[!] usage: set <OPTION> <VALUE>  |  set output json|table"
        if not self.current_module:
            return "[!] no module selected (use <module> first)"
        self.module_options[args[0]] = " ".join(args[1:])
        return f"{args[0]} => {' '.join(args[1:])}"

    def do_unset(self, args):
        if args and args[0] in self.module_options:
            del self.module_options[args[0]]
            return f"unset {args[0]}"
        return "[!] not set"

    def do_options(self, args):
        if not self.current_module:
            return "[!] no module selected"
        rows = [[k, v] for k, v in self.module_options.items()]
        return f"Module: {self.current_module}\n" + render_table(["Option", "Value"], rows)

    def do_run(self, args):
        if not self.current_module:
            return "[!] no module selected (use <module> first)"
        result = run_exploit(self.client, self.current_module, dict(self.module_options))
        return self._emit(result, format_exploit_result)

    def do_back(self, args):
        self.current_module = None
        self.module_options = {}
        return ""

    def do_generate(self, args):
        if len(args) != 5:
            return "[!] usage: generate <fmt> <payload> <lhost> <lport> <outfile>"
        result = generate_payload(*args)
        return self._emit(result, lambda d: d.get("message", ""))

    def do_connect(self, args):
        ci = self.conn_info
        return (f"[*] RPC {ci.get('rpc_server')}:{ci.get('rpc_port')} "
                f"ssl={ci.get('rpc_ssl')}")

    def do_help(self, args):
        return (
            "Commands:\n"
            "  jobs                         list active jobs\n"
            "  jobs -k <id>                 kill a job\n"
            "  sessions                     list active sessions\n"
            "  sessions -i <id>             interact with a session\n"
            "  use <module>                 select a module\n"
            "  set <OPT> <VAL>              set a module option\n"
            "  unset <OPT>                  clear a module option\n"
            "  options                      show current module + options\n"
            "  run | exploit                run the current module (run -j)\n"
            "  back                         clear current module\n"
            "  generate <fmt> <payload> <lhost> <lport> <outfile>\n"
            "  set output json|table        switch output format\n"
            "  connect                      show RPC connection\n"
            "  help | ?                     this help\n"
            "  exit | quit                  leave the console"
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_repl.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ryotenkai.py tests/test_repl.py
git commit -m "feat: RtkConsole REPL dispatcher and command handlers"
```

---

## Task 7: Interactive session sub-prompt

`interact_session` drives a session with injectable IO so it is testable without a live prompt.

**Files:**
- Modify: `ryotenkai.py`
- Modify: `tests/test_repl.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_repl.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_repl.py -v`
Expected: FAIL (`interact_session` undefined).

- [ ] **Step 3: Implement in ryotenkai.py**

Add this method to `RtkConsole`:

```python
    def interact_session(self, session_id, read_line, write_out):
        """Loop reading lines and running them in a session. Exits on
        'background'/'exit'/'quit'/'back', EOF, or KeyboardInterrupt. The
        session is left alive in the background."""
        write_out(f"[*] Interacting with session {session_id}. "
                  f"'background' or Ctrl-D to return.")
        while True:
            try:
                line = read_line()
            except (EOFError, KeyboardInterrupt):
                break
            if line is None:
                break
            line = line.strip()
            if line in ("background", "exit", "quit", "back"):
                break
            if not line:
                continue
            write_out(run_session_command(self.client, session_id, line))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_repl.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ryotenkai.py tests/test_repl.py
git commit -m "feat: interactive sessions -i sub-prompt"
```

---

## Task 8: prompt_toolkit wiring + argparse + __main__

Wire the REPL loop to `prompt_toolkit`, add the `interactive` subcommand, launch the REPL on no subcommand, and route every non-interactive subcommand through the data layer with JSON output preserved.

**Files:**
- Modify: `ryotenkai.py`

- [ ] **Step 1: Add prompt_toolkit imports and REPL runtime helpers**

Add near the top of `ryotenkai.py` (with the other imports):

```python
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import NestedCompleter
from prompt_toolkit.history import FileHistory
```

Add module-level constants:

```python
HISTORY_PATH = os.path.expanduser("~/.rtk_history")
BANNER = "RyoTenkai interactive console. Type 'help' for commands, 'exit' to quit."
```

Add a completer builder and the `cmdloop` method.

Completer builder (module-level function):

```python
def build_completer():
    return NestedCompleter.from_nested_dict({
        "use": None,
        "set": {"output": {"json": None, "table": None}},
        "unset": None,
        "options": None,
        "run": None,
        "exploit": None,
        "back": None,
        "jobs": {"-k": None},
        "sessions": {"-i": None},
        "generate": None,
        "connect": None,
        "help": None,
        "exit": None,
        "quit": None,
    })
```

Add `cmdloop` to `RtkConsole`:

```python
    def cmdloop(self, session=None):
        """Run the interactive loop using prompt_toolkit."""
        session = session or PromptSession(history=FileHistory(HISTORY_PATH),
                                           completer=build_completer())
        print(BANNER)
        while True:
            try:
                line = session.prompt(self.prompt_str())
            except EOFError:
                break
            except KeyboardInterrupt:
                continue
            output, keep_going, action = self.dispatch(line)
            if output:
                print(output)
            if action and action[0] == "interact":
                sid = action[1]
                self.interact_session(
                    sid,
                    read_line=lambda: session.prompt(f"session {sid} > "),
                    write_out=print,
                )
            if not keep_going:
                break
```

- [ ] **Step 2: Add the `interactive` subparser**

In `parse_arguments`, add a new subparser (alongside the existing ones, before `return parser.parse_args()`):

```python
    # Interactive REPL
    interactive_parser = subparsers.add_parser('interactive', help='Launch the interactive console.')
    interactive_parser.add_argument('--rpc-password', default=config.get('rpc_password', 'msfrpc'))
    interactive_parser.add_argument('--rpc-server', default=config.get('rpc_server', '127.0.0.1'))
    interactive_parser.add_argument('--rpc-port', type=int, default=int(config.get('rpc_port', 55552)))
    interactive_parser.add_argument('--rpc-ssl', action='store_true')
```

- [ ] **Step 3: Rewrite the `__main__` dispatch block**

Replace the entire `if __name__ == "__main__":` block with:

```python
def _launch_repl(args, config):
    rpc_password = getattr(args, "rpc_password", config.get("rpc_password", "msfrpc"))
    rpc_server = getattr(args, "rpc_server", config.get("rpc_server", "127.0.0.1"))
    rpc_port = int(getattr(args, "rpc_port", config.get("rpc_port", 55552)))
    rpc_ssl = getattr(args, "rpc_ssl", False)
    try:
        client = make_client(rpc_password, rpc_server, rpc_port, rpc_ssl)
    except Exception as e:
        print(json.dumps({"status": "error", "message": f"RPC connect failed: {e}"}))
        return
    conn_info = {"rpc_server": rpc_server, "rpc_port": rpc_port, "rpc_ssl": rpc_ssl}
    RtkConsole(client, conn_info).cmdloop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s - %(levelname)s - %(message)s")
    config = load_config("config.ini", "default")
    args = parse_arguments(config)

    if args.command in (None, "interactive"):
        _launch_repl(args, config)

    elif args.command == "start_rpc":
        start_rpc_server(args.rpc_password, args.rpc_port, args.rpc_ssl,
                         args.rpc_user, args.rpc_server)

    elif args.command == "run_module":
        client = make_client(args.rpc_password, args.rpc_server, args.rpc_port, args.rpc_ssl)
        options = parse_options(args.option)
        print(json.dumps(run_exploit(client, args.module, options, args.regex), indent=4))

    elif args.command == "get_jobs":
        client = make_client(args.rpc_password, args.rpc_server, args.rpc_port, args.rpc_ssl)
        print(json.dumps(get_jobs(client)))

    elif args.command == "get_sessions":
        client = make_client(args.rpc_password, args.rpc_server, args.rpc_port, args.rpc_ssl)
        print(json.dumps(get_sessions(client)))

    elif args.command == "run_command":
        client = make_client(args.rpc_password, args.rpc_server, args.rpc_port, args.rpc_ssl)
        print(json.dumps(access_session(client, args.session_id, args.commands), indent=4))

    elif args.command == "generate_payload":
        print(json.dumps(generate_payload(args.format, args.payload, args.lhost,
                                           args.lport, args.output_file), indent=4))
```

Note: `start_rpc_server` keeps its existing implementation and signature — it is unchanged by this plan.

- [ ] **Step 4: Run the full test suite**

Run: `pytest -v`
Expected: PASS (all tests across the three test files).

- [ ] **Step 5: Smoke-test the CLI imports and help**

Run: `python ryotenkai.py --help`
Expected: usage text listing subcommands including `interactive`.

Run: `python ryotenkai.py get_jobs --help`
Expected: usage for `get_jobs` (no traceback — confirms module imports cleanly with the new imports).

- [ ] **Step 6: Manual REPL smoke test (requires a running msfrpcd)**

Only if an `msfrpcd` is reachable:
Run: `python ryotenkai.py interactive --rpc-password msfrpc --rpc-server 127.0.0.1 --rpc-port 55552`
Expected: banner prints, prompt shows `rtk > `. Try `help`, `jobs`, `sessions`, `use exploit/multi/handler` → prompt becomes `rtk (exploit/multi/handler) > `, `set output json`, `exit`.

- [ ] **Step 7: Commit**

```bash
git add ryotenkai.py
git commit -m "feat: launch interactive REPL via prompt_toolkit; route subcommands through data layer"
```

---

## Self-Review

**Spec coverage:**
- msfconsole-style REPL → Tasks 6, 8 (dispatch, cmdloop, prompt).
- jobs/sessions/use/set/run/generate/connect/help/output-toggle commands → Task 6.
- Interactive `sessions -i` → Task 7.
- Table default + JSON toggle → Tasks 5, 6 (`_emit`, `set output`).
- Persistent client → Task 8 (`_launch_repl`, one `make_client`).
- Poll instead of fixed sleep → Task 3.
- `OPTION=VALUE` parse fix → Task 4.
- Launch REPL on no subcommand → Task 8.
- prompt_toolkit dep added → Task 1.
- Tests with mock client, no live msfrpcd → Tasks 1–7.
- Non-interactive JSON contract preserved → Task 8 (`__main__` prints `json.dumps`).

**Type/name consistency:** `make_client`, `get_jobs`, `get_sessions`, `kill_job`, `run_exploit`, `run_session_command`, `access_session`, `generate_payload`, `parse_options`, `render_table`, `format_jobs`, `format_sessions`, `format_exploit_result`, `RtkConsole.dispatch` (returns 3-tuple everywhere), `interact_session(session_id, read_line, write_out)`, `build_completer`, `cmdloop` — names used consistently across tasks and tests.

**Placeholder scan:** none — every code/test step contains complete code.

**Out-of-scope confirmed untouched:** Django, agent.py, Flask prototype.

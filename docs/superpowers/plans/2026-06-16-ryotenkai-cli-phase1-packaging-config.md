# RyoTenkai CLI Phase 1 — Packaging & Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `ryotenkai.py` `pip`-installable as an `rtk` command, and resolve every Metasploit RPC connection parameter through one helper with a documented precedence (CLI flag > env var > `config.ini` > built-in default), fixing the bug where `config.ini`'s `rpc_ssl` is ignored.

**Architecture:** Add a single `resolve_conn(args, config)` resolver plus a `DEFAULTS` constant, replacing the per-subparser hardcoded defaults scattered across `parse_arguments`. Make argparse RPC options default to `None` (so "not passed" is distinguishable) and give `--rpc-ssl` a tri-state via a mutually-exclusive `--rpc-ssl`/`--no-rpc-ssl` pair (3.8-safe). Extract a `main()` entrypoint and expose it as a `console_scripts` entry in a new `pyproject.toml`.

**Tech Stack:** Python 3.8+, argparse, configparser, `pymetasploit3`, `prompt_toolkit`, pytest (mock RPC client). setuptools build backend.

**Source spec:** `docs/superpowers/specs/2026-06-16-ryotenkai-cli-optimization-design.md` §3 (Phase 1).

---

## File Structure

- `ryotenkai.py` — add `DEFAULTS`, `ENV_KEYS`, `_parse_bool`, `resolve_conn`, `add_rpc_args`, `main`; refactor `parse_arguments` and `_launch_repl`; replace the `__main__` body. `os` is already imported.
- `tests/test_config.py` — **new**. Unit tests for `_parse_bool`, `resolve_conn` precedence, argparse defaults/tri-state SSL, and `main` dispatch.
- `pyproject.toml` — **new**. PEP 621 metadata + `[project.scripts] rtk = "ryotenkai:main"` + `py-modules = ["ryotenkai"]`.
- `requirements.txt` — unchanged (already pins `pymetasploit3`, `prompt_toolkit`, `pytest`).

**Out of scope (later phases / not Phase 1):** `start_rpc` keeps its own server-spawn args (it is not a client connection); adaptive polling, REPL completion, and new MSF verbs are Phases 2–4.

**Known limitation to document, not fix here:** `config.ini` is read as a cwd-relative path (`load_config("config.ini", ...)`). After `pip install`, running `rtk` from another directory won't find it — that is exactly why env-var support is part of this phase (env vars work from anywhere). XDG config-path search is deferred.

---

## Task 1: Connection resolver (`DEFAULTS`, `_parse_bool`, `resolve_conn`)

**Files:**
- Modify: `ryotenkai.py` (add constants + two functions near the other module-level helpers, after the `POLL_*`/`HISTORY_PATH` constants block, before `load_config`)
- Test: `tests/test_config.py` (new)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_config.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `AttributeError: module 'ryotenkai' has no attribute '_parse_bool'` (and `resolve_conn`).

- [ ] **Step 3: Write the implementation**

In `ryotenkai.py`, after the `HISTORY_PATH`/`BANNER` constants (around line 23) and before `load_config`, add:

```python
DEFAULTS = {
    "rpc_password": "msfrpc",
    "rpc_server": "127.0.0.1",
    "rpc_port": 55552,
    "rpc_ssl": False,
}

ENV_KEYS = {
    "rpc_password": "RTK_RPC_PASSWORD",
    "rpc_server": "RTK_RPC_SERVER",
    "rpc_port": "RTK_RPC_PORT",
    "rpc_ssl": "RTK_RPC_SSL",
}


def _parse_bool(value):
    """Coerce a config/env value to bool. None passes through unchanged."""
    if value is None or isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def resolve_conn(args, config):
    """Resolve RPC client params with precedence:
    CLI flag > env (RTK_RPC_*) > config.ini [default] > built-in default.

    `args` RPC attrs are None when the flag was not passed on the CLI;
    `config` is the dict returned by load_config(...). Returns the tuple
    (password, server, port, ssl).
    """
    def pick(key):
        cli = getattr(args, key, None)
        if cli is not None:
            return cli
        env = os.environ.get(ENV_KEYS[key])
        if env is not None:
            return env
        if key in config:
            return config[key]
        return DEFAULTS[key]

    password = str(pick("rpc_password"))
    server = str(pick("rpc_server"))
    port = int(pick("rpc_port"))
    ssl = _parse_bool(pick("rpc_ssl"))
    if ssl is None:
        ssl = DEFAULTS["rpc_ssl"]
    return password, server, port, ssl
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add ryotenkai.py tests/test_config.py
git commit -m "feat: add resolve_conn RPC param resolver with precedence

CLI flag > env (RTK_RPC_*) > config.ini > built-in default. Adds
DEFAULTS, ENV_KEYS, _parse_bool. Foundation for single-source-of-truth
connection params (Phase 1)."
```

---

## Task 2: argparse RPC options — `None` defaults + tri-state SSL

**Files:**
- Modify: `ryotenkai.py` — add `add_rpc_args(parser)` helper; use it in the `run_module`, `get_jobs`, `get_sessions`, `run_command`, and `interactive` subparsers in `parse_arguments` (replacing the four repeated `--rpc-*` lines in each). Leave `start_rpc` and `generate_payload` untouched.
- Test: `tests/test_config.py` (extend)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_config.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_config.py -k parse_arguments -v`
Expected: FAIL — `args.rpc_password` is currently a config-derived string default (not `None`), and `--no-rpc-ssl` is an unrecognized argument (`SystemExit`).

- [ ] **Step 3: Write the implementation**

In `ryotenkai.py`, add this helper just above `parse_arguments` (after `load_config`):

```python
def add_rpc_args(parser):
    """Attach the shared RPC client flags. Defaults are None so resolve_conn
    can apply CLI > env > config > default precedence; --rpc-ssl is tri-state."""
    parser.add_argument('--rpc-password', default=None,
                        help='Metasploit RPC password (env RTK_RPC_PASSWORD / config / default).')
    parser.add_argument('--rpc-server', default=None,
                        help='Metasploit RPC server address.')
    parser.add_argument('--rpc-port', type=int, default=None,
                        help='Metasploit RPC server port.')
    ssl = parser.add_mutually_exclusive_group()
    ssl.add_argument('--rpc-ssl', dest='rpc_ssl', action='store_true', default=None,
                     help='Use SSL for the RPC connection.')
    ssl.add_argument('--no-rpc-ssl', dest='rpc_ssl', action='store_false',
                     help='Disable SSL for the RPC connection.')
```

Then, in `parse_arguments`, replace the four `--rpc-*` `add_argument` lines in each of these subparsers with a single `add_rpc_args(<parser>)` call:

- `run_parser` (keep its `module` positional and `--option`/`--regex`): after `--regex`, replace lines adding `--rpc-password/--rpc-server/--rpc-port/--rpc-ssl` with `add_rpc_args(run_parser)`.
- `jobs_parser`: replace its four `--rpc-*` lines with `add_rpc_args(jobs_parser)`.
- `sessions_parser`: replace its four `--rpc-*` lines with `add_rpc_args(sessions_parser)`.
- `access_parser` (keep `session_id` and `commands` positionals): replace its four `--rpc-*` lines with `add_rpc_args(access_parser)`.
- `interactive_parser`: replace its four `--rpc-*` lines with `add_rpc_args(interactive_parser)`.

Leave `rpc_parser` (start_rpc) and `venom_parser` (generate_payload) exactly as they are.

- [ ] **Step 4: Run the full suite to verify pass + no regressions**

Run: `pytest -q`
Expected: PASS — previously 37 + Task 1's 5 + 3 new = 45 tests; all green.

- [ ] **Step 5: Commit**

```bash
git add ryotenkai.py tests/test_config.py
git commit -m "refactor: RPC argparse defaults to None; tri-state --rpc-ssl

DRY shared client flags via add_rpc_args; None defaults let resolve_conn
own precedence. Adds --no-rpc-ssl so config/env can supply the SSL
default (3.8-safe mutually-exclusive group)."
```

---

## Task 3: `main()` entrypoint routed through `resolve_conn`

**Files:**
- Modify: `ryotenkai.py` — rewrite `_launch_repl` to use `resolve_conn`; extract the `if __name__ == "__main__"` body into `def main()`, routing each client-building branch through `resolve_conn`; reduce the guard to `main()`.
- Test: `tests/test_config.py` (extend)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_config.py`:

```python
def test_main_get_jobs_prints_json(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["ryotenkai.py", "get_jobs"])
    monkeypatch.setattr(ryotenkai, "load_config", lambda *_a, **_k: {})
    fake = MagicMock()
    fake.jobs.list = {"0": "Exploit: multi/handler"}
    monkeypatch.setattr(ryotenkai, "make_client", lambda *a, **k: fake)
    ryotenkai.main()
    assert '"0": "Exploit: multi/handler"' in capsys.readouterr().out


def test_main_is_callable():
    assert callable(ryotenkai.main)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_config.py -k main -v`
Expected: FAIL — `AttributeError: module 'ryotenkai' has no attribute 'main'`.

- [ ] **Step 3: Write the implementation**

First, rewrite `_launch_repl` (currently ~lines 537-548) to:

```python
def _launch_repl(args, config):
    rpc_password, rpc_server, rpc_port, rpc_ssl = resolve_conn(args, config)
    try:
        client = make_client(rpc_password, rpc_server, rpc_port, rpc_ssl)
    except Exception as e:
        print(json.dumps({"status": "error", "message": f"RPC connect failed: {e}"}))
        return
    conn_info = {"rpc_server": rpc_server, "rpc_port": rpc_port, "rpc_ssl": rpc_ssl}
    RtkConsole(client, conn_info).cmdloop()
```

Then replace the entire `if __name__ == "__main__":` block (currently ~lines 551-583) with a `main()` function plus a thin guard:

```python
def main():
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
        pw, srv, port, ssl = resolve_conn(args, config)
        client = make_client(pw, srv, port, ssl)
        options = parse_options(args.option)
        print(json.dumps(run_exploit(client, args.module, options, args.regex), indent=4))

    elif args.command == "get_jobs":
        pw, srv, port, ssl = resolve_conn(args, config)
        client = make_client(pw, srv, port, ssl)
        print(json.dumps(get_jobs(client)))

    elif args.command == "get_sessions":
        pw, srv, port, ssl = resolve_conn(args, config)
        client = make_client(pw, srv, port, ssl)
        print(json.dumps(get_sessions(client)))

    elif args.command == "run_command":
        pw, srv, port, ssl = resolve_conn(args, config)
        client = make_client(pw, srv, port, ssl)
        print(json.dumps(access_session(client, args.session_id, args.commands), indent=4))

    elif args.command == "generate_payload":
        print(json.dumps(generate_payload(args.format, args.payload, args.lhost,
                                           args.lport, args.output_file), indent=4))


if __name__ == "__main__":
    main()
```

(Note: `start_rpc` reads `args.rpc_password`/`args.rpc_port`/`args.rpc_ssl` from its own subparser, which still defines those with server-spawn defaults — unchanged. The tri-state `--rpc-ssl` change in Task 2 did not touch `rpc_parser`.)

- [ ] **Step 4: Run the full suite to verify pass**

Run: `pytest -q`
Expected: PASS — 47 tests green (45 + 2 new).

- [ ] **Step 5: Commit**

```bash
git add ryotenkai.py tests/test_config.py
git commit -m "refactor: extract main(); route client commands through resolve_conn

_launch_repl and every client-building subcommand now resolve connection
params via resolve_conn, giving one precedence rule. main() is the
console_script target (Task 4)."
```

---

## Task 4: `pyproject.toml` + `rtk` console entrypoint

**Files:**
- Create: `pyproject.toml`
- Test: `tests/test_config.py` already asserts `main` is callable (Task 3); add a packaging smoke check below (manual, since entrypoint resolution is an install-time concern).

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "ryotenkai"
version = "0.1.0"
description = "Lab-grade Metasploit CLI/REPL and C2 framework for authorized red-team work."
readme = "README.md"
requires-python = ">=3.8"
license = { text = "Apache-2.0" }
authors = [{ name = "d3vn0mi" }]
dependencies = ["pymetasploit3", "prompt_toolkit"]

[project.optional-dependencies]
test = ["pytest"]

[project.scripts]
rtk = "ryotenkai:main"

[tool.setuptools]
py-modules = ["ryotenkai"]
```

- [ ] **Step 2: Verify the editable install exposes `rtk`**

Run:
```bash
pip install -e .
rtk --help
```
Expected: `pip install -e .` succeeds; `rtk --help` prints the argparse usage (subcommands listed) and exits 0. This proves the `ryotenkai:main` entrypoint resolves.

- [ ] **Step 3: Verify the test suite still passes under the installed package**

Run: `pytest -q`
Expected: PASS — 47 tests green (no test references the install; this confirms no import breakage from the packaging metadata).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "build: add pyproject.toml with rtk console entrypoint

PEP 621 metadata, Apache-2.0, py-modules=[ryotenkai], console_script
rtk=ryotenkai:main. Enables pip install . (Phase 1 complete)."
```

---

## Task 5: Update docs for the new install + config precedence

**Files:**
- Modify: `README.md` — Quickstart can now use `pip install -e .` + `rtk <cmd>`; document env vars and the precedence rule; soften the `rpc_ssl` caveat (now fixed via `--rpc-ssl`/`--no-rpc-ssl` + config).
- Modify: `CLAUDE.md` — update the "config.ini does not feed rpc_ssl" known-mismatch entry (now resolved) and note the `rtk` entrypoint.

- [ ] **Step 1: Update README Quickstart and Configuration**

In `README.md` Quickstart, after the deps step, add an install line and switch examples to `rtk`:

```sh
pip install -e .        # exposes the `rtk` command
rtk interactive         # or: python ryotenkai.py interactive
```

In the Configuration section, replace the `rpc_ssl` caveat block with a precedence note:

```markdown
**Connection precedence:** `--rpc-* flag` > env (`RTK_RPC_PASSWORD`, `RTK_RPC_SERVER`,
`RTK_RPC_PORT`, `RTK_RPC_SSL`) > `config.ini [default]` > built-in default.
SSL is now config/env-driven; force it per-run with `--rpc-ssl` / `--no-rpc-ssl`.
Note: `rtk` reads `./config.ini` from the current directory — use the env vars
when running from elsewhere.
```

- [ ] **Step 2: Update CLAUDE.md known-mismatch entry**

In `CLAUDE.md` under "Known mismatches", change the `config.ini [default] does not feed rpc_ssl` bullet to past tense / resolved:

```markdown
- **`rpc_ssl` is now config/env-driven (resolved).** `resolve_conn` applies
  CLI > env (`RTK_RPC_*`) > `config.ini` > default; `--rpc-ssl`/`--no-rpc-ssl`
  force it per-run. The CLI is installable as `rtk` via `pyproject.toml`.
```

- [ ] **Step 3: Verify docs reference real behavior**

Run: `rtk --help` and confirm the flags named in the docs (`--rpc-ssl`, `--no-rpc-ssl`) appear in a subcommand's help, e.g. `rtk get_jobs --help`.
Expected: both flags listed.

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: document rtk install, RPC precedence, resolved rpc_ssl"
```

---

## Self-Review

**Spec coverage (spec §3 Phase 1):**
- "`pip install .` yields an `rtk` command" → Task 4 (pyproject + console_script) ✓
- "single resolver with documented precedence CLI > env > config > default" → Task 1 (`resolve_conn`) + Task 3 (routing) ✓
- "replace scattered `config.get(..., 55552)` with one DEFAULTS dict" → Task 1 (`DEFAULTS`) + Task 2 (`add_rpc_args` removes the per-subparser defaults) ✓
- "extract `main()` for the console_script target" → Task 3 ✓
- "fix `rpc_ssl`: tri-state flag so config/env supply default" → Task 2 (`--rpc-ssl`/`--no-rpc-ssl`) + Task 1 (`_parse_bool`) ✓
- "env-var support `RTK_RPC_*`" → Task 1 (`ENV_KEYS`) ✓
- Invariant "JSON stdout contract preserved" → Task 3 keeps every `print(json.dumps(...))` branch verbatim ✓
- Invariant "suite stays green / new behavior gets tests" → Tasks 1–4 add `tests/test_config.py`; full-suite run in Tasks 2/3/4 ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code; every command states expected output. ✓

**Type consistency:** `resolve_conn` returns `(password, server, port, ssl)` and is unpacked identically in `_launch_repl` and every `main()` branch. `add_rpc_args` sets dest `rpc_ssl` matching `resolve_conn`'s `getattr(args, "rpc_ssl")` and the Task-2 tests. `_parse_bool` returns `None` only for `None` input; `resolve_conn` guards the residual `None` → `DEFAULTS["rpc_ssl"]`. ✓

**Test count trail:** 37 baseline → +5 (Task 1) = 42 → +3 (Task 2) = 45 → +2 (Task 3) = 47, asserted in Tasks 2/3/4. ✓

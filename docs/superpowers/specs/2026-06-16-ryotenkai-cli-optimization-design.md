# RyoTenkai CLI Optimization — Design

**Date:** 2026-06-16
**Author:** d3vn0mi
**Scope:** `ryotenkai.py` (non-interactive subcommands + interactive `RtkConsole` REPL). Django C2 (`ryotenkai_gui/`) and the beacon (`agent.py`) are explicitly out of scope and tracked separately on the roadmap.
**Status:** Design approved; implementation deferred to a later session (this session produces docs + this plan only).

---

## 1. Purpose

`ryotenkai.py` is the most mature component in the repo: layered (connection → pure data functions → presentation → REPL), unit-tested (37 passing tests, mock RPC client), and contract-bound (non-interactive subcommands emit JSON to stdout for downstream Ansible parsing). This document plans four optimization axes without breaking that JSON contract or the test suite.

The four axes map directly to roadmap Phases 1–4:

| Phase | Axis | Goal |
|-------|------|------|
| 1 | Packaging & config | `pip install`, `rtk` entrypoint, one source of truth for connection params |
| 2 | RPC perf & reliability | Faster, more robust polling and reconnect |
| 3 | REPL UX | Live completion, search, color, sharper errors |
| 4 | Metasploit coverage | Module search/info, session kill/upgrade, db/creds/loot |

**Non-negotiable invariants (apply to every phase):**
- Non-interactive subcommands keep emitting machine-readable JSON on stdout (`json.dumps`). Any *new* subcommand must also emit JSON.
- Pure data functions keep *returning* data and never print; presentation stays in the `format_*` / `render_table` layer.
- The mock-RPC test suite stays green; new behavior ships with new tests.

---

## 2. Current state (baseline, from code read)

- **Connection:** `make_client()` builds a fresh `MsfRpcClient` per non-interactive invocation (new login each run). The REPL builds one client and reuses it for the session. No reconnect-on-failure anywhere.
- **Config / params:** `load_config()` reads `config.ini [default]`. Each subparser sets its own defaults via `config.get(...)`, with a hardcoded fallback of port `55552` scattered across ~6 call sites (the committed `config.ini` uses `55559`, so config wins only when present). `--rpc-ssl` is `store_true` and is **not** wired to `config.ini`'s `rpc_ssl`, so `rpc_ssl = True` in config is silently ignored. No env-var support. No precedence rule is written down.
- **Polling:** `_read_console` settles one interval, then loops `read()` every fixed `POLL_INTERVAL=0.5s` until not busy or `CONSOLE_TIMEOUT=15s`. `_read_session` uses a quiet-round counter (`SESSION_QUIET_ROUNDS=2`) and `SESSION_TIMEOUT=10s`. Intervals/timeouts are module constants, not configurable. No adaptive backoff.
- **Completion:** `build_completer()` returns a *static* `NestedCompleter`. `use` maps to `None` (no module names), and module options are never completed. Output of `sessions`/`jobs` is not cached.
- **Coverage:** subcommands = `run_module`, `get_jobs`, `get_sessions`, `run_command`, `generate_payload`, `start_rpc`, `interactive`. REPL verbs = `use/set/unset/options/run/exploit/back/jobs[-k]/sessions[-i]/generate/connect/help/exit`. No `search`, no `info`, no session kill/upgrade, no db/creds/loot access.
- **Entrypoint:** run as `python ryotenkai.py <subcommand>`. No `pyproject.toml`, no console_script, not installable.

---

## 3. Phase 1 — Packaging & config

**Target:** `pip install .` yields an `rtk` command; one resolver decides every connection parameter with a documented precedence; `rpc_ssl` config value is honored.

**Changes:**
- Add `pyproject.toml` (PEP 621). Keep `ryotenkai.py` as a top-level module (`py-modules = ["ryotenkai"]`) to avoid churning imports in `tests/`. Define `[project.scripts] rtk = "ryotenkai:main"`.
- Extract a `main()` function from the `if __name__ == "__main__"` block so the console_script has a target. The `__main__` guard just calls `main()`.
- Add a single `resolve_conn(args, config)` helper returning `(password, server, port, ssl)` with precedence: **CLI flag > env var (`RTK_RPC_*`) > `config.ini [default]` > built-in default constant**. Replace the scattered `config.get(..., 55552)` defaults with one `DEFAULTS` dict.
- Fix `rpc_ssl`: replace `store_true` with a tri-state (`--rpc-ssl` / `--no-rpc-ssl`, default `None`) so the resolver can fall back to config/env. This closes the documented "config `rpc_ssl` ignored" bug.

**Tradeoffs:**
- Keeping a single-file module (vs. a `ryotenkai/` package) is simplest and preserves test imports; revisit only if the file is split later.
- Tri-state SSL flag is slightly more argparse boilerplate but is the only correct way to let config/env supply the default.

**Test impact:** new `tests/test_config.py` — precedence (flag beats env beats config beats default), SSL tri-state resolution. Existing tests unaffected (resolver is additive).

---

## 4. Phase 2 — RPC perf & reliability

**Target:** polling that returns sooner on fast commands without truncating slow ones; survive a dropped RPC socket; intervals/timeouts configurable.

**Changes:**
- **Adaptive polling:** keep the one-interval settle (it prevents first-read truncation — do not remove), then back off the interval geometrically (e.g. 0.2s → 0.4s → 0.8s, capped) instead of a flat 0.5s. Fast commands return in ~0.2s; long jobs still poll to timeout.
- **Configurable timing:** read `poll_interval` / `console_timeout` / `session_timeout` from `config.ini [default]` via the Phase-1 resolver; constants become defaults.
- **Reconnect:** wrap client calls in a thin guard that, on a transport-level failure (dead socket / auth-token expiry), attempts exactly one `make_client()` reconnect before surfacing the error as the existing `{"status":"error",...}` shape. No infinite retry loops.
- **Caching (REPL only):** optional short-TTL cache for `jobs`/`sessions` list to avoid re-querying on rapid repeats; explicit refresh on mutating commands (`jobs -k`, `sessions -k`).

**Tradeoffs:**
- Adaptive backoff trades a few hundred ms of worst-case latency on a slow first chunk for much faster common-case returns. Backoff cap keeps long jobs correct.
- One-shot reconnect (not N retries) avoids masking a genuinely-down msfrpcd as a hang.

**Test impact:** mock-client tests for backoff sequence, reconnect-once-then-fail, and cache invalidation on mutation. Settle/timeout branches already covered — extend, don't replace.

---

## 5. Phase 3 — REPL UX

**Target:** the REPL feels like `msfconsole` — real completion, search, color, helpful errors.

**Changes:**
- **Live completion:** build the completer dynamically from the connected client (`client.modules.exploits/payloads/post/...`) so `use <TAB>` lists real modules; after `use <module>`, complete its option names for `set <TAB>`. Module lists are large/slow to fetch — fetch once, **cache** on the `RtkConsole` instance, lazy-load on first `use`/`search`.
- **`search <term>`:** filter the cached module list by substring; render via `render_table` (table mode) or JSON.
- **Color:** ANSI-color status markers (`[*]`/`[!]`/`[+]`) and table headers via prompt_toolkit styling; honor a `set color on|off` toggle and `NO_COLOR`.
- **History search:** `FileHistory` already enables Ctrl-R; add `AutoSuggestFromHistory` and document the shortcut in `help`.
- **Sharper errors:** map common `MsfRpcError` strings (auth failure, unknown module, no such session) to one-line hints instead of raw exception text.

**Tradeoffs:**
- First `use`/`search` pays a one-time module-list fetch (can be seconds against a real msfrpcd). Caching + lazy-load confines the cost to first use; a `[*] indexing modules...` notice manages expectation.
- Color must degrade cleanly on non-TTY / `NO_COLOR` to keep output readable in pipes.

**Test impact:** tests for the dynamic completer builder (mock `client.modules`), `search` filtering, error-message mapping. Color path tested for the no-color fallback.

---

## 6. Phase 4 — Metasploit coverage

**Target:** common operator actions available without dropping to raw msfconsole.

**Changes (each as a data function + REPL verb + non-interactive subcommand where it fits):**
- **`info <module>`** — module metadata/options.
- **`sessions -k <id>` / `sessions -K`** — kill one / all sessions (data fn `kill_session`, mirrors existing `kill_job`).
- **session upgrade** — `sessions -u <id>`: run `post/multi/manage/shell_to_meterpreter` against a shell session.
- **db read** — `creds` / `loot` / `hosts` read-only views when an msf database is connected; degrade gracefully with a clear message when it is not.

**Tradeoffs:**
- DB features depend on a connected msf database; all must guard for "db not available" and return the standard error shape rather than throwing.
- Session upgrade is inherently best-effort (depends on target); report job/handler status, do not block on success.

**Test impact:** data-layer tests (`kill_session`, `info`, db-not-available guard) and REPL-dispatch tests, all mock-based — no live msfrpcd required, consistent with current suite.

---

## 7. Sequencing & rationale

Build in phase order: **1 → 2 → 3 → 4**.
- Phase 1 is the foundation — fixes the live `rpc_ssl`/config bug, makes the tool installable, and gives later phases one place to read timing/connection settings.
- Phase 2 hardens the transport every other feature rides on.
- Phase 3 and Phase 4 are additive feature work and could interleave, but completion (3) benefits from the cached module list that `search`/`info` (4) also use, so 3 lands first.

Each phase is independently shippable, leaves the suite green, and preserves the JSON stdout contract. After this design is approved, `writing-plans` turns **Phase 1** into the first executable implementation plan.

---

## 8. Out of scope (tracked elsewhere)

- Django C2 fixes (agent result URL, task-pull loop, `timezone` NameError, template name, cred reconciliation) — roadmap Phase 5+.
- Beacon (`agent.py`) and the Flask prototype (`ryotenkai_c2.py`) — not part of CLI optimization.
- Encryption / auth on the C2 REST API — C2 roadmap, not CLI.

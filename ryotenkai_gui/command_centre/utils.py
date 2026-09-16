import requests
from pymetasploit3.msfrpc import MsfRpcClient
from .models import Beacon, Task


def make_client():
    """Build a Metasploit RPC client tolerant of non-UTF-8 RPC output.

    decode_error_handling='backslashreplace' stops a single non-UTF-8 byte in
    Windows console/filesystem output from raising UnicodeDecodeError inside
    pymetasploit3 (its default 'strict' handler) and killing the call; invalid
    bytes render as visible \\xNN escapes instead. Single choke point so every
    Django-side Metasploit call is hardened the same way.
    """
    return MsfRpcClient('msfpassword', server='127.0.0.1', port=55552,
                        decode_error_handling='backslashreplace')


def assign_task_to_beacon(hostname, command):
    """Assign a task to a beacon directly (internal method, no HTTP request)."""
    try:
        beacon = Beacon.objects.get(hostname=hostname)
        task = Task.objects.create(beacon=beacon, command=command)
        print(f"Task assigned successfully with ID: {task.id}")
    except Beacon.DoesNotExist:
        print("Beacon not found.")


def run_metasploit_module(module, options):
    # Logic to run a Metasploit module via the existing Ryotenkai tool
    client = make_client()
    console = client.consoles.console()
    console.write(f'use {module}\n')
    for option in options:
        console.write(f'set {option}\n')
    console.write('run\n')


def get_jobs():
    # Logic to retrieve active Metasploit jobs
    client = make_client()
    return client.jobs.list


def get_sessions():
    # Logic to retrieve active Metasploit sessions
    client = make_client()
    return client.sessions.list

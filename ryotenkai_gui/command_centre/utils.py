import requests
from pymetasploit3.msfrpc import MsfRpcClient
from .models import Beacon, Task


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
    client = MsfRpcClient('msfpassword', server='127.0.0.1', port=55552)
    console = client.consoles.console()
    console.write(f'use {module}\n')
    for option in options:
        console.write(f'set {option}\n')
    console.write('run\n')


def get_jobs():
    # Logic to retrieve active Metasploit jobs
    client = MsfRpcClient('msfpassword', server='127.0.0.1', port=55552)
    return client.jobs.list


def get_sessions():
    # Logic to retrieve active Metasploit sessions
    client = MsfRpcClient('msfpassword', server='127.0.0.1', port=55552)
    return client.sessions.list

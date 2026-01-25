```
 ____            _____          _         _    ____ ____  
|  _ \ _   _  __|_   _|__ _ __ | | ____ _(_)  / ___|___ \ 
| |_) | | | |/ _ \| |/ _ \ '_ \| |/ / _` | | | |     __) |
|  _ <| |_| | (_) | |  __/ | | |   < (_| | | | |___ / __/ 
|_| \_\\__, |\___/|_|\___|_| |_|_|\_\__,_|_|  \____|_____|
       |___/                                              
```

# Ryotenkai Command Centre

## Overview
The Ryotenkai Command Centre is a Django-based web application that serves as a central control interface for managing beacons, running Metasploit modules, monitoring jobs and sessions, and managing tasks related to offensive security operations. This solution uses a backend API to handle beacon check-ins, task assignments, and agent communications, making it ideal for centralized management of a distributed security operation.

## Features
- **Dashboard View**: Provides a comprehensive overview of active beacons, Metasploit jobs, sessions, and tasks.
- **Beacon Management**: Allows for active tracking and management of beacons, with real-time status updates.
- **Task Assignment**: Assign commands to beacons using a REST API and monitor task progress and outputs.
- **Metasploit Integration**: Run Metasploit modules via the command centre and monitor active jobs and sessions.
- **Agent Check-In**: Beacons periodically check in to update their status and keep the server informed of their availability.

## Structure
- **Backend**: Django framework for handling HTTP requests, interacting with the database, and managing all core functionalities.
- **Frontend**: HTML templates that display dashboards, active jobs, sessions, beacons, and task lists.
- **Agent**: Python-based beacon agent that connects to the C2 server, checks in, and executes assigned tasks.

## Installation
### Prerequisites
- Python 3.8 or higher
- Django 4.0 or higher
- pymetasploit3 (for interacting with Metasploit)
- Requests library for agent operations

### Installation Steps
1. Clone the repository:
   ```sh
   git clone https://github.com/yourusername/ryotenkai.git
   cd ryotenkai
   ```
2. Set up a virtual environment:
   ```sh
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
4. Apply database migrations:
   ```sh
   python manage.py makemigrations
   python manage.py migrate
   ```
5. Run the server:
   ```sh
   python manage.py runserver
   ```
6. Access the application at `http://127.0.0.1:8000/`.

## Usage
### Dashboard View
- **URL**: `/`
- **Purpose**: Displays active beacons, Metasploit jobs, active sessions, and tasks.

### Beacon Check-In Endpoint
- **URL**: `/api/check_in/`
- **Method**: POST
- **Description**: Beacons use this endpoint to periodically check in and update their status.
- **Payload Example**:
  ```json
  {
      "hostname": "test-beacon"
  }
  ```

### Assign Task to Beacon
- **URL**: `/api/assign_task/`
- **Method**: POST
- **Description**: Assigns a command task to a specific beacon.
- **Payload Example**:
  ```json
  {
      "hostname": "test-beacon",
      "command": "ifconfig"
  }
  ```

### Receive Task Results
- **URL**: `/api/receive_result/`
- **Method**: POST
- **Description**: Beacons use this endpoint to send back the results of a completed task.
- **Payload Example**:
  ```json
  {
      "task_id": 1,
      "result": "Command output here"
  }
  ```

## Agent
The beacon agent is a Python script that connects to the command centre, checks in periodically, retrieves tasks, and sends task results.

### Agent Command
Run the beacon agent with the following command:
```sh
python agent.py --c2-ip 127.0.0.1 --c2-port 8000 --min-sleep 60 --max-sleep 120
```
- **c2-ip**: IP address of the C2 server.
- **c2-port**: Port of the C2 server.
- **min-sleep, max-sleep**: The agent sleeps for a random interval between these values before the next check-in.

## Models
### Beacon
- **hostname**: The unique identifier for the beacon.
- **last_checkin**: Timestamp of the last time the beacon checked in.
- **status**: Current status of the beacon (e.g., active, dormant).

### Task
- **beacon**: The beacon assigned to this task.
- **command**: Command to be run by the beacon.
- **result**: Output of the command.
- **status**: Status of the task (e.g., pending, completed).

### Session
- **session_id**: The ID of the session.
- **hostname**: Hostname associated with the session.
- **status**: Status of the session (e.g., active, closed).

### Job
- **job_id**: The ID of the Metasploit job.
- **module**: Metasploit module being run.
- **status**: Status of the job.

## API Endpoints
- `/api/check_in/` - Beacon check-in endpoint.
- `/api/assign_task/` - Assigns a command to a beacon.
- `/api/receive_result/` - Endpoint to receive results from beacons.

## Roadmap
1. **Enhanced Beacon Management**: Integrate beacon geolocation and status visualization on the dashboard.
2. **Advanced Task Scheduling**: Allow scheduling of tasks for beacons at specific times.
3. **Beacon Grouping**: Ability to group beacons and assign tasks to groups for parallel execution.
4. **Scalable Infrastructure**: Optimize the application to support hundreds or thousands of beacons, using scalable storage solutions like Redis or PostgreSQL and load balancing.
5. **Redundancy and Failover**: Implement redundancy for critical components to ensure continuity of command and control even in case of server failure.
6. **Encrypted Communication**: Implement end-to-end encryption for communication between the agent and the server, improving the security of the C2 network.
7. **Beacon Evasion Techniques**: Add techniques for beacon evasion, such as randomized sleep times, protocol obfuscation, and anti-detection mechanisms.
8. **User Role Management**: Add user roles and permissions for multi-operator usage, similar to other advanced C2 frameworks.
9. **Real-Time Notifications**: Integrate WebSockets or similar technologies to provide real-time updates on beacon activity, jobs, and sessions.
10. **Advanced Post-Exploitation Modules**: Add support for advanced post-exploitation modules, such as lateral movement, credential harvesting, and persistence.
11. **Integration with Threat Intelligence Feeds**: Allow beacons to gather and report threat intelligence to assist operators in making real-time decisions.
12. **Campaign Management**: Provide functionality to manage and track campaigns, where users can track multi-stage operations.
13. **Cross-Platform Agent Support**: Develop agents for Windows, macOS, and Linux to provide broader support for various target environments.

## Contributing
Contributions are welcome! Please create an issue or pull request if you have any ideas or improvements.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.

## Contact
For any inquiries, please contact info@isomarakis.eu.


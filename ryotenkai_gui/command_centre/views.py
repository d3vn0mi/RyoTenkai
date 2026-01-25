from django.shortcuts import render, redirect
from .models import Beacon, Task, Session, Job
from .utils import assign_task_to_beacon, run_metasploit_module, get_jobs, get_sessions
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json


def home(request):
    """Dashboard view."""
    beacons = Beacon.objects.all()
    jobs = Job.objects.all()
    sessions = Session.objects.all()
    tasks = Task.objects.all().order_by('-created_at')

    context = {
        'beacons': beacons,
        'jobs': jobs,
        'sessions': sessions,
        'tasks': tasks,
    }
    return render(request, 'command_centre/home.html', context)

@csrf_exempt
def beacons(request):
    """View and manage beacons."""
    active_beacons = Beacon.objects.all()
    return render(request, 'command_centre/beacons.html', {'active_beacons': active_beacons})


@csrf_exempt
def tasks(request):
    """View all tasks and their outputs."""
    tasks = Task.objects.all().order_by('-created_at')
    context = {
        'tasks': tasks,
    }
    return render(request, 'command_centre/tasks.html', context)


@csrf_exempt
def assign_task(request):
    """REST API endpoint to assign a task to a beacon."""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            hostname = data.get('hostname')
            command = data.get('command')

            if hostname and command:
                assign_task_to_beacon(hostname, command)
                return JsonResponse({'status': 'success', 'message': 'Task assigned successfully'}, status=200)
            else:
                return JsonResponse({'status': 'error', 'message': 'Hostname or command missing'}, status=400)
        
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


@csrf_exempt
def check_in(request):
    """REST API endpoint for beacons to check in."""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            hostname = data.get('hostname')

            if hostname:
                # Get or create the Beacon object to track its status
                beacon, created = Beacon.objects.get_or_create(hostname=hostname)
                beacon.last_checkin = timezone.now()
                beacon.status = 'active'
                beacon.save()
                return JsonResponse({'status': 'success', 'message': 'Beacon checked in successfully'}, status=200)
            else:
                return JsonResponse({'status': 'error', 'message': 'Hostname missing'}, status=400)
        
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)

@csrf_exempt
def receive_result(request):
    """REST API endpoint to receive results from a beacon."""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            task_id = data.get('task_id')
            result = data.get('result')

            if task_id and result is not None:
                task = Task.objects.get(id=task_id)
                task.result = result
                task.status = 'completed'
                task.save()
                return JsonResponse({'status': 'success', 'message': 'Result received and task updated'}, status=200)
            else:
                return JsonResponse({'status': 'error', 'message': 'Task ID or result missing'}, status=400)

        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)
        except Task.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Task not found'}, status=404)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


@csrf_exempt
def run_module(request):
    """Run a Metasploit module."""
    if request.method == "POST":
        module = request.POST['module']
        options = request.POST.getlist('options')
        run_metasploit_module(module, options)
        return redirect('run_module')

    return render(request, 'command_centre/run_module.html')

def jobs_sessions(request):
    """Monitor jobs and sessions."""
    jobs = get_jobs()
    sessions = get_sessions()

    context = {
        'jobs': jobs,
        'sessions': sessions
    }
    return render(request, 'command_centre/jobs_sessions.html', context)

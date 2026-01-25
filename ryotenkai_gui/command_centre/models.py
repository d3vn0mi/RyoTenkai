# Create your models here.
from django.db import models

class Beacon(models.Model):
    hostname = models.CharField(max_length=255, unique=True)
    last_checkin = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=50, default='active')  # active, dormant, terminated

    def __str__(self):
        return self.hostname

class Task(models.Model):
    beacon = models.ForeignKey(Beacon, on_delete=models.CASCADE, related_name='tasks')
    command = models.CharField(max_length=255)
    result = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, default='pending')  # pending, completed, failed

    def __str__(self):
        return f"{self.command} for {self.beacon.hostname}"


class Session(models.Model):
    session_id = models.IntegerField(unique=True)
    hostname = models.CharField(max_length=255)
    session_type = models.CharField(max_length=50)  # e.g., meterpreter, shell
    status = models.CharField(max_length=50, default='active')  # active, closed
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Session {self.session_id} on {self.hostname}"


class Job(models.Model):
    job_id = models.IntegerField(unique=True)
    module = models.CharField(max_length=255)
    status = models.CharField(max_length=50, default='running')  # running, completed, failed
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Job {self.job_id} running {self.module}"

from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('beacons/', views.beacons, name='beacons'),
    path('run_module/', views.run_module, name='run_module'),
    path('jobs_sessions/', views.jobs_sessions, name='jobs_sessions'),
    path('api/assign_task/', views.assign_task, name='assign_task'), 
    path('api/tasks/', views.tasks, name='tasks'),  
    path('api/receive_result/', views.receive_result, name='receive_result'),  
    path('api/check_in/', views.check_in, name='check_in'),  
]
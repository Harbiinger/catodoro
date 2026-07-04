from django.urls import path

from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('tasks/create/', views.create_task, name='create_task'),
    path('tasks/<int:task_id>/pomodoro/', views.complete_pomodoro, name='complete_pomodoro'),
    path('tasks/<int:task_id>/complete/', views.complete_task, name='complete_task'),
    path('tasks/<int:task_id>/abandon/', views.abandon_task, name='abandon_task'),
]

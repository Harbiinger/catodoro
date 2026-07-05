from django.urls import path

from . import views

urlpatterns = [
    path('staff/', views.dashboard, name='admin_dashboard'),
]

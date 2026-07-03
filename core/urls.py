from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .forms import EmailAuthenticationForm

urlpatterns = [
    # auth
    path('accounts/login/',
         auth_views.LoginView.as_view(
             template_name='registration/login.html',
             authentication_form=EmailAuthenticationForm,
         ),
         name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('accounts/register/', views.register, name='register'),

    # game
    path('', views.dashboard, name='dashboard'),
    path('setup/', views.setup, name='setup'),
    path('tasks/create/', views.create_task, name='create_task'),
    path('tasks/<int:task_id>/pomodoro/', views.complete_pomodoro, name='complete_pomodoro'),
    path('tasks/<int:task_id>/complete/', views.complete_task, name='complete_task'),
    path('tasks/<int:task_id>/abandon/', views.abandon_task, name='abandon_task'),

    path('achievements/', views.achievements, name='achievements'),

    path('shop/', views.shop, name='shop'),
    path('shop/<int:item_id>/buy/', views.buy_item, name='buy_item'),
    path('care/feed/<int:owned_id>/', views.feed_cat, name='feed_cat'),
    path('care/play/<int:owned_id>/', views.play_toy, name='play_toy'),
    path('care/equip/<int:owned_id>/', views.toggle_equip, name='toggle_equip'),
]

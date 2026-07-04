from django.urls import path

from . import views

urlpatterns = [
    path('shop/', views.shop, name='shop'),
    path('shop/<int:item_id>/buy/', views.buy_item, name='buy_item'),
    path('care/feed/<int:owned_id>/', views.feed_cat, name='feed_cat'),
    path('care/play/<int:owned_id>/', views.play_toy, name='play_toy'),
    path('care/equip/<int:owned_id>/', views.toggle_equip, name='toggle_equip'),
]

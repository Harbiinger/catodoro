from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),        # auth (login/logout/register)
    path('', include('cats.urls')),        # setup / cat settings
    path('', include('tasks.urls')),       # dashboard + quests
    path('', include('shop.urls')),        # shop + cat care
    path('', include('achievements.urls')),
    path('', include('adminpanel.urls')),  # staff-only stats dashboard
]

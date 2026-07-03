from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .forms import RegisterForm
from .models import Cat, OwnedItem, Player, ShopItem, Task, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = RegisterForm
    ordering = ('email',)
    list_display = ('email', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('email',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser',
                                     'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {'classes': ('wide',), 'fields': ('email', 'password1', 'password2')}),
    )


admin.site.register(Player)
admin.site.register(Cat)
admin.site.register(Task)
admin.site.register(ShopItem)
admin.site.register(OwnedItem)

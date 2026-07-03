from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .forms import RegisterForm
from .models import (
    Achievement,
    Cat,
    OwnedItem,
    Player,
    ShopItem,
    Task,
    UnlockedAchievement,
    User,
)


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


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ('icon', 'name', 'rarity', 'metric', 'threshold', 'category',
                    'item', 'reward_coins', 'active')
    list_display_links = ('name',)
    list_filter = ('rarity', 'metric', 'active')
    list_editable = ('active',)
    search_fields = ('name', 'description')
    autocomplete_fields = ('item',)
    fields = ('name', 'description', 'icon', 'rarity', 'metric', 'threshold',
              'category', 'item', 'reward_coins', 'active')


@admin.register(UnlockedAchievement)
class UnlockedAchievementAdmin(admin.ModelAdmin):
    list_display = ('user', 'achievement', 'unlocked_at')
    list_filter = ('achievement',)
    search_fields = ('user__email', 'achievement__name')
    readonly_fields = ('user', 'achievement', 'unlocked_at')


@admin.register(ShopItem)
class ShopItemAdmin(admin.ModelAdmin):
    list_display = ('icon', 'name', 'category', 'price')
    list_filter = ('category',)
    search_fields = ('name',)


admin.site.register(Player)
admin.site.register(Cat)
admin.site.register(Task)
admin.site.register(OwnedItem)

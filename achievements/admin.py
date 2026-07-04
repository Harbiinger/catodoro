from django.contrib import admin

from .models import Achievement, UnlockedAchievement


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

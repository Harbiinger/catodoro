"""Achievement evaluation: compute metric values and unlock earned goals."""
from __future__ import annotations

from django.contrib import messages

from cats.models import Cat
from core.models import Player
from tasks.models import Task

from .models import Achievement, UnlockedAchievement


def metric_value(user, achievement: Achievement, player: Player, cat: Cat):
    """The player's current value for an achievement's metric."""
    m = achievement.metric
    if m == Achievement.METRIC_LOGIN_STREAK:
        return player.login_streak
    if m == Achievement.METRIC_TASKS_DONE:
        return Task.objects.filter(user=user, status=Task.STATUS_DONE).count()
    if m == Achievement.METRIC_TASKS_FAILED:
        return Task.objects.filter(user=user, status=Task.STATUS_FAILED).count()
    if m == Achievement.METRIC_CAT_HAPPINESS:
        return cat.happiness
    if m == Achievement.METRIC_CAT_SATIETY:
        return cat.satiety
    if m == Achievement.METRIC_ITEMS_TOTAL:
        return player.items_bought_total
    if m == Achievement.METRIC_ITEMS_CATEGORY:
        return (player.purchases or {}).get(achievement.category, 0)
    if m == Achievement.METRIC_ITEMS_ITEM:
        return (player.purchases_by_item or {}).get(str(achievement.item_id), 0)
    return 0


def check_achievements(user, player: Player, cat: Cat) -> list[Achievement]:
    """Unlock any newly-earned achievements; return the ones just unlocked."""
    already = set(
        UnlockedAchievement.objects.filter(user=user).values_list('achievement_id', flat=True)
    )
    newly = []
    for ach in Achievement.objects.filter(active=True).exclude(id__in=already):
        if metric_value(user, ach, player, cat) >= ach.threshold:
            _, created = UnlockedAchievement.objects.get_or_create(user=user, achievement=ach)
            if created:
                if ach.reward_coins:
                    player.earn(ach.reward_coins)
                newly.append(ach)
    return newly


def award_achievements(request, world):
    """Unlock any newly-earned achievements and toast them to the player."""
    for ach in check_achievements(request.user, world.player, world.cat):
        bonus = f' (+{ach.reward_coins} 🪙)' if ach.reward_coins else ''
        messages.success(request, f'🏆 Achievement unlocked: {ach.name}{bonus}')

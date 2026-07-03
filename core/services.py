"""Glue between the models and the views.

``sync_world`` is the important bit: it's called at the top of every view and
brings the game up to date with wall-clock time (decaying the cat, failing any
tasks whose deadline slipped past).  Doing it lazily here means the app needs
no background scheduler.
"""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from .models import (
    Achievement,
    Cat,
    OwnedItem,
    Player,
    ShopItem,
    Task,
    UnlockedAchievement,
)

# mood -> how the cat is drawn on the dashboard
CAT_FACES = {
    Cat.MOOD_HAPPY: '😸',
    Cat.MOOD_CONTENT: '🐱',
    Cat.MOOD_HUNGRY: '🙀',
    Cat.MOOD_ANGRY: '🐈‍⬛',
    Cat.MOOD_AWAY: '',
}

MOOD_BLURB = {
    Cat.MOOD_HAPPY: 'is purring and happy to see you!',
    Cat.MOOD_CONTENT: 'is lounging around, content.',
    Cat.MOOD_HUNGRY: 'is hungry — better feed them.',
    Cat.MOOD_ANGRY: 'is sulking with their back turned to you.',
    Cat.MOOD_AWAY: 'is nowhere to be found. You neglected them...',
}


class World:
    """A snapshot of the whole game state for one request."""

    def __init__(self, player: Player, cat: Cat):
        self.player = player
        self.cat = cat

    @property
    def cat_face(self) -> str:
        return CAT_FACES.get(self.cat.mood, '🐱')

    @property
    def cat_blurb(self) -> str:
        return MOOD_BLURB.get(self.cat.mood, '')

    @property
    def cat_visible(self) -> bool:
        return self.cat.mood != Cat.MOOD_AWAY


def sync_world(user) -> World:
    """Bring one user's game up to date and return the current state."""
    player = Player.for_user(user)
    _touch_login_streak(player)
    cat = Cat.for_user(user).refresh()

    overdue = Task.objects.filter(
        user=user, status=Task.STATUS_ACTIVE, deadline__lt=_now()
    )
    for task in overdue:
        task.fail(player, cat)

    return World(player, cat)


def _touch_login_streak(player: Player):
    """Bump the daily login streak once per calendar day of activity."""
    today = timezone.localdate()
    if player.last_active_date == today:
        return
    if player.last_active_date == today - timedelta(days=1):
        player.login_streak += 1
    else:
        player.login_streak = 1
    player.last_active_date = today
    player.save(update_fields=['login_streak', 'last_active_date'])


# ---------------------------------------------------------------------------
# achievements
# ---------------------------------------------------------------------------
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


def context(world: World, **extra) -> dict:
    """Common template context shared by dashboard + partials."""
    data = {
        'world': world,
        'player': world.player,
        'cat': world.cat,
        'equipped': list(world.cat.equipped),
    }
    data.update(extra)
    return data


def _now():
    from django.utils import timezone
    return timezone.now()

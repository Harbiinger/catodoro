"""Shared game orchestration.

``sync_world`` is the important bit: it's called at the top of every view and
brings the game up to date with wall-clock time (decaying the cat, failing any
tasks whose deadline slipped past). Doing it lazily here means the app needs no
background scheduler.
"""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from cats.models import Cat
from tasks.models import Task

from .models import Player


class World:
    """A snapshot of the whole game state for one request."""

    def __init__(self, player: Player, cat: Cat):
        self.player = player
        self.cat = cat
        self.just_failed = 0  # tasks auto-failed during this request's sync

    @property
    def cat_blurb(self) -> str:
        return self.cat.blurb

    @property
    def cat_visible(self) -> bool:
        return self.cat.is_visible


def sync_world(user) -> World:
    """Bring one user's game up to date and return the current state."""
    player = Player.for_user(user)
    _touch_login_streak(player)
    cat = Cat.for_user(user).refresh()

    overdue = Task.objects.filter(
        user=user, status=Task.STATUS_ACTIVE, deadline__lt=timezone.now()
    )
    world = World(player, cat)
    for task in overdue:
        task.fail(player, cat)
        world.just_failed += 1

    return world


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

"""Glue between the models and the views.

``sync_world`` is the important bit: it's called at the top of every view and
brings the game up to date with wall-clock time (decaying the cat, failing any
tasks whose deadline slipped past).  Doing it lazily here means the app needs
no background scheduler.
"""
from __future__ import annotations

from .models import Cat, OwnedItem, Player, ShopItem, Task

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
    cat = Cat.for_user(user).refresh()

    overdue = Task.objects.filter(
        user=user, status=Task.STATUS_ACTIVE, deadline__lt=_now()
    )
    for task in overdue:
        task.fail(player, cat)

    return World(player, cat)


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

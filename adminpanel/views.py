"""Staff-only admin dashboard: a bird's-eye view of the whole game.

Everything here is read-only aggregation over the other apps' models. It's
gated behind ``staff_member_required`` so only Django staff/superusers can see
player-wide numbers.
"""
from __future__ import annotations

from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Max, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from achievements.models import Achievement, UnlockedAchievement
from cats.models import CAT_COLORS, Cat
from core.models import Player
from shop.models import OwnedItem, ShopItem
from tasks.models import DIFFICULTY_CHOICES, Task

User = get_user_model()


def _pct(part: int, whole: int) -> int:
    """Whole-number percentage, guarding against divide-by-zero."""
    return round(100 * part / whole) if whole else 0


def _user_stats():
    now = timezone.now()
    today = timezone.localdate()
    total = User.objects.count()
    # "Active" = has been seen (login-streak touched) within the window.
    active_today = Player.objects.filter(last_active_date=today).count()
    active_7d = Player.objects.filter(
        last_active_date__gte=today - timedelta(days=7)
    ).count()
    active_30d = Player.objects.filter(
        last_active_date__gte=today - timedelta(days=30)
    ).count()
    new_7d = User.objects.filter(date_joined__gte=now - timedelta(days=7)).count()
    return {
        'total': total,
        'staff': User.objects.filter(is_staff=True).count(),
        'active_today': active_today,
        'active_7d': active_7d,
        'active_30d': active_30d,
        'active_7d_pct': _pct(active_7d, total),
        'new_7d': new_7d,
        'longest_streak': Player.objects.aggregate(m=Max('login_streak'))['m'] or 0,
    }


def _quest_stats():
    by_status = dict(
        Task.objects.values_list('status').annotate(n=Count('id')).values_list('status', 'n')
    )
    active = by_status.get(Task.STATUS_ACTIVE, 0)
    done = by_status.get(Task.STATUS_DONE, 0)
    failed = by_status.get(Task.STATUS_FAILED, 0)
    total = active + done + failed
    resolved = done + failed

    by_diff_raw = dict(
        Task.objects.values_list('difficulty').annotate(n=Count('id')).values_list('difficulty', 'n')
    )
    by_difficulty = [
        {'label': label, 'count': by_diff_raw.get(key, 0), 'pct': _pct(by_diff_raw.get(key, 0), total)}
        for key, label in DIFFICULTY_CHOICES
    ]

    agg = Task.objects.aggregate(
        pomodoros=Sum('completed_pomodoros'),
        coins_earned=Sum('reward', filter=Q(status=Task.STATUS_DONE)),
        coins_lost=Sum('penalty', filter=Q(status=Task.STATUS_FAILED)),
    )
    overdue = Task.objects.filter(
        status=Task.STATUS_ACTIVE, deadline__lt=timezone.now()
    ).count()

    return {
        'total': total,
        'active': active,
        'done': done,
        'failed': failed,
        'overdue': overdue,
        'completion_rate': _pct(done, resolved),
        'by_difficulty': by_difficulty,
        'pomodoros': agg['pomodoros'] or 0,
        'coins_earned': agg['coins_earned'] or 0,
        'coins_lost': agg['coins_lost'] or 0,
    }


def _cat_stats():
    total = Cat.objects.count()
    configured = Cat.objects.filter(configured=True).count()
    agg = Cat.objects.aggregate(happy=Avg('happiness'), sat=Avg('satiety'))

    by_color_raw = dict(
        Cat.objects.values_list('color').annotate(n=Count('id')).values_list('color', 'n')
    )
    by_color = [
        {'label': label, 'hex': hex_, 'count': by_color_raw.get(key, 0),
         'pct': _pct(by_color_raw.get(key, 0), total)}
        for key, label, hex_ in CAT_COLORS
    ]
    by_color.sort(key=lambda c: -c['count'])

    # Mood is a computed property, so tally it in Python.
    moods: dict[str, int] = {}
    for cat in Cat.objects.only('happiness', 'satiety'):
        moods[cat.mood] = moods.get(cat.mood, 0) + 1
    mood_rows = sorted(
        ({'mood': m.title(), 'count': n, 'pct': _pct(n, total)} for m, n in moods.items()),
        key=lambda r: -r['count'],
    )

    return {
        'total': total,
        'configured': configured,
        'avg_happiness': round(agg['happy'] or 0),
        'avg_satiety': round(agg['sat'] or 0),
        'by_color': by_color,
        'moods': mood_rows,
    }


def _economy_stats():
    coins = Player.objects.aggregate(total=Sum('coins'), avg=Avg('coins'))
    items_owned = OwnedItem.objects.aggregate(n=Sum('quantity'))['n'] or 0
    top_items = list(
        ShopItem.objects.annotate(sold=Sum('owned__quantity'))
        .filter(sold__gt=0).order_by('-sold')[:5]
    )
    return {
        'coins_total': coins['total'] or 0,
        'coins_avg': round(coins['avg'] or 0),
        'catalogue_size': ShopItem.objects.count(),
        'items_owned': items_owned,
        'top_items': top_items,
    }


def _achievement_stats():
    total = Achievement.objects.count()
    active = Achievement.objects.filter(active=True).count()
    unlocks = UnlockedAchievement.objects.count()
    top = list(
        Achievement.objects.annotate(n=Count('unlocks')).filter(n__gt=0).order_by('-n')[:5]
    )
    players = Player.objects.count()
    return {
        'total': total,
        'active': active,
        'unlocks': unlocks,
        'avg_per_user': round(unlocks / players, 1) if players else 0,
        'top': top,
    }


@staff_member_required
def dashboard(request):
    ctx = {
        'users': _user_stats(),
        'quests': _quest_stats(),
        'cats': _cat_stats(),
        'economy': _economy_stats(),
        'achievements': _achievement_stats(),
        'generated_at': timezone.now(),
    }
    return render(request, 'adminpanel/dashboard.html', ctx)

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from core import services

from .models import Achievement, UnlockedAchievement
from .services import award_achievements, metric_value


@login_required
def achievements(request):
    world = services.sync_world(request.user)
    if not world.cat.configured:
        return redirect('setup')
    award_achievements(request, world)

    unlocked = {
        u.achievement_id: u
        for u in UnlockedAchievement.objects.filter(user=request.user)
    }
    rows = []
    for ach in Achievement.objects.filter(active=True):
        value = metric_value(request.user, ach, world.player, world.cat)
        pct = min(100, round(100 * value / ach.threshold)) if ach.threshold else 100
        rows.append({
            'ach': ach,
            'value': int(value),
            'pct': pct,
            'unlocked': unlocked.get(ach.id),
        })
    rows.sort(key=lambda r: (r['unlocked'] is None, -r['pct']))
    return render(request, 'achievements/achievements.html', services.context(
        world, rows=rows, unlocked_count=len(unlocked), total_count=len(rows),
    ))

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from achievements.services import award_achievements
from core import services

from .forms import TaskForm
from .models import COINS_PER_POMODORO, Task


def _active_tasks(user):
    return Task.objects.filter(user=user, status=Task.STATUS_ACTIVE)


def _history(user):
    return Task.objects.filter(user=user).exclude(status=Task.STATUS_ACTIVE)[:12]


def _dashboard_context(request, world, form=None, emote=None):
    award_achievements(request, world)
    return services.context(
        world,
        tasks=_active_tasks(request.user),
        history=_history(request.user),
        form=form or TaskForm(),
        coins_per_pomodoro=COINS_PER_POMODORO,
        emote_path=world.cat.image_for(emote),
    )


@login_required
def dashboard(request):
    world = services.sync_world(request.user)
    if not world.cat.configured:
        return redirect('setup')
    emote = 'quest_failed' if world.just_failed else None
    return render(request, 'tasks/dashboard.html', _dashboard_context(request, world, emote=emote))


@login_required
@require_POST
def create_task(request):
    world = services.sync_world(request.user)
    form = TaskForm(request.POST)
    if form.is_valid():
        task = form.save(commit=False)
        task.user = request.user
        task.save()
        world = services.sync_world(request.user)
        messages.success(request, 'New quest added. Get focusing!')
        return render(request, 'tasks/partials/task_section.html',
                      _dashboard_context(request, world))
    # invalid: re-render the form section with errors
    return render(request, 'tasks/partials/task_section.html',
                  _dashboard_context(request, world, form=form))


@login_required
@require_POST
def complete_pomodoro(request, task_id):
    """Called by the timer when a focus session finishes."""
    world = services.sync_world(request.user)
    task = get_object_or_404(Task, pk=task_id, user=request.user, status=Task.STATUS_ACTIVE)
    task.completed_pomodoros += 1
    task.save(update_fields=['completed_pomodoros'])
    world.player.earn(COINS_PER_POMODORO)
    world.cat.adjust(happiness=3)
    messages.success(request, f'Focus session done! +{COINS_PER_POMODORO} coins 🪙')
    return render(request, 'tasks/partials/task_section.html',
                  _dashboard_context(request, world))


@login_required
@require_POST
def complete_task(request, task_id):
    world = services.sync_world(request.user)
    task = get_object_or_404(Task, pk=task_id, user=request.user, status=Task.STATUS_ACTIVE)
    with transaction.atomic():
        task.complete(world.player, world.cat)
    messages.success(request, f'"{task.title}" done! +{task.reward} coins 🪙')
    return render(request, 'tasks/partials/task_section.html',
                  _dashboard_context(request, world))


@login_required
@require_POST
def abandon_task(request, task_id):
    """Give up on a task now — takes the penalty immediately."""
    world = services.sync_world(request.user)
    task = get_object_or_404(Task, pk=task_id, user=request.user, status=Task.STATUS_ACTIVE)
    with transaction.atomic():
        task.fail(world.player, world.cat)
    messages.error(request, f'You abandoned "{task.title}". The cat is not pleased.')
    return render(request, 'tasks/partials/task_section.html',
                  _dashboard_context(request, world, emote='quest_failed'))

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .forms import CatSetupForm, RegisterForm, TaskForm
from .models import (
    CAT_COLORS,
    COINS_PER_POMODORO,
    Achievement,
    Cat,
    OwnedItem,
    Player,
    ShopItem,
    Task,
    UnlockedAchievement,
)


def _award_achievements(request, world):
    """Unlock any newly-earned achievements and toast them to the player."""
    for ach in services.check_achievements(request.user, world.player, world.cat):
        bonus = f' (+{ach.reward_coins} 🪙)' if ach.reward_coins else ''
        messages.success(request, f'🏆 Achievement unlocked: {ach.name}{bonus}')


# ---------------------------------------------------------------------------
# auth
# ---------------------------------------------------------------------------
def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            # bootstrap this player's world (cat still needs configuring)
            Player.for_user(user)
            Cat.for_user(user)
            login(request, user)
            return redirect('setup')
    else:
        form = RegisterForm()
    return render(request, 'registration/register.html', {'form': form})


@login_required
def setup(request):
    """Onboarding / cat settings: choose the cat's name and colour."""
    player = Player.for_user(request.user)
    cat = Cat.for_user(request.user)
    first_time = not cat.configured
    if request.method == 'POST':
        form = CatSetupForm(request.POST, instance=cat)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.configured = True
            cat.save()
            messages.success(request, f'{cat.name} is settled in. Welcome!')
            return redirect('dashboard')
    else:
        form = CatSetupForm(instance=cat)
    return render(request, 'core/setup.html', {
        'form': form, 'cat': cat, 'player': player,
        'colors': CAT_COLORS, 'first_time': first_time,
    })


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _active_tasks(user):
    return Task.objects.filter(user=user, status=Task.STATUS_ACTIVE)


def _history(user):
    return Task.objects.filter(user=user).exclude(status=Task.STATUS_ACTIVE)[:12]


def _dashboard_context(request, world, form=None):
    _award_achievements(request, world)
    return services.context(
        world,
        tasks=_active_tasks(request.user),
        history=_history(request.user),
        form=form or TaskForm(),
        coins_per_pomodoro=COINS_PER_POMODORO,
    )


# ---------------------------------------------------------------------------
# dashboard
# ---------------------------------------------------------------------------
@login_required
def dashboard(request):
    world = services.sync_world(request.user)
    if not world.cat.configured:
        return redirect('setup')
    return render(request, 'core/dashboard.html', _dashboard_context(request, world))


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
        return render(request, 'core/partials/task_section.html',
                      _dashboard_context(request, world))
    # invalid: re-render the form section with errors
    return render(request, 'core/partials/task_section.html',
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
    return render(request, 'core/partials/task_section.html',
                  _dashboard_context(request, world))


@login_required
@require_POST
def complete_task(request, task_id):
    world = services.sync_world(request.user)
    task = get_object_or_404(Task, pk=task_id, user=request.user, status=Task.STATUS_ACTIVE)
    with transaction.atomic():
        task.complete(world.player, world.cat)
    messages.success(request, f'"{task.title}" done! +{task.reward} coins 🪙')
    return render(request, 'core/partials/task_section.html',
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
    return render(request, 'core/partials/task_section.html',
                  _dashboard_context(request, world))


# ---------------------------------------------------------------------------
# shop & cat care
# ---------------------------------------------------------------------------
def _owned_map(user):
    return {o.item_id: o for o in OwnedItem.objects.filter(user=user).select_related('item')}


def _shop_context(request, world):
    _award_achievements(request, world)
    owned = _owned_map(request.user)
    items = list(ShopItem.objects.all())
    for it in items:
        # attach the current user's ownership row (avoid the reverse-relation
        # accessor `it.owned`, which is a manager, not an assignable attribute)
        it.owned_entry = owned.get(it.id)

    def in_cat(cat):
        return [i for i in items if i.category == cat]

    owned_items = owned.values()
    return services.context(
        world,
        catalog=[
            {'title': '🍽️ Food', 'items': in_cat(ShopItem.FOOD)},
            {'title': '🧶 Toys', 'items': in_cat(ShopItem.TOY)},
            {'title': '🎀 Accessories', 'items': in_cat(ShopItem.ACCESSORY)},
        ],
        pantry=[o for o in owned_items if o.item.category == ShopItem.FOOD and o.quantity > 0],
        toys_owned=[o for o in owned_items if o.item.category == ShopItem.TOY],
        accessories_owned=[o for o in owned_items if o.item.category == ShopItem.ACCESSORY],
    )


@login_required
def shop(request):
    world = services.sync_world(request.user)
    if not world.cat.configured:
        return redirect('setup')
    return render(request, 'core/shop.html', _shop_context(request, world))


def _render_shop(request, world):
    return render(request, 'core/partials/shop_body.html', _shop_context(request, world))


@login_required
@require_POST
def buy_item(request, item_id):
    world = services.sync_world(request.user)
    item = get_object_or_404(ShopItem, pk=item_id)
    if not world.player.spend(item.price):
        messages.error(request, f'Not enough coins for {item.name}.')
        return _render_shop(request, world)

    owned, created = OwnedItem.objects.get_or_create(user=request.user, item=item)
    if not created:
        # only food stacks; toys/accessories are one-and-done
        if item.category == ShopItem.FOOD:
            owned.quantity += 1
            owned.save(update_fields=['quantity'])
    world.player.record_purchase(item)
    messages.success(request, f'Bought {item.icon} {item.name}!')
    return _render_shop(request, world)


@login_required
@require_POST
def feed_cat(request, owned_id):
    world = services.sync_world(request.user)
    owned = get_object_or_404(
        OwnedItem, pk=owned_id, user=request.user, item__category=ShopItem.FOOD
    )
    if owned.quantity <= 0:
        messages.error(request, 'None of that food left.')
        return _render_shop(request, world)
    owned.quantity -= 1
    owned.save(update_fields=['quantity'])
    world.cat.adjust(happiness=owned.item.happiness_boost, satiety=owned.item.satiety_boost)
    messages.success(request, f'{world.cat.name} enjoyed the {owned.item.name}! 😋')
    return _render_shop(request, world)


@login_required
@require_POST
def play_toy(request, owned_id):
    world = services.sync_world(request.user)
    owned = get_object_or_404(
        OwnedItem, pk=owned_id, user=request.user, item__category=ShopItem.TOY
    )
    world.cat.adjust(happiness=owned.item.happiness_boost)
    messages.success(request, f'{world.cat.name} had fun with the {owned.item.name}! 🧶')
    return _render_shop(request, world)


@login_required
@require_POST
def toggle_equip(request, owned_id):
    world = services.sync_world(request.user)
    owned = get_object_or_404(
        OwnedItem, pk=owned_id, user=request.user, item__category=ShopItem.ACCESSORY
    )
    owned.equipped = not owned.equipped
    owned.save(update_fields=['equipped'])
    return _render_shop(request, world)


# ---------------------------------------------------------------------------
# achievements
# ---------------------------------------------------------------------------
@login_required
def achievements(request):
    world = services.sync_world(request.user)
    if not world.cat.configured:
        return redirect('setup')
    _award_achievements(request, world)

    unlocked = {
        u.achievement_id: u
        for u in UnlockedAchievement.objects.filter(user=request.user)
    }
    rows = []
    for ach in Achievement.objects.filter(active=True):
        value = services.metric_value(request.user, ach, world.player, world.cat)
        pct = min(100, round(100 * value / ach.threshold)) if ach.threshold else 100
        rows.append({
            'ach': ach,
            'value': int(value),
            'pct': pct,
            'unlocked': unlocked.get(ach.id),
        })
    rows.sort(key=lambda r: (r['unlocked'] is None, -r['pct']))
    return render(request, 'core/achievements.html', services.context(
        world, rows=rows, unlocked_count=len(unlocked), total_count=len(rows),
    ))

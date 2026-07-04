from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from achievements.services import award_achievements
from core import services

from .models import OwnedItem, ShopItem


def _owned_map(user):
    return {o.item_id: o for o in OwnedItem.objects.filter(user=user).select_related('item')}


def _shop_context(request, world, emote=None):
    award_achievements(request, world)
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
        emote_path=world.cat.image_for(emote),
    )


@login_required
def shop(request):
    world = services.sync_world(request.user)
    if not world.cat.configured:
        return redirect('setup')
    return render(request, 'shop/shop.html', _shop_context(request, world))


def _render_shop(request, world, emote=None):
    return render(request, 'shop/partials/shop_body.html',
                  _shop_context(request, world, emote=emote))


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
    return _render_shop(request, world, emote='gift')


@login_required
@require_POST
def play_toy(request, owned_id):
    world = services.sync_world(request.user)
    owned = get_object_or_404(
        OwnedItem, pk=owned_id, user=request.user, item__category=ShopItem.TOY
    )
    world.cat.adjust(happiness=owned.item.happiness_boost)
    messages.success(request, f'{world.cat.name} had fun with the {owned.item.name}! 🧶')
    return _render_shop(request, world, emote='gift')


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

"""The shop catalogue and what each player owns."""
from __future__ import annotations

from django.conf import settings
from django.db import models


class ShopItem(models.Model):
    FOOD = 'food'
    TOY = 'toy'
    ACCESSORY = 'accessory'
    CATEGORY_CHOICES = [
        (FOOD, 'Food'),
        (TOY, 'Toy'),
        (ACCESSORY, 'Accessory'),
    ]

    name = models.CharField(max_length=60)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    price = models.PositiveIntegerField()
    icon = models.CharField(max_length=8, default='🎁', help_text='emoji shown in shop')
    # gameplay effect (used by food/toys)
    happiness_boost = models.FloatField(default=0)
    satiety_boost = models.FloatField(default=0)
    description = models.CharField(max_length=140, blank=True)
    sort = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['category', 'sort', 'price']

    def __str__(self):
        return f'{self.icon} {self.name}'


class OwnedItem(models.Model):
    """An item the player owns.

    Food is consumable (``quantity`` decrements when used).  Toys and
    accessories are permanent; accessories additionally track ``equipped``.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_items'
    )
    item = models.ForeignKey(ShopItem, on_delete=models.CASCADE, related_name='owned')
    quantity = models.PositiveIntegerField(default=1)
    equipped = models.BooleanField(default=False)
    acquired_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'item')

    def __str__(self):
        return f'{self.item.name} x{self.quantity}'

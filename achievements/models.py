"""Admin-configurable achievements and per-user unlock records."""
from __future__ import annotations

from django.conf import settings
from django.db import models

from shop.models import ShopItem


class Achievement(models.Model):
    """An unlockable goal, configured in the Django admin.

    Each achievement watches one *metric* and unlocks for a player once their
    value reaches ``threshold``. ``category`` is only used by the
    "items bought (category)" metric.
    """

    METRIC_LOGIN_STREAK = 'login_streak'
    METRIC_TASKS_DONE = 'tasks_done'
    METRIC_TASKS_FAILED = 'tasks_failed'
    METRIC_CAT_HAPPINESS = 'cat_happiness'
    METRIC_CAT_SATIETY = 'cat_satiety'
    METRIC_ITEMS_TOTAL = 'items_bought_total'
    METRIC_ITEMS_CATEGORY = 'items_bought_category'
    METRIC_ITEMS_ITEM = 'items_bought_item'
    METRIC_CHOICES = [
        (METRIC_LOGIN_STREAK, 'Login streak (consecutive days)'),
        (METRIC_TASKS_DONE, 'Tasks completed'),
        (METRIC_TASKS_FAILED, 'Tasks failed'),
        (METRIC_CAT_HAPPINESS, 'Cat happiness reached (%)'),
        (METRIC_CAT_SATIETY, 'Cat fullness reached (%)'),
        (METRIC_ITEMS_TOTAL, 'Items bought (total)'),
        (METRIC_ITEMS_CATEGORY, 'Items bought (category)'),
        (METRIC_ITEMS_ITEM, 'Items bought (specific item)'),
    ]

    RARITY_COMMON = 'common'
    RARITY_RARE = 'rare'
    RARITY_EPIC = 'epic'
    RARITY_LEGENDARY = 'legendary'
    RARITY_CHOICES = [
        (RARITY_COMMON, 'Common'),
        (RARITY_RARE, 'Rare'),
        (RARITY_EPIC, 'Epic'),
        (RARITY_LEGENDARY, 'Legendary'),
    ]
    # Tailwind classes for the rarity badge / unlocked-card ring.
    RARITY_STYLES = {
        RARITY_COMMON: ('bg-stone-100 text-stone-600', 'ring-stone-200'),
        RARITY_RARE: ('bg-sky-100 text-sky-700', 'ring-sky-300'),
        RARITY_EPIC: ('bg-purple-100 text-purple-700', 'ring-purple-300'),
        RARITY_LEGENDARY: ('bg-amber-100 text-amber-700', 'ring-amber-400'),
    }

    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=200, blank=True)
    icon = models.CharField(max_length=8, default='🏆', help_text='emoji badge')
    rarity = models.CharField(max_length=10, choices=RARITY_CHOICES, default=RARITY_COMMON)
    metric = models.CharField(max_length=24, choices=METRIC_CHOICES)
    threshold = models.PositiveIntegerField(
        help_text='Target value: streak days, a count, or a percentage.'
    )
    category = models.CharField(
        max_length=10, blank=True, choices=ShopItem.CATEGORY_CHOICES,
        help_text='Only for the "items bought (category)" metric.',
    )
    item = models.ForeignKey(
        ShopItem, null=True, blank=True, on_delete=models.CASCADE,
        related_name='achievements',
        help_text='Only for the "items bought (specific item)" metric.',
    )
    reward_coins = models.PositiveIntegerField(
        default=0, help_text='Bonus coins granted on unlock.'
    )
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['rarity', 'metric', 'threshold']

    def __str__(self):
        return f'{self.icon} {self.name}'

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.metric == self.METRIC_ITEMS_CATEGORY and not self.category:
            raise ValidationError({'category': 'Pick a category for this metric.'})
        if self.metric != self.METRIC_ITEMS_CATEGORY and self.category:
            raise ValidationError(
                {'category': 'Category only applies to the "items bought (category)" metric.'}
            )
        if self.metric == self.METRIC_ITEMS_ITEM and not self.item_id:
            raise ValidationError({'item': 'Pick an item for this metric.'})
        if self.metric != self.METRIC_ITEMS_ITEM and self.item_id:
            raise ValidationError(
                {'item': 'Item only applies to the "items bought (specific item)" metric.'}
            )

    @property
    def is_percentage(self) -> bool:
        return self.metric in (self.METRIC_CAT_HAPPINESS, self.METRIC_CAT_SATIETY)

    @property
    def target_label(self) -> str:
        if self.metric == self.METRIC_ITEMS_CATEGORY and self.category:
            return self.get_category_display()
        if self.metric == self.METRIC_ITEMS_ITEM and self.item_id:
            return self.item.name
        return ''

    @property
    def rarity_badge_class(self) -> str:
        return self.RARITY_STYLES.get(self.rarity, self.RARITY_STYLES[self.RARITY_COMMON])[0]

    @property
    def rarity_ring_class(self) -> str:
        return self.RARITY_STYLES.get(self.rarity, self.RARITY_STYLES[self.RARITY_COMMON])[1]


class UnlockedAchievement(models.Model):
    """Records that a user has unlocked an achievement."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='achievements'
    )
    achievement = models.ForeignKey(
        Achievement, on_delete=models.CASCADE, related_name='unlocks'
    )
    unlocked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'achievement')
        ordering = ['-unlocked_at']

    def __str__(self):
        return f'{self.user} → {self.achievement.name}'

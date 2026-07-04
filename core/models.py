"""Data models and the little game engine that powers Catodoro.

The whole thing is single-player: there is exactly one Player row and one
Cat row, created lazily.  All time-based mechanics (stat decay, overdue
tasks) are evaluated lazily whenever a page is loaded, so no background
worker or cron job is required.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

# ---------------------------------------------------------------------------
# Tunable game balance
# ---------------------------------------------------------------------------
COINS_PER_POMODORO = 5          # earned every time a focus session completes
STARTING_COINS = 15             # so the shop isn't empty-handed on day one

# Stat decay, expressed as points lost per hour of real time.
SATIETY_DECAY_PER_HOUR = 6.0    # ~16h to go from full to starving
HAPPINESS_DECAY_PER_HOUR = 1.5  # slow drift; big swings come from tasks

# How much a failed task stings.
FAIL_HAPPINESS_HIT = 30

# Coin economy: rewards/penalties come from the task's difficulty (chosen by
# the player) scaled by how tight the deadline is. Each difficulty has a
# (reward_base, penalty_base); the urgency multiplier is applied to both.
DIFFICULTY_EASY = 'easy'
DIFFICULTY_MEDIUM = 'medium'
DIFFICULTY_HARD = 'hard'
DIFFICULTY_CHOICES = [
    (DIFFICULTY_EASY, 'Easy'),
    (DIFFICULTY_MEDIUM, 'Medium'),
    (DIFFICULTY_HARD, 'Hard'),
]
DIFFICULTY_ICONS = {DIFFICULTY_EASY: '🌱', DIFFICULTY_MEDIUM: '⚡', DIFFICULTY_HARD: '🔥'}
DIFFICULTY_BASE = {          # (reward_base, penalty_base)
    DIFFICULTY_EASY: (10, 8),
    DIFFICULTY_MEDIUM: (20, 16),
    DIFFICULTY_HARD: (35, 28),
}


def deadline_urgency_multiplier(hours):
    """Tighter deadlines are worth (and cost) more."""
    if hours <= 3:
        return 1.5      # crunch time
    if hours <= 24:
        return 1.25     # today
    if hours <= 72:
        return 1.0      # this week
    return 0.8          # plenty of time


def rewards_for(difficulty, deadline, reference=None):
    """Return (reward, penalty) for a difficulty + deadline pair."""
    reference = reference or timezone.now()
    hours = max(0.0, (deadline - reference).total_seconds() / 3600)
    mult = deadline_urgency_multiplier(hours)
    reward_base, penalty_base = DIFFICULTY_BASE.get(
        difficulty, DIFFICULTY_BASE[DIFFICULTY_MEDIUM]
    )
    return round(reward_base * mult), round(penalty_base * mult)

# Mood thresholds (see Cat.mood).
MOOD_AWAY_BELOW = 20            # too neglected to even show up
MOOD_ANGRY_BELOW = 45          # sulking, back turned
MOOD_HUNGRY_SATIETY = 30       # otherwise fine but needs feeding

# Fur colours the player can pick during setup: (key, label, glow hex).
CAT_COLORS = [
    ('orange', 'Orange', '#fb923c'),
    ('grey', 'Grey', '#94a3b8'),
    ('black', 'Black', '#475569'),
    ('white', 'White', '#e2e8f0'),
    ('cream', 'Cream', '#fcd34d'),
    ('pink', 'Pink', '#f9a8d4'),
]
COLOR_CHOICES = [(key, label) for key, label, _ in CAT_COLORS]
COLOR_HEX = {key: hex_ for key, _, hex_ in CAT_COLORS}


class UserManager(BaseUserManager):
    """User manager keyed on email instead of username."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('An email address is required.')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Email is the login identifier; there is no username."""

    username = None
    email = models.EmailField('email address', unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


class Player(models.Model):
    """One wallet per user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='player'
    )
    coins = models.IntegerField(default=STARTING_COINS)
    # Achievement tracking (see core.services).
    login_streak = models.PositiveIntegerField(default=0)
    last_active_date = models.DateField(null=True, blank=True)
    # Purchases counted per ShopItem category, e.g. {"food": 3, "toy": 1}.
    purchases = models.JSONField(default=dict, blank=True)
    # Purchases counted per ShopItem id, e.g. {"2": 5} (keys are str(item.id)).
    purchases_by_item = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f'{self.user} ({self.coins} coins)'

    @classmethod
    def for_user(cls, user) -> 'Player':
        obj, _ = cls.objects.get_or_create(user=user)
        return obj

    def can_afford(self, amount: int) -> bool:
        return self.coins >= amount

    def earn(self, amount: int):
        self.coins += amount
        self.save(update_fields=['coins'])

    def record_purchase(self, item):
        by_cat = self.purchases or {}
        by_cat[item.category] = by_cat.get(item.category, 0) + 1
        self.purchases = by_cat
        by_item = self.purchases_by_item or {}
        key = str(item.id)
        by_item[key] = by_item.get(key, 0) + 1
        self.purchases_by_item = by_item
        self.save(update_fields=['purchases', 'purchases_by_item'])

    @property
    def items_bought_total(self) -> int:
        return sum((self.purchases or {}).values())

    def spend(self, amount: int) -> bool:
        if not self.can_afford(amount):
            return False
        self.coins -= amount
        self.save(update_fields=['coins'])
        return True


class Cat(models.Model):
    """The cat you're taking care of.

    ``happiness`` and ``satiety`` are 0-100 floats that decay over time.
    They're only recomputed when :meth:`refresh` is called, which the views
    do on every request.
    """

    MOOD_HAPPY = 'happy'
    MOOD_CONTENT = 'content'
    MOOD_HUNGRY = 'hungry'
    MOOD_ANGRY = 'angry'
    MOOD_AWAY = 'away'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cat'
    )
    name = models.CharField(max_length=40, default='Miso')
    color = models.CharField(max_length=10, choices=COLOR_CHOICES, default='orange')
    configured = models.BooleanField(default=False)  # completed onboarding?
    happiness = models.FloatField(default=70)
    satiety = models.FloatField(default=70)
    updated_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.name} ({self.mood})'

    @classmethod
    def for_user(cls, user) -> 'Cat':
        obj, _ = cls.objects.get_or_create(user=user)
        return obj

    @property
    def color_hex(self) -> str:
        return COLOR_HEX.get(self.color, COLOR_HEX['orange'])

    # -- mechanics ----------------------------------------------------------
    def refresh(self, *, commit=True):
        """Apply time-based decay since the last refresh."""
        now = timezone.now()
        hours = (now - self.updated_at).total_seconds() / 3600
        if hours > 0:
            self.satiety = _clamp(self.satiety - SATIETY_DECAY_PER_HOUR * hours)
            self.happiness = _clamp(self.happiness - HAPPINESS_DECAY_PER_HOUR * hours)
            self.updated_at = now
            if commit:
                self.save(update_fields=['satiety', 'happiness', 'updated_at'])
        return self

    def adjust(self, *, happiness=0.0, satiety=0.0):
        self.happiness = _clamp(self.happiness + happiness)
        self.satiety = _clamp(self.satiety + satiety)
        self.save(update_fields=['happiness', 'satiety'])

    @property
    def mood(self) -> str:
        if self.happiness < MOOD_AWAY_BELOW:
            return self.MOOD_AWAY
        if self.happiness < MOOD_ANGRY_BELOW:
            return self.MOOD_ANGRY
        if self.satiety < MOOD_HUNGRY_SATIETY:
            return self.MOOD_HUNGRY
        if self.happiness >= 75 and self.satiety >= 50:
            return self.MOOD_HAPPY
        return self.MOOD_CONTENT

    @property
    def equipped(self):
        return OwnedItem.objects.filter(
            user=self.user, item__category=ShopItem.ACCESSORY, equipped=True
        ).select_related('item')

    # -- artwork ------------------------------------------------------------
    # Fur colours that ship a full set of PNGs under static/cats/<colour>/.
    # Colours not listed here fall back to the drawn SVG cat.
    IMAGE_COLORS = {'orange', 'grey', 'black', 'white', 'cream', 'pink'}

    @property
    def has_images(self) -> bool:
        return self.color in self.IMAGE_COLORS

    def image_for(self, state) -> str:
        """static-relative path for a mood/emote png, or '' if unavailable."""
        if not self.has_images or not state:
            return ''
        return f'cats/{self.color}/{self.color}_{state}.png'

    @property
    def mood_image(self) -> str:
        # 'away' keeps the emoji basket, so no image for it.
        if self.mood == self.MOOD_AWAY:
            return ''
        return self.image_for(self.mood)

    @property
    def happy_image(self) -> str:
        """The happy pose — used as the default art in the settings preview."""
        return self.image_for('happy')


class Task(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_DONE = 'done'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_DONE, 'Done'),
        (STATUS_FAILED, 'Failed'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tasks'
    )
    title = models.CharField(max_length=120)
    deadline = models.DateTimeField()
    difficulty = models.CharField(
        max_length=6, choices=DIFFICULTY_CHOICES, default=DIFFICULTY_MEDIUM
    )
    estimated_pomodoros = models.PositiveSmallIntegerField(default=1)
    completed_pomodoros = models.PositiveSmallIntegerField(default=0)
    # Derived from difficulty + deadline at creation time (see save()).
    reward = models.PositiveIntegerField(default=20)
    penalty = models.PositiveIntegerField(default=15)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['status', 'deadline']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Compute the coin stakes when the task is first created, from its
        # difficulty and how soon the deadline is.
        if self._state.adding and self.deadline:
            self.reward, self.penalty = rewards_for(self.difficulty, self.deadline)
        super().save(*args, **kwargs)

    @property
    def difficulty_icon(self) -> str:
        return DIFFICULTY_ICONS.get(self.difficulty, '⚡')

    @property
    def is_overdue(self) -> bool:
        return self.status == self.STATUS_ACTIVE and self.deadline < timezone.now()

    @property
    def progress_pct(self) -> int:
        if not self.estimated_pomodoros:
            return 0
        return min(100, round(100 * self.completed_pomodoros / self.estimated_pomodoros))

    def complete(self, player: Player, cat: Cat):
        """Mark done, pay out the reward, cheer the cat up."""
        if self.status != self.STATUS_ACTIVE:
            return
        self.status = self.STATUS_DONE
        self.resolved_at = timezone.now()
        self.save(update_fields=['status', 'resolved_at'])
        player.earn(self.reward)
        cat.adjust(happiness=12, satiety=2)

    def fail(self, player: Player, cat: Cat):
        """Mark failed, dock coins, upset the cat."""
        if self.status != self.STATUS_ACTIVE:
            return
        self.status = self.STATUS_FAILED
        self.resolved_at = timezone.now()
        self.save(update_fields=['status', 'resolved_at'])
        player.spend(min(self.penalty, player.coins))  # never go negative
        cat.adjust(happiness=-FAIL_HAPPINESS_HIT)


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


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))

"""The cat the player takes care of: mood, stats decay, and artwork."""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

# Stat decay, expressed as points lost per hour of real time.
SATIETY_DECAY_PER_HOUR = 6.0    # ~16h to go from full to starving
HAPPINESS_DECAY_PER_HOUR = 1.5  # slow drift; big swings come from tasks

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


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


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

    MOOD_BLURB = {
        MOOD_HAPPY: 'is purring and happy to see you!',
        MOOD_CONTENT: 'is lounging around, content.',
        MOOD_HUNGRY: 'is hungry — better feed them.',
        MOOD_ANGRY: 'is sulking with their back turned to you.',
        MOOD_AWAY: 'is nowhere to be found. You neglected them...',
    }

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
    def blurb(self) -> str:
        return self.MOOD_BLURB.get(self.mood, '')

    @property
    def is_visible(self) -> bool:
        return self.mood != self.MOOD_AWAY

    @property
    def equipped(self):
        # lazy import to avoid a cats -> shop import at module load
        from shop.models import OwnedItem, ShopItem
        return OwnedItem.objects.filter(
            user=self.user, item__category=ShopItem.ACCESSORY, equipped=True
        ).select_related('item')

    # -- artwork ------------------------------------------------------------
    # Fur colours that ship a full set of PNGs under cats/static/cats/<colour>/.
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
        """The happy pose."""
        return self.image_for('happy')

    @property
    def content_image(self) -> str:
        """The content pose — the default art in the settings preview."""
        return self.image_for('content')

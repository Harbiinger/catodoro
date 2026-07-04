"""Quests: deadline-driven tasks whose stakes come from difficulty + urgency."""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

COINS_PER_POMODORO = 5          # earned every time a focus session completes
FAIL_HAPPINESS_HIT = 30         # how much a failed task upsets the cat

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

    def complete(self, player, cat):
        """Mark done, pay out the reward, cheer the cat up."""
        if self.status != self.STATUS_ACTIVE:
            return
        self.status = self.STATUS_DONE
        self.resolved_at = timezone.now()
        self.save(update_fields=['status', 'resolved_at'])
        player.earn(self.reward)
        cat.adjust(happiness=12, satiety=2)

    def fail(self, player, cat):
        """Mark failed, dock coins, upset the cat."""
        if self.status != self.STATUS_ACTIVE:
            return
        self.status = self.STATUS_FAILED
        self.resolved_at = timezone.now()
        self.save(update_fields=['status', 'resolved_at'])
        player.spend(min(self.penalty, player.coins))  # never go negative
        cat.adjust(happiness=-FAIL_HAPPINESS_HIT)

"""Accounts + shared hub: the custom email User and the player's wallet.

The custom ``User`` model stays in ``core`` because ``AUTH_USER_MODEL`` points
at it; moving a swappable user model after the fact is a Django footgun. Each
feature (cats, tasks, shop, achievements) lives in its own app.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models

STARTING_COINS = 15             # so the shop isn't empty-handed on day one


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
    """One wallet per user (also tracks streak + purchase counters)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='player'
    )
    coins = models.IntegerField(default=STARTING_COINS)
    # Achievement tracking (see achievements.services).
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

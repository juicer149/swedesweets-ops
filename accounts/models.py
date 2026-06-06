from __future__ import annotations

from django.conf import settings
from django.db import models

from accounts.roles import StaffAccessLevel


class StaffAccount(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="staff_account",
    )
    access_level = models.CharField(
        max_length=20,
        choices=StaffAccessLevel.choices(),
        default=StaffAccessLevel.RESTRICTED,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self) -> str:
        return f"{self.user} ({self.get_access_level_display()})"


class CustomerMembership(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_membership",
    )
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["customer__name", "user__username"]

    def __str__(self) -> str:
        return f"{self.user} -> {self.customer}"

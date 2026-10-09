from decimal import Decimal

from django.conf import settings
from django.db import models


class SessionStatus(models.TextChoices):
    UNASSIGNED = "unassigned", "Unassigned"
    ASSIGNED = "assigned", "Assigned"
    ACCEPTED_BY_PROVIDER = "accepted_by_provider", "Accepted by provider"
    IN_PROGRESS = "in_progress", "In progress"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class EndedBy(models.TextChoices):
    USER = "user", "User"
    PROVIDER = "provider", "Provider"
    SYSTEM = "system", "System"


class Session(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="booked_sessions",
    )
    provider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="provided_sessions",
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=32,
        choices=SessionStatus.choices,
        default=SessionStatus.UNASSIGNED,
    )
    per_minute_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("50.00"),
    )
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    billed_minutes = models.PositiveIntegerField(default=0)
    billed_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    billable_seconds = models.PositiveIntegerField(default=0)
    ended_by = models.CharField(max_length=16, choices=EndedBy.choices, blank=True)
    end_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status="in_progress"),
                name="one_in_progress_session_per_user",
            ),
        ]

    def __str__(self):
        return f"Session {self.pk} ({self.status})"


class BillingTick(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="billing_ticks")
    minute_index = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "minute_index"],
                name="unique_billing_tick_per_minute",
            ),
        ]

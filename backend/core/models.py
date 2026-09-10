"""Festival records. Financial records are retained; corrections use review/void actions."""

import hashlib
from uuid import uuid4
from django.conf import settings
from django.db import models
from django.utils import timezone


class Member(models.Model):
    name = models.CharField(max_length=120)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True)
    position = models.CharField(max_length=40, default="Volunteer")
    authority = models.CharField(max_length=160, default="Festival volunteer")
    joined_on = models.DateField(auto_now_add=True)
    active = models.BooleanField(default=True)


class Plan(models.Model):
    title = models.CharField(max_length=160)
    category = models.CharField(max_length=80)
    budget = models.DecimalField(max_digits=12, decimal_places=2)
    # Retained for migration compatibility; API calculates actual spending from approved expenses.
    spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=30, default="Planning")
    target_date = models.DateField(null=True, blank=True)


class Expense(models.Model):
    submission_key = models.UUIDField(null=True, blank=True, unique=True)
    submission_hash = models.CharField(max_length=64, blank=True)
    description = models.CharField(max_length=180)
    category = models.CharField(max_length=40, default="Operations")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    spent_on = models.DateField()
    plan = models.ForeignKey(
        Plan, null=True, blank=True, on_delete=models.PROTECT, related_name="expenses"
    )
    vendor = models.CharField(max_length=120, blank=True)
    receipt_reference = models.CharField(max_length=120, blank=True)
    evidence_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        default="pending",
        choices=[
            ("pending", "Pending review"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("void", "Voided"),
        ],
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="submitted_expenses",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_expenses",
    )
    reviewed_at = models.DateTimeField(null=True)
    review_note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["spent_on", "status"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(created_by__isnull=True) | models.Q(amount__gt=0),
                name="new_expense_amount_positive",
            )
        ]


class Payment(models.Model):
    submission_key = models.UUIDField(null=True, blank=True, unique=True)
    submission_hash = models.CharField(max_length=64, blank=True)
    donor_name = models.CharField(max_length=120)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=30, default="UPI")
    reference = models.CharField(max_length=80, unique=True)
    paid_on = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=30, default="pending")
    transaction_reference = models.CharField(max_length=120, blank=True)
    evidence_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="submitted_payments",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_payments",
    )
    reviewed_at = models.DateTimeField(null=True)
    review_note = models.CharField(max_length=500, blank=True)

    class Meta:
        indexes = [models.Index(fields=["paid_on", "status"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(created_by__isnull=True) | models.Q(amount__gt=0),
                name="new_payment_amount_positive",
            ),
            models.UniqueConstraint(
                fields=["method", "transaction_reference"],
                condition=~models.Q(transaction_reference="")
                & models.Q(status__in=["pending", "confirmed"]),
                name="unique_live_payment_transaction",
            ),
        ]


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ("admin", "Administrator"),
        ("treasurer", "Treasurer"),
        ("secretary", "Secretary"),
        ("coordinator", "Coordinator"),
        ("member", "Member"),
    ]
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    phone = models.CharField(max_length=30, blank=True, db_index=True)
    avatar_url = models.URLField(blank=True)
    phone_verified = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class ProfileImage(models.Model):
    # Kept separately so account lists never load image bytes. Database storage
    # survives app restarts/deployments and is included in normal database backups.
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    image = models.BinaryField()
    version = models.UUIDField(default=uuid4)


class OTPChallenge(models.Model):
    """Legacy records only. OTP API disabled until a verified delivery integration exists."""

    PURPOSE_CHOICES = [
        ("login", "Login"),
        ("password_reset", "Password reset"),
        ("verify_email", "Verify email"),
        ("verify_phone", "Verify phone"),
    ]
    channel = models.CharField(max_length=10, choices=[("email", "Email"), ("phone", "Phone")])
    destination = models.CharField(max_length=160)
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def verify(self, code):
        return (
            not self.used
            and self.expires_at > timezone.now()
            and self.attempts < 5
            and hashlib.sha256(str(code).encode()).hexdigest() == self.code_hash
        )


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    actor_name = models.CharField(max_length=150)
    action = models.CharField(max_length=40)
    resource = models.CharField(max_length=40)
    object_id = models.CharField(max_length=40)
    summary = models.CharField(max_length=240)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

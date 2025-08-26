# blood/models.py
from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone


# Supported blood types (RBC)
BLOOD_TYPES = [
    ("A+", "A+"), ("A-", "A-"),
    ("B+", "B+"), ("B-", "B-"),
    ("AB+", "AB+"), ("AB-", "AB-"),
    ("O+", "O+"), ("O-", "O-"),
]


class Donor(models.Model):
    national_id = models.CharField(
        "National ID",
        max_length=9,
        unique=True,
        db_index=True,
        validators=[RegexValidator(r"^\d{9}$", "National ID must be exactly 9 digits.")],
    )
    full_name = models.CharField("Full name", max_length=120)

    class Meta:
        ordering = ["full_name"]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.national_id})"


class DonationUnit(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        EXPIRED = "expired", "Expired"
        DISPENSED = "dispensed", "Dispensed"

    donor = models.ForeignKey(Donor, on_delete=models.CASCADE, related_name="donations")
    blood_type = models.CharField("Blood type", max_length=3, choices=BLOOD_TYPES)

    # When the donation was registered
    donation_date = models.DateTimeField("Donation time", auto_now_add=True)

    # Professional inventory fields
    expiry_at = models.DateTimeField("Expiry at", null=True, blank=True)
    status = models.CharField(
        "Status", max_length=16, choices=Status.choices, default=Status.AVAILABLE
    )
    dispensed_at = models.DateTimeField("Dispensed at", null=True, blank=True)

    class Meta:
        ordering = ["-donation_date"]
        indexes = [
            models.Index(fields=["blood_type", "status"]),
            models.Index(fields=["expiry_at"]),
        ]

    def is_expired(self) -> bool:
        return self.expiry_at is not None and self.expiry_at <= timezone.now()

    def __str__(self) -> str:
        when = self.donation_date.strftime("%Y-%m-%d %H:%M")
        return f"{self.blood_type} {when} - {self.donor.full_name}"


class DispenseLog(models.Model):
    requested_type = models.CharField("Requested type", max_length=3, choices=BLOOD_TYPES)
    quantity = models.PositiveIntegerField("Quantity")
    dispensed_map = models.JSONField("Dispensed map", default=dict)  # e.g. {"A+":2,"O-":1}
    created_at = models.DateTimeField("Created at", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        when = self.created_at.strftime("%Y-%m-%d %H:%M")
        return f"{self.requested_type} x{self.quantity} ({when})"

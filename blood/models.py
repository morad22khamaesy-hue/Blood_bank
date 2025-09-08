# blood/models.py
from django.db import models
from django.contrib.auth.models import User

# ---------------- Blood types ----------------
BLOOD_TYPES = [
    ("A+", "A+"), ("A-", "A-"),
    ("B+", "B+"), ("B-", "B-"),
    ("AB+", "AB+"), ("AB-", "AB-"),
    ("O+", "O+"), ("O-", "O-"),
]

# ---------------- User profile / roles ----------------
class Profile(models.Model):
    class Role(models.TextChoices):
        DONOR = "DONOR", "Donor"
        REQUESTER = "REQUESTER", "Requester"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=16, choices=Role.choices)

    # תוספות להרשמת תורם
    full_name = models.CharField(max_length=120, blank=True, default="")
    national_id = models.CharField(max_length=9, blank=True, default="")
    default_blood_type = models.CharField(max_length=3, choices=BLOOD_TYPES, blank=True, default="")

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

# ---------------- Core entities ----------------
class Donor(models.Model):
    national_id = models.CharField("National ID", max_length=9)
    full_name = models.CharField("Full name", max_length=120)
    def __str__(self): return f"{self.full_name} ({self.national_id})"

class DonationUnit(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        DISPENSED = "DISPENSED", "Dispensed"

    donor = models.ForeignKey(Donor, on_delete=models.CASCADE, related_name="donations")
    blood_type = models.CharField("Blood type", max_length=3, choices=BLOOD_TYPES)
    donation_date = models.DateTimeField("Donation time", auto_now_add=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.AVAILABLE)
    expiry_at = models.DateTimeField("Expiry at", null=True, blank=True)
    dispensed_at = models.DateTimeField("Dispensed at", null=True, blank=True)

    def __str__(self):
        return f"{self.blood_type} {self.donation_date:%Y-%m-%d %H:%M} - {self.donor.full_name}"

class DispenseLog(models.Model):
    requested_type = models.CharField("Requested type", max_length=3, choices=BLOOD_TYPES)
    quantity = models.PositiveIntegerField("Quantity")
    dispensed_map = models.JSONField("Dispensed map", default=dict)
    created_at = models.DateTimeField("Created at", auto_now_add=True)
    def __str__(self): return f"{self.requested_type} x{self.quantity} ({self.created_at:%Y-%m-%d %H:%M})"

class DispenseRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    class Urgency(models.TextChoices):
        REGULAR = "REGULAR", "Regular"
        URGENT = "URGENT", "Urgent"

    hospital_name = models.CharField(max_length=120)
    hospital_city = models.CharField(max_length=120, blank=True, default="")
    urgency = models.CharField(max_length=8, choices=Urgency.choices, default=Urgency.REGULAR)
    requested_type = models.CharField(max_length=3, choices=BLOOD_TYPES)
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=9, choices=Status.choices, default=Status.PENDING)
    plan = models.JSONField(default=dict, blank=True)
    shortfall = models.IntegerField(default=0)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.get_urgency_display()} {self.requested_type} x{self.quantity} → {self.hospital_name} ({self.status})"

class AuditEvent(models.Model):
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    role = models.CharField(max_length=16, blank=True, default="")
    session_key = models.CharField(max_length=64, blank=True, default="")
    action = models.CharField(max_length=64)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        who = self.user.username if self.user else "anon"
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {who} — {self.action}"

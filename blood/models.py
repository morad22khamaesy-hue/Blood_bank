# blood/models.py
from django.db import models
from django.contrib.auth.models import User

# -------------------- Constants --------------------
BLOOD_TYPES = [
    ("A+", "A+"), ("A-", "A-"),
    ("B+", "B+"), ("B-", "B-"),
    ("AB+", "AB+"), ("AB-", "AB-"),
    ("O+", "O+"), ("O-", "O-"),
]

# -------------------- Core domain --------------------
class Donor(models.Model):
    national_id = models.CharField("National ID", max_length=9, unique=True, db_index=True)
    full_name = models.CharField("Full name", max_length=120)
    date_of_birth = models.DateField("Date of birth", null=True, blank=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.full_name} ({self.national_id})"


class DonationUnit(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        DISPENSED = "DISPENSED", "Dispensed"

    donor = models.ForeignKey(Donor, on_delete=models.CASCADE, related_name="donations")
    blood_type = models.CharField("Blood type", max_length=3, choices=BLOOD_TYPES)
    donation_date = models.DateTimeField("Donation time", auto_now_add=True)
    expiry_at = models.DateTimeField("Expiry at", null=True, blank=True)
    status = models.CharField("Status", max_length=20, choices=Status.choices,
                              default=Status.AVAILABLE, db_index=True)
    dispensed_at = models.DateTimeField("Dispensed at", null=True, blank=True)

    class Meta:
        ordering = ["-donation_date"]

    def __str__(self):
        return f"{self.blood_type} {self.donation_date:%Y-%m-%d %H:%M} - {self.donor.full_name}"


class DispenseLog(models.Model):
    requested_type = models.CharField("Requested type", max_length=3, choices=BLOOD_TYPES)
    quantity = models.PositiveIntegerField("Quantity")
    dispensed_map = models.JSONField("Dispensed map", default=dict)
    created_at = models.DateTimeField("Created at", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.requested_type} x{self.quantity} ({self.created_at:%Y-%m-%d %H:%M})"


class DispenseRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    class Urgency(models.TextChoices):
        REGULAR = "REGULAR", "Regular"
        URGENT = "URGENT", "Urgent"

    hospital_name = models.CharField("Hospital name", max_length=120)
    hospital_city = models.CharField("Hospital city", max_length=80, blank=True)
    urgency = models.CharField("Urgency", max_length=10, choices=Urgency.choices, default=Urgency.REGULAR)
    requested_type = models.CharField("Requested type", max_length=3, choices=BLOOD_TYPES)
    quantity = models.PositiveIntegerField("Quantity")
    status = models.CharField("Status", max_length=10, choices=Status.choices,
                              default=Status.PENDING, db_index=True)
    plan = models.JSONField("Compatibility plan", default=dict, blank=True)
    shortfall = models.PositiveIntegerField("Shortfall", default=0)
    notes = models.TextField("Notes", blank=True)
    created_at = models.DateTimeField("Created at", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Req {self.requested_type} x{self.quantity} ({self.urgency}) - {self.hospital_name}"


# -------------------- Users & audit --------------------
class Profile(models.Model):
    class Role(models.TextChoices):
        DONOR = "DONOR", "Donor"
        REQUESTER = "REQUESTER", "Requester"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField("Role", max_length=12, choices=Role.choices)

    # פרטי תורם (רשות למבקשים)
    full_name = models.CharField("Full name", max_length=120, blank=True)
    # ייחודי כדי שלא יהיו שני משתמשים עם אותה ת"ז (רשות -> NULL/ריק מותר)
    national_id = models.CharField("National ID", max_length=9, unique=True, null=True, blank=True)
    default_blood_type = models.CharField("Default blood type", max_length=3, choices=BLOOD_TYPES, blank=True)
    date_of_birth = models.DateField("Date of birth", null=True, blank=True)
    photo = models.ImageField("Profile photo", upload_to="profiles/", null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class AuditEvent(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    role = models.CharField("Role at time", max_length=20, blank=True)
    session_key = models.CharField("Session key", max_length=64, blank=True)
    action = models.CharField("Action", max_length=50)
    details = models.JSONField("Details", default=dict, blank=True)
    created_at = models.DateTimeField("Created at", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        who = self.user.username if self.user else "anon"
        return f"{self.created_at:%Y-%m-%d %H:%M} [{self.role}] {who} -> {self.action}"

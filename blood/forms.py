from django import forms
from django.core.exceptions import ValidationError
from .models import Donor, DonationUnit, BLOOD_TYPES

class DispenseForm(forms.Form):
    blood_type = forms.ChoiceField(
        choices=[("", "Select blood type")] + BLOOD_TYPES,
        label="Requested blood type",
        widget=forms.Select(attrs={"class": "form-select"})
    )
    quantity = forms.IntegerField(
        min_value=1,
        label="Quantity",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 1})
    )

class DonationForm(forms.ModelForm):
    # National ID: exactly 9 digits, no letters
    national_id = forms.RegexField(
        label="National ID",
        regex=r"^\d{9}$",
        error_messages={"invalid": "Enter exactly 9 digits."},
        widget=forms.TextInput(attrs={
            "class": "form-control js-digits-only",
            "placeholder": "e.g., 123456789",
            "maxlength": "9",
            "pattern": r"\d{9}",
            "inputmode": "numeric",
            "autocomplete": "off",
        })
    )

    # Full name: letters only (any language) + spaces/hyphen/apostrophe – no digits/specials
    full_name = forms.CharField(
        label="Full name",
        widget=forms.TextInput(attrs={
            "class": "form-control js-letters-only",
            "placeholder": "Donor name",
            "autocomplete": "off",
        })
    )

    class Meta:
        model = DonationUnit
        fields = ["blood_type"]
        widgets = {
            "blood_type": forms.Select(attrs={"class": "form-select"})
        }
        labels = {"blood_type": "Blood type"}

    # Extra server-side safety for full_name (Unicode-safe)
    def clean_full_name(self):
        name = self.cleaned_data["full_name"].strip()
        if not name:
            raise ValidationError("Full name is required.")
        # allow letters in any language + space/hyphen/apostrophe
        for ch in name:
            if not (ch.isalpha() or ch in " -'"):
                raise ValidationError("Full name may contain letters, spaces, hyphens and apostrophes only.")
        # normalize double spaces etc. (optional)
        while "  " in name:
            name = name.replace("  ", " ")
        return name

    def save(self, commit=True):
        donor, _ = Donor.objects.get_or_create(
            national_id=self.cleaned_data["national_id"],
            defaults={"full_name": self.cleaned_data["full_name"]},
        )
        donation = super().save(commit=False)
        donation.donor = donor
        if commit:
            donation.save()
        return donation

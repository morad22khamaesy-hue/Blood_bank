# blood/forms.py
from django import forms
from django.core.validators import RegexValidator

# ⬇⬇⬇ הוספה חשובה ⬇⬇⬇
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
# ⬆⬆⬆ הוספה חשובה ⬆⬆⬆

from .models import Donor, DonationUnit, BLOOD_TYPES, Profile
from django.utils import timezone

# -------------------------------------------------------------------
# Comprehensive hospitals list (Israel) → value: "Name|City", label: "Name — City"
# -------------------------------------------------------------------
HOSPITAL_CHOICES = [
    ("", "Choose hospital"),
    # --- Jerusalem District ---
    ("Shaare Zedek Medical Center|Jerusalem", "Shaare Zedek Medical Center — Jerusalem"),
    ("Hadassah Ein Kerem Hospital|Jerusalem", "Hadassah Ein Kerem Hospital — Jerusalem"),
    ("Hadassah Mount Scopus Hospital|Jerusalem", "Hadassah Mount Scopus Hospital — Jerusalem"),
    ("Herzog Medical Center|Jerusalem", "Herzog Medical Center — Jerusalem"),
    ("ALYN Hospital|Jerusalem", "ALYN Hospital — Jerusalem"),
    ("Misgav Ladach|Jerusalem", "Misgav Ladach — Jerusalem"),
    ("Saint John Eye Hospital|Jerusalem", "Saint John Eye Hospital — Jerusalem"),
    ("Saint Louis French Hospital|Jerusalem", "Saint Louis French Hospital — Jerusalem"),
    ("Kfar Shaul Mental Health Center|Jerusalem", "Kfar Shaul Mental Health Center — Jerusalem"),
    ("Eitanim Psychiatric Hospital|Jerusalem", "Eitanim Psychiatric Hospital — Jerusalem"),
    ("Augusta Victoria Hospital|Jerusalem", "Augusta Victoria Hospital — Jerusalem"),
    ("Al-Makassed Islamic Charitable Hospital|Jerusalem", "Al-Makassed Islamic Charitable Hospital — Jerusalem"),
    ("Amal Hod Adumim (Geriatric/Rehab)|Ma'ale Adumim", "Amal Hod Adumim (Geriatric/Rehab) — Ma'ale Adumim"),

    # --- Tel Aviv District ---
    ("Tel Aviv Sourasky Medical Center (Ichilov)|Tel Aviv", "Tel Aviv Sourasky Medical Center (Ichilov) — Tel Aviv"),
    ("Assuta Medical Center|Tel Aviv", "Assuta Medical Center — Tel Aviv"),
    ("Reuth Medical and Rehabilitation Center|Tel Aviv", "Reuth Medical and Rehabilitation Center — Tel Aviv"),
    ("Naot Hatikhon Geriatric Center|Tel Aviv", "Naot Hatikhon Geriatric Center — Tel Aviv"),
    ("Wolfson Medical Center|Holon", "Wolfson Medical Center — Holon"),
    ("Sheba Medical Center (Tel HaShomer)|Ramat Gan", "Sheba Medical Center (Tel HaShomer) — Ramat Gan"),
    ("Ramat Marpe Hospital|Ramat Gan", "Ramat Marpe Hospital — Ramat Gan"),
    ("Mayanei Hayeshua Medical Center|Bnei Brak", "Mayanei Hayeshua Medical Center — Bnei Brak"),
    ("Herzliya Medical Center|Herzliya", "Herzliya Medical Center — Herzliya"),
    ("Abarbanel Psychiatric Hospital|Bat Yam", "Abarbanel Psychiatric Hospital — Bat Yam"),
    ("Bayit Balev Rehabilitation Hospital|Bat Yam", "Bayit Balev Rehabilitation Hospital — Bat Yam"),
    ("Assuta Medical Center|Rishon LeZion", "Assuta Medical Center — Rishon LeZion"),

    # --- Central District ---
    ("Yitzhak Shamir Medical Center (Assaf Harofeh)|Be'er Ya'akov", "Yitzhak Shamir Medical Center (Assaf Harofeh) — Be'er Ya'akov"),
    ("Shmuel HaRofeh Geriatric Hospital|Be'er Ya'akov", "Shmuel HaRofeh Geriatric Hospital — Be'er Ya'akov"),
    ("Herzfeld Geriatric Hospital|Gedera", "Herzfeld Geriatric Hospital — Gedera"),
    ("Ganim Sanatorium|Gedera", "Ganim Sanatorium — Gedera"),
    ("Shalvata Mental Health Center|Hod HaSharon", "Shalvata Mental Health Center — Hod HaSharon"),
    ("Kiryat Shlomo Geriatric Hospital|Hof HaSharon", "Kiryat Shlomo Geriatric Hospital — Hof HaSharon"),
    ("Meir Medical Center (Sapir)|Kfar Saba", "Meir Medical Center (Sapir) — Kfar Saba"),
    ("Lev HaSharon Psychiatric Hospital|Lev HaSharon", "Lev HaSharon Psychiatric Hospital — Lev HaSharon"),
    ("Ness Ziona Psychiatric Hospital|Ness Ziona", "Ness Ziona Psychiatric Hospital — Ness Ziona"),
    ("Laniado Hospital|Netanya", "Laniado Hospital — Netanya"),
    ("Netanya Geriatric Medical Center|Netanya", "Netanya Geriatric Medical Center — Netanya"),
    ("Rabin Medical Center (Beilinson)|Petah Tikva", "Rabin Medical Center (Beilinson) — Petah Tikva"),
    ("Rabin Medical Center (HaSharon/Golda)|Petah Tikva", "Rabin Medical Center (HaSharon/Golda) — Petah Tikva"),
    ("Geha Mental Health Center|Petah Tikva", "Geha Mental Health Center — Petah Tikva"),
    ("Beit Rivka Geriatric Hospital|Petah Tikva", "Beit Rivka Geriatric Hospital — Petah Tikva"),
    ("Loewenstein Rehabilitation Center|Ra'anana", "Loewenstein Rehabilitation Center — Ra'anana"),
    ("Kaplan Medical Center|Rehovot", "Kaplan Medical Center — Rehovot"),

    # --- Haifa District ---
    ("Hillel Yaffe Medical Center|Hadera", "Hillel Yaffe Medical Center — Hadera"),
    ("Rambam Health Care Campus|Haifa", "Rambam Health Care Campus — Haifa"),
    ("Carmel Medical Center|Haifa", "Carmel Medical Center — Haifa"),
    ("Bnai Zion Medical Center|Haifa", "Bnai Zion Medical Center — Haifa"),
    ("Horev Medical Center|Haifa", "Horev Medical Center — Haifa"),
    ("Elisha Medical Center|Haifa", "Elisha Medical Center — Haifa"),
    ("Italian Hospital in Haifa|Haifa", "Italian Hospital in Haifa — Haifa"),
    ("Fliman Geriatric Hospital|Haifa", "Fliman Geriatric Hospital — Haifa"),
    ("Dekel Medical Center|Daliyat al-Karmel", "Dekel Medical Center — Daliyat al-Karmel"),
    ("Shoham Geriatric Medical Center|Pardes Hanna-Karkur", "Shoham Geriatric Medical Center — Pardes Hanna-Karkur"),
    ("Sha'ar Menashe Mental Health Center|Pardes Hanna-Karkur", "Sha'ar Menashe Mental Health Center — Pardes Hanna-Karkur"),
    ("Neve Shalva (Psychiatric)|Pardes Hanna-Karkur", "Neve Shalva (Psychiatric) — Pardes Hanna-Karkur"),
    ("Ma'ale Hacarmel Mental Health Center|Tirat Carmel", "Ma'ale Hacarmel Mental Health Center — Tirat Carmel"),

    # --- Northern District ---
    ("HaEmek Medical Center|Afula", "HaEmek Medical Center — Afula"),
    ("Fligelman (Mazra) Psychiatric Hospital|Acre", "Fligelman (Mazra) Psychiatric Hospital — Acre"),
    ("Galilee Medical Center (Western Galilee)|Nahariya", "Galilee Medical Center (Western Galilee) — Nahariya"),
    ("Ziv Medical Center (Rebecca Sieff)|Safed", "Ziv Medical Center (Rebecca Sieff) — Safed"),
    ("Poriya / Baruch Padeh Medical Center|Tiberias", "Poriya / Baruch Padeh Medical Center — Tiberias"),
    ("EMMS Nazareth Hospital (Scottish)|Nazareth", "EMMS Nazareth Hospital (Scottish) — Nazareth"),
    ("French Nazareth Hospital (Saint Vincent)|Nazareth", "French Nazareth Hospital (Saint Vincent) — Nazareth"),
    ("Holy Family Hospital (Italian)|Nazareth", "Holy Family Hospital (Italian) — Nazareth"),

    # --- Southern District ---
    ("Assuta Ashdod University Hospital|Ashdod", "Assuta Ashdod University Hospital — Ashdod"),
    ("Barzilai Medical Center|Ashkelon", "Barzilai Medical Center — Ashkelon"),
    ("Soroka University Medical Center|Beersheba", "Soroka University Medical Center — Beersheba"),
    ("Assuta Beersheba Medical Center|Beersheba", "Assuta Beersheba Medical Center — Beersheba"),
    ("Yoseftal Medical Center|Eilat", "Yoseftal Medical Center — Eilat"),
    ("ADI Negev Kaylie Rehabilitation Medical Center|Ofakim", "ADI Negev Kaylie Rehabilitation Medical Center — Ofakim"),
]

URGENCY_CHOICES = [
    ("REGULAR", "Regular"),
    ("URGENT", "Urgent"),
]

# ---------------- Validators ----------------
digits_9_validator = RegexValidator(regex=r"^\d{9}$", message="National ID must be exactly 9 digits.")
name_validator = RegexValidator(regex=r"^[A-Za-z\u0590-\u05FF\s'\-]{2,}$",
                                message="Name may contain letters, spaces, apostrophes, and hyphens only.")

# ==================== Auth forms ====================
class SignupForm(UserCreationForm):
    ROLE_CHOICES = [(Profile.Role.DONOR, "Register as Donor"),
                    (Profile.Role.REQUESTER, "Register as Requester")]
    role = forms.ChoiceField(choices=ROLE_CHOICES, label="Role",
                             widget=forms.Select(attrs={"class": "form-select"}))

    # Donor-only
    full_name = forms.CharField(label="Full name", required=False, validators=[name_validator],
                                widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Full name"}))
    national_id = forms.CharField(label="National ID", required=False, validators=[digits_9_validator],
                                  widget=forms.TextInput(attrs={
                                      "class": "form-control", "placeholder": "9 digits",
                                      "maxlength": "9", "inputmode": "numeric", "pattern": r"\d{9}",
                                  }))
    donor_blood_type = forms.ChoiceField(label="Blood type (for donors)", required=False,
                                         choices=[("", "Choose blood type")] + BLOOD_TYPES,
                                         widget=forms.Select(attrs={"class": "form-select"}))
    date_of_birth = forms.DateField(label="Date of birth (for donors)", required=False,
                                    widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))

    class Meta:
        model = User
        fields = ["username", "password1", "password2",
                  "role", "full_name", "national_id", "donor_blood_type", "date_of_birth"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({"class": "form-control", "placeholder": "Username"})
        self.fields["password1"].widget.attrs.update({"class": "form-control", "placeholder": "Password"})
        self.fields["password2"].widget.attrs.update({"class": "form-control", "placeholder": "Confirm password"})

    # מניעת ת"ז כפולה
    def clean_national_id(self):
        nid = (self.cleaned_data.get("national_id") or "").strip()
        role = self.cleaned_data.get("role")
        if role == Profile.Role.DONOR:
            if not nid:
                raise forms.ValidationError("National ID is required for donors.")
            if Profile.objects.filter(national_id=nid).exists():
                raise forms.ValidationError("This National ID is already registered.")
        return nid

    def clean(self):
        data = super().clean()
        role = data.get("role")
        if role == Profile.Role.DONOR:
            if not data.get("full_name"):
                self.add_error("full_name", "Full name is required for donors.")
            if not data.get("donor_blood_type"):
                self.add_error("donor_blood_type", "Blood type is required for donors.")
            dob = data.get("date_of_birth")
            if not dob:
                self.add_error("date_of_birth", "Date of birth is required for donors.")
            else:
                if dob > timezone.now().date():
                    self.add_error("date_of_birth", "Date of birth cannot be in the future.")
        return data

    def save(self, commit=True):
        user = super().save(commit=commit)
        role = self.cleaned_data["role"]
        full_name = (self.cleaned_data.get("full_name") or "").strip()
        national_id = (self.cleaned_data.get("national_id") or "").strip()
        donor_bt = (self.cleaned_data.get("donor_blood_type") or "").strip()
        dob = self.cleaned_data.get("date_of_birth")

        if commit:
            Profile.objects.create(
                user=user, role=role,
                full_name=full_name if role == Profile.Role.DONOR else "",
                national_id=national_id if role == Profile.Role.DONOR else "",
                default_blood_type=donor_bt if role == Profile.Role.DONOR else "",
                date_of_birth=dob if role == Profile.Role.DONOR else None,
            )
            if role == Profile.Role.DONOR and national_id:
                donor, _ = Donor.objects.get_or_create(
                    national_id=national_id,
                    defaults={"full_name": full_name or user.username, "date_of_birth": dob},
                )
                # סינכרון שם אם השתנה
                if full_name and donor.full_name != full_name:
                    donor.full_name = full_name
                    donor.save(update_fields=["full_name"])
        else:
            user._selected_role = role
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Username",
                               widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Username"}))
    password = forms.CharField(label="Password",
                               widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Password"}))

# --------- Profile update ----------
class ProfileUpdateForm(forms.ModelForm):
    national_id = forms.CharField(label="National ID", required=False, validators=[digits_9_validator],
                                  widget=forms.TextInput(attrs={"class": "form-control", "maxlength": "9"}))
    full_name = forms.CharField(label="Full name", required=False, validators=[name_validator],
                                widget=forms.TextInput(attrs={"class": "form-control"}))
    default_blood_type = forms.ChoiceField(label="Blood type", required=False,
                                           choices=[("", "—")] + BLOOD_TYPES,
                                           widget=forms.Select(attrs={"class": "form-select"}))
    date_of_birth = forms.DateField(label="Birth date", required=False,
                                    widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    photo = forms.ImageField(label="Profile photo", required=False,
                             widget=forms.ClearableFileInput(attrs={"class": "form-control"}))

    class Meta:
        model = Profile
        fields = ["full_name", "national_id", "default_blood_type", "date_of_birth", "photo"]

    def clean_national_id(self):
        nid = (self.cleaned_data.get("national_id") or "").strip()
        if nid and Profile.objects.exclude(pk=self.instance.pk).filter(national_id=nid).exists():
            raise forms.ValidationError("This National ID is already registered to another account.")
        return nid

    def save(self, commit=True):
        profile = super().save(commit=commit)
        # שמירת/סנכרון Donor
        if commit and profile.national_id:
            donor, _ = Donor.objects.get_or_create(
                national_id=profile.national_id,
                defaults={"full_name": profile.full_name or profile.user.username,
                          "date_of_birth": profile.date_of_birth},
            )
            changed = False
            if profile.full_name and donor.full_name != profile.full_name:
                donor.full_name = profile.full_name
                changed = True
            if profile.date_of_birth and donor.date_of_birth != profile.date_of_birth:
                donor.date_of_birth = profile.date_of_birth
                changed = True
            if changed:
                donor.save()
        return profile

# ==================== Domain forms ====================
class DispenseForm(forms.Form):
    urgency = forms.ChoiceField(choices=URGENCY_CHOICES, label="Urgency",
                                widget=forms.Select(attrs={"class": "form-select"}))
    hospital = forms.ChoiceField(choices=HOSPITAL_CHOICES, label="Hospital",
                                 widget=forms.Select(attrs={"class": "form-select"}))
    blood_type = forms.ChoiceField(choices=[("", "Choose blood type")] + BLOOD_TYPES,
                                   label="Requested blood type",
                                   widget=forms.Select(attrs={"class": "form-select"}))
    quantity = forms.IntegerField(min_value=1, label="Quantity",
                                  widget=forms.NumberInput(attrs={"class": "form-control", "min": "1"}))
    notes = forms.CharField(label="Notes", required=False,
                            widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))

    def clean_hospital(self):
        val = self.cleaned_data["hospital"]
        if not val or "|" not in val:
            raise forms.ValidationError("Please choose a hospital from the list.")
        return val


class DonationForm(forms.ModelForm):
    national_id = forms.CharField(label="National ID", validators=[digits_9_validator])
    full_name = forms.CharField(label="Full name", validators=[name_validator])

    class Meta:
        model = DonationUnit
        fields = ["blood_type"]
        widgets = {"blood_type": forms.Select(attrs={"class": "form-select"})}

    def save(self, commit=True):
        donor, _ = Donor.objects.get_or_create(
            national_id=self.cleaned_data["national_id"],
            defaults={"full_name": self.cleaned_data["full_name"]},
        )
        if donor.full_name != self.cleaned_data["full_name"]:
            donor.full_name = self.cleaned_data["full_name"]
            donor.save(update_fields=["full_name"])

        donation = super().save(commit=False)
        donation.donor = donor
        if commit:
            donation.save()
        return donation
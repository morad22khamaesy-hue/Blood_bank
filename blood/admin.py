from django.contrib import admin
from .models import Donor, DonationUnit

admin.site.register(Donor)
admin.site.register(DonationUnit)

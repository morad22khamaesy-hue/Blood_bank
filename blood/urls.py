# blood/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("intake/", views.intake, name="intake"),
    path("dispense/", views.dispense, name="dispense"),
    path("donations/", views.donations_list, name="donations_list"),
    path("donations/export/", views.donations_export, name="donations_export"),
    path("inventory/", views.inventory_dashboard, name="inventory"),
]

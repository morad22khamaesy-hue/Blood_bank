# blood/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),

    # auth
    path("signup/", views.signup, name="signup"),
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),

    # donor / requester
    path("intake/", views.intake, name="intake"),
    path("dispense/", views.dispense, name="dispense"),
    path("profile/", views.profile, name="profile"),

    # manager portal
    path("portal/login/", views.portal_login, name="portal_login"),
    path("portal/logout/", views.portal_logout, name="portal_logout"),

    # manager pages
    path("records/", views.records, name="records"),
    path("records/export/", views.donations_export, name="donations_export"),
    path("records/dispensed/export/", views.dispensed_export, name="dispensed_export"),

    path("inventory/", views.inventory_dashboard, name="inventory"),
    path("requests/<int:pk>/approve/", views.request_approve, name="request_approve"),
    path("requests/<int:pk>/reject/", views.request_reject, name="request_reject"),

    path("donations/<int:pk>/delete/", views.donation_delete, name="donation_delete"),
]

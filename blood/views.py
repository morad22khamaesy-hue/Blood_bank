# blood/views.py
from urllib.parse import urlencode
from datetime import timedelta
import csv

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone

from .forms import DonationForm, DispenseForm
from .models import DonationUnit, DispenseLog, BLOOD_TYPES
from .compat import plan_dispense


def home(request):
    return render(request, "blood/home.html")


def intake(request):
    if request.method == "POST":
        form = DonationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Donation saved successfully.")
            return redirect("home")
    else:
        form = DonationForm()
    return render(request, "blood/intake.html", {"form": form})


def dispense(request):
    """
    Dispense units using compatibility plan + FEFO (closest expiry first).
    Works only with AVAILABLE and non-expired units.
    """
    result = None
    plan = None

    if request.method == "POST":
        form = DispenseForm(request.POST)
        if form.is_valid():
            btype = form.cleaned_data["blood_type"]
            qty = form.cleaned_data["quantity"]
            now = timezone.now()

            # count available & non-expired inventory by blood type
            counts_qs = (
                DonationUnit.objects.filter(status=DonationUnit.Status.AVAILABLE)
                .filter(Q(expiry_at__isnull=True) | Q(expiry_at__gt=now))
                .values("blood_type")
                .annotate(cnt=Count("id"))
            )
            inventory_counts = {row["blood_type"]: row["cnt"] for row in counts_qs}

            # build compatibility plan
            plan, shortfall = plan_dispense(btype, qty, inventory_counts)

            if shortfall == 0 and plan:
                # FEFO: take closest-to-expiry first (then by donation_date)
                for dtype, take in plan.items():
                    units = (
                        DonationUnit.objects.filter(
                            blood_type=dtype, status=DonationUnit.Status.AVAILABLE
                        )
                        .filter(Q(expiry_at__isnull=True) | Q(expiry_at__gt=now))
                        .order_by("expiry_at", "donation_date")[:take]
                    )
                    ids = list(units.values_list("id", flat=True))
                    if ids:
                        DonationUnit.objects.filter(id__in=ids).update(
                            status=DonationUnit.Status.DISPENSED,
                            dispensed_at=now,
                        )

                DispenseLog.objects.create(
                    requested_type=btype, quantity=qty, dispensed_map=plan
                )
                result = f"Dispensed {qty} unit(s) for {btype}."
                messages.success(request, result)
            else:
                if plan:
                    partial = sum(plan.values())
                    result = (
                        f"Cannot fully dispense {qty} unit(s) for {btype}. "
                        f"Available now: {partial} compatible unit(s)."
                    )
                else:
                    result = f"No compatible inventory for {qty} unit(s) of {btype}."
                messages.warning(request, result)
    else:
        form = DispenseForm()

    return render(
        request, "blood/dispense.html", {"form": form, "result": result, "plan": plan}
    )


def donations_list(request):
    """
    Donations table with filtering by blood type, sorting, and pagination.
    """
    blood_type = request.GET.get("blood_type", "").strip()
    sort_key = request.GET.get("sort", "recent").strip()

    qs = DonationUnit.objects.select_related("donor")
    if blood_type:
        qs = qs.filter(blood_type=blood_type)

    sort_map = {
        "recent": "-donation_date",  # newest first
        "oldest": "donation_date",
        "name": "donor__full_name",
        "type": "blood_type",
    }
    order_by = sort_map.get(sort_key, "-donation_date")
    qs = qs.order_by(order_by)

    paginator = Paginator(qs, 12)
    page = request.GET.get("page")
    donations = paginator.get_page(page)

    # keep filters in pagination links
    qp = {}
    if blood_type:
        qp["blood_type"] = blood_type
    if sort_key and sort_key != "recent":
        qp["sort"] = sort_key
    qs_no_page = urlencode(qp)

    context = {
        "donations": donations,
        "blood_types": BLOOD_TYPES,
        "current_blood_type": blood_type,
        "current_sort": sort_key,
        "qs_no_page": qs_no_page,
    }
    return render(request, "blood/donations_list.html", context)


def donations_export(request):
    """
    Export filtered/sorted donations to CSV (without National ID).
    """
    blood_type = request.GET.get("blood_type", "").strip()
    sort_key = request.GET.get("sort", "recent").strip()

    qs = DonationUnit.objects.select_related("donor")
    if blood_type:
        qs = qs.filter(blood_type=blood_type)

    sort_map = {
        "recent": "-donation_date",
        "oldest": "donation_date",
        "name": "donor__full_name",
        "type": "blood_type",
    }
    order_by = sort_map.get(sort_key, "-donation_date")
    qs = qs.order_by(order_by)

    # CSV response (no sensitive ID)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="donations.csv"'
    writer = csv.writer(response)
    writer.writerow(["Donor name", "Blood type", "Donation time"])
    for d in qs:
        writer.writerow([d.donor.full_name, d.blood_type, d.donation_date.strftime("%Y-%m-%d %H:%M")])
    return response


def inventory_dashboard(request):
    """
    Inventory summary with counts per blood type and near-expiry counts.
    Also passes 'rows' for an easy table, and JSON-safe series for Chart.js.
    """
    now = timezone.now()
    near_days = getattr(settings, "NEAR_EXPIRY_DAYS", 7)
    near_cutoff = now + timedelta(days=near_days)

    base_qs = (
        DonationUnit.objects.filter(status=DonationUnit.Status.AVAILABLE)
        .filter(Q(expiry_at__isnull=True) | Q(expiry_at__gt=now))
    )

    # total counts per type
    counts = {bt: 0 for bt, _ in BLOOD_TYPES}
    for row in base_qs.values("blood_type").annotate(cnt=Count("id")):
        counts[row["blood_type"]] = row["cnt"]

    # near-expiry counts per type
    near_counts = {bt: 0 for bt, _ in BLOOD_TYPES}
    for row in (
        base_qs.filter(expiry_at__isnull=False, expiry_at__lte=near_cutoff)
        .values("blood_type")
        .annotate(cnt=Count("id"))
    ):
        near_counts[row["blood_type"]] = row["cnt"]

    labels = [bt for bt, _ in BLOOD_TYPES]
    values = [counts[bt] for bt in labels]
    near_values = [near_counts[bt] for bt in labels]
    rows = [{"bt": bt, "total": counts[bt], "near": near_counts[bt]} for bt in labels]

    context = {
        "near_days": near_days,
        "labels": labels,
        "values": values,
        "near_values": near_values,
        "rows": rows,  # for simple table loop
    }
    return render(request, "blood/inventory_dashboard.html", context)

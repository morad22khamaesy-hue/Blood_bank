# blood/views.py
from urllib.parse import urlencode
from datetime import timedelta
import csv
import io
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from .forms import ProfileUpdateForm

from .forms import DonationForm, DispenseForm, SignupForm, LoginForm
from .models import (
    DonationUnit, DispenseLog, BLOOD_TYPES,
    DispenseRequest, Profile, AuditEvent, Donor
)
from .compat import plan_dispense

# ========= Admin display for portal events =========
ADMIN_DISPLAY_NAME = "MORAD"
ADMIN_ROLE_LABEL = "ADMIN"


# ------------------------ helpers ------------------------
def _urgent_pending_count():
    return DispenseRequest.objects.filter(
        status=DispenseRequest.Status.PENDING,
        urgency=DispenseRequest.Urgency.URGENT,
    ).count()


def _get_role(request):
    if request.user.is_authenticated and hasattr(request.user, "profile"):
        return request.user.profile.role
    return ""


def _ensure_session_key(request):
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key


def log_event(request, action, role=None, user_display=None, **details):
    """
    Create AuditEvent.
    role – override role shown on the row (default: current user's role).
    user_display – override display name (e.g., MORAD on portal logins).
    details – extra dict persisted.
    """
    role_val = role if role is not None else _get_role(request)
    skey = _ensure_session_key(request)
    payload = details or {}
    if user_display:
        payload["display_user"] = user_display
    AuditEvent.objects.create(
        user=request.user if request.user.is_authenticated else None,
        role=role_val or "",
        session_key=skey or "",
        action=action,
        details=payload,
    )


# ------------------------ role guards ------------------------
def role_required(expected_role):
    def decorator(view_func):
        @wraps(view_func)
        @login_required(login_url="login")
        def _wrapped(request, *args, **kwargs):
            role = _get_role(request)
            if role != expected_role:
                messages.error(request, "You do not have access to this page.")
                return redirect("home")
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


# ------------------------ manager portal (password per page) ------------------------
def portal_protected(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        # one-time access for this request only
        if request.session.pop("portal_once_ok", False):
            return view_func(request, *args, **kwargs)
        request.session["portal_next"] = request.get_full_path()
        return redirect("portal_login")
    return _wrapped


def portal_login(request):
    """
    Ask for portal password. On success, permit a single page load,
    and log PORTAL_LOGIN with ROLE=ADMIN and USER=MORAD to the audit table.
    """
    error = None
    if request.method == "POST":
        pwd = (request.POST.get("password") or "").strip()
        portal_pwd = (getattr(settings, "PORTAL_PASSWORD", "") or "change-me")
        if pwd == portal_pwd:
            request.session["portal_once_ok"] = True
            messages.success(request, "Access granted.")
            log_event(
                request,
                action="PORTAL_LOGIN",
                role=ADMIN_ROLE_LABEL,
                user_display=ADMIN_DISPLAY_NAME,
            )
            next_url = request.session.pop("portal_next", None) or reverse("records")
            return redirect(next_url)
        error = "Incorrect password."
        messages.error(request, error)

    ctx = {"error": error, "urgent_pending_count": _urgent_pending_count()}
    return render(request, "blood/portal_login.html", ctx)


def portal_logout(request):
    request.session.pop("portal_once_ok", None)
    request.session.pop("portal_next", None)
    messages.info(request, "You have been logged out.")
    log_event(
        request,
        action="PORTAL_LOGOUT",
        role=ADMIN_ROLE_LABEL,
        user_display=ADMIN_DISPLAY_NAME,
    )
    return redirect("portal_login")


# ------------------------ auth ------------------------
def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, "Welcome! Your account was created.")
            log_event(request, "signup", role=_get_role(request))
            return redirect("home")
    else:
        form = SignupForm()
    return render(
        request,
        "blood/signup.html",
        {"form": form, "urgent_pending_count": _urgent_pending_count(), "user_role": _get_role(request)},
    )


def login(request):
    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            messages.success(request, "Signed in successfully.")
            log_event(request, "login", role=_get_role(request))
            return redirect("home")
    else:
        form = LoginForm(request)
    return render(
        request,
        "blood/login.html",
        {"form": form, "urgent_pending_count": _urgent_pending_count(), "user_role": _get_role(request)},
    )


def logout(request):
    log_event(request, "logout", role=_get_role(request))
    auth_logout(request)
    messages.info(request, "You have been signed out.")
    return redirect("home")


# ------------------------ public ------------------------
def home(request):
    return render(
        request,
        "blood/home.html",
        {"urgent_pending_count": _urgent_pending_count(), "user_role": _get_role(request)},
    )


# ------------------------ donor only ------------------------
@role_required(Profile.Role.DONOR)
def intake(request):
    """
    Intake page: fields are locked and prefilled from Profile.
    """
    prof = getattr(request.user, "profile", None)
    initial_full_name = (
        prof.full_name if prof and prof.full_name else request.user.get_full_name() or request.user.username
    )
    initial = {
        "national_id": prof.national_id if prof else "",
        "full_name": initial_full_name,
        "blood_type": prof.default_blood_type if prof else "",
    }

    if request.method == "POST":
        # lock values (ignore client-side edits)
        post_data = {
            "national_id": initial["national_id"],
            "full_name": initial["full_name"],
            "blood_type": initial["blood_type"],
        }
        form = DonationForm(post_data)
        if form.is_valid():
            donation = form.save()
            messages.success(request, "Donation saved successfully.")
            log_event(
                request,
                "donation_create",
                blood_type=donation.blood_type,
                donor=donation.donor.full_name,
            )
            return redirect("home")
        else:
            messages.error(request, "Could not save donation. Please contact support.")
    else:
        form = DonationForm(initial=initial)

    return render(
        request,
        "blood/intake.html",
        {
            "form": form,
            "lock_fields": True,
            "urgent_pending_count": _urgent_pending_count(),
            "user_role": _get_role(request),
        },
    )


# ------------------------ requester only ------------------------
@role_required(Profile.Role.REQUESTER)
def dispense(request):
    """
    Create dispense request (only if stock is sufficient), plus show all requests.
    """
    requests_all = DispenseRequest.objects.all().order_by("-created_at")

    if request.method == "POST":
        form = DispenseForm(request.POST)
        if form.is_valid():
            urgency = form.cleaned_data["urgency"]
            hospital_raw = form.cleaned_data["hospital"]
            blood_type = form.cleaned_data["blood_type"]
            qty = form.cleaned_data["quantity"]
            notes = form.cleaned_data.get("notes", "").strip()

            if "|" in hospital_raw:
                hospital_name, hospital_city = [x.strip() for x in hospital_raw.split("|", 1)]
            else:
                hospital_name, hospital_city = hospital_raw, ""

            now = timezone.now()
            counts_qs = (
                DonationUnit.objects.filter(status=DonationUnit.Status.AVAILABLE)
                .filter(Q(expiry_at__isnull=True) | Q(expiry_at__gt=now))
                .values("blood_type")
                .annotate(cnt=Count("id"))
            )
            inventory_counts = {row["blood_type"]: row["cnt"] for row in counts_qs}
            plan, shortfall = plan_dispense(blood_type, qty, inventory_counts)

            # insufficient stock => do not submit request
            if not plan or (shortfall and shortfall > 0):
                if not plan or shortfall == qty:
                    messages.error(
                        request,
                        f"No compatible inventory available now for {blood_type}. The request was not submitted.",
                    )
                    log_event(
                        request,
                        "dispense_request_failed",
                        blood_type=blood_type,
                        qty=qty,
                        reason="no_stock",
                    )
                else:
                    available_now = qty - shortfall
                    messages.error(
                        request,
                        f"Insufficient stock for {blood_type}: requested {qty}, available {available_now}. The request was not submitted.",
                    )
                    log_event(
                        request,
                        "dispense_request_failed",
                        blood_type=blood_type,
                        qty=qty,
                        reason="partial_stock",
                        available=available_now,
                    )
                return redirect("dispense")

            # ok → pending manager approval
            DispenseRequest.objects.create(
                hospital_name=hospital_name,
                hospital_city=hospital_city,
                urgency=urgency,
                requested_type=blood_type,
                quantity=qty,
                status=DispenseRequest.Status.PENDING,
                plan=plan,
                shortfall=0,
                notes=notes,
            )
            log_event(
                request,
                "dispense_request_created",
                blood_type=blood_type,
                qty=qty,
                urgency=urgency,
                hospital=hospital_name,
            )
            messages.success(request, "Request submitted and pending manager approval.")
            return redirect("dispense")
    else:
        form = DispenseForm()

    return render(
        request,
        "blood/dispense.html",
        {
            "form": form,
            "requests_all": requests_all,
            "urgent_pending_count": _urgent_pending_count(),
            "user_role": _get_role(request),
        },
    )


# ------------------------ manager (portal-protected) ------------------------
@portal_protected
def records(request):
    """
    Records page:
    A: intake donations
    B: dispensed units
    """
    blood_type = request.GET.get("blood_type", "").strip()
    sort_key = request.GET.get("sort", "recent").strip()

    # A – donations
    in_qs = DonationUnit.objects.select_related("donor")
    if blood_type:
        in_qs = in_qs.filter(blood_type=blood_type)
    sort_map_in = {
        "recent": "-donation_date",
        "oldest": "donation_date",
        "name": "donor__full_name",
        "type": "blood_type",
    }
    in_order = sort_map_in.get(sort_key, "-donation_date")
    in_qs = in_qs.order_by(in_order)
    in_pager = Paginator(in_qs, 12)
    in_page = request.GET.get("page")
    donations = in_pager.get_page(in_page)

    # B – dispensed
    out_qs = DonationUnit.objects.filter(status=DonationUnit.Status.DISPENSED).select_related("donor")
    if blood_type:
        out_qs = out_qs.filter(blood_type=blood_type)
    sort_map_out = {
        "recent": "-dispensed_at",
        "oldest": "dispensed_at",
        "name": "donor__full_name",
        "type": "blood_type",
    }
    out_order = sort_map_out.get(sort_key, "-dispensed_at")
    out_qs = out_qs.order_by(out_order)
    out_pager = Paginator(out_qs, 12)
    out_page = request.GET.get("dpage")
    dispensed = out_pager.get_page(out_page)

    qp = {}
    if blood_type:
        qp["blood_type"] = blood_type
    if sort_key and sort_key != "recent":
        qp["sort"] = sort_key
    qs_no_page = urlencode(qp)

    context = {
        "page_title": "Records",
        "donations": donations,
        "dispensed": dispensed,
        "blood_types": BLOOD_TYPES,
        "current_blood_type": blood_type,
        "current_sort": sort_key,
        "qs_no_page": qs_no_page,
        "show_portal_logout": True,
        "urgent_pending_count": _urgent_pending_count(),
        "user_role": _get_role(request),
    }
    return render(request, "blood/records.html", context)


# ------------------------ exports ------------------------
def _export_rows(filename_prefix, headers, rows, fmt):
    fmt = (fmt or "csv").lower()
    if fmt == "xlsx":
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "data"
        ws.append(headers)
        for r in rows:
            ws.append(r)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        resp = HttpResponse(
            buf.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        resp["Content-Disposition"] = f'attachment; filename="{filename_prefix}.xlsx"'
        return resp
    elif fmt == "pdf":
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=landscape(A4), title=filename_prefix)
        elems = []
        styles = getSampleStyleSheet()
        elems.append(Paragraph(filename_prefix.title(), styles["Title"]))
        elems.append(Spacer(1, 12))

        data = [headers] + rows
        table = Table(data, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#c81d25")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ]
            )
        )
        elems.append(table)
        doc.build(elems)
        pdf = buf.getvalue()
        buf.close()
        resp = HttpResponse(pdf, content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="{filename_prefix}.pdf"'
        return resp
    else:
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="{filename_prefix}.csv"'
        writer = csv.writer(resp)
        writer.writerow(headers)
        for r in rows:
            writer.writerow(r)
        return resp


@portal_protected
def donations_export(request):
    blood_type = request.GET.get("blood_type", "").strip()
    sort_key = request.GET.get("sort", "recent").strip()
    fmt = request.GET.get("format", "csv")

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

    headers = ["Donor name", "Blood type", "Donation time"]
    rows = [
        [d.donor.full_name, d.blood_type, d.donation_date.strftime("%Y-%m-%d %H:%M")]
        for d in qs
    ]
    return _export_rows("donations", headers, rows, fmt)


@portal_protected
def dispensed_export(request):
    blood_type = request.GET.get("blood_type", "").strip()
    sort_key = request.GET.get("sort", "recent").strip()
    fmt = request.GET.get("format", "csv")

    qs = DonationUnit.objects.filter(status=DonationUnit.Status.DISPENSED).select_related("donor")
    if blood_type:
        qs = qs.filter(blood_type=blood_type)

    sort_map = {
        "recent": "-dispensed_at",
        "oldest": "dispensed_at",
        "name": "donor__full_name",
        "type": "blood_type",
    }
    order_by = sort_map.get(sort_key, "-dispensed_at")
    qs = qs.order_by(order_by)

    headers = ["Donor name", "Blood type", "Dispensed at"]
    rows = [
        [
            u.donor.full_name,
            u.blood_type,
            (u.dispensed_at or u.donation_date).strftime("%Y-%m-%d %H:%M"),
        ]
        for u in qs
    ]
    return _export_rows("dispensed", headers, rows, fmt)


@portal_protected
def inventory_dashboard(request):
    """
    Inventory + pending requests + audit log.
    Also passes low_stock_threshold for the red line on the chart.
    """
    now = timezone.now()
    near_days = getattr(settings, "NEAR_EXPIRY_DAYS", 7)
    near_cutoff = now + timedelta(days=near_days)
    low_threshold = getattr(settings, "LOW_STOCK_THRESHOLD", 500)

    base_qs = (
        DonationUnit.objects.filter(status=DonationUnit.Status.AVAILABLE)
        .filter(Q(expiry_at__isnull=True) | Q(expiry_at__gt=now))
    )

    # available by type
    available_counts = {bt: 0 for bt, _ in BLOOD_TYPES}
    for row in base_qs.values("blood_type").annotate(cnt=Count("id")):
        available_counts[row["blood_type"]] = row["cnt"]

    # near expiry
    near_counts = {bt: 0 for bt, _ in BLOOD_TYPES}
    for row in (
        base_qs.filter(expiry_at__isnull=False, expiry_at__lte=near_cutoff)
        .values("blood_type")
        .annotate(cnt=Count("id"))
    ):
        near_counts[row["blood_type"]] = row["cnt"]

    # total donated historically
    donated_totals = {bt: 0 for bt, _ in BLOOD_TYPES}
    for row in DonationUnit.objects.values("blood_type").annotate(cnt=Count("id")):
        donated_totals[row["blood_type"]] = row["cnt"]

    labels = [bt for bt, _ in BLOOD_TYPES]
    values = [available_counts[bt] for bt in labels]
    near_values = [near_counts[bt] for bt in labels]
    rows = [
        {"bt": bt, "donated": donated_totals[bt], "available": available_counts[bt], "near": near_counts[bt]}
        for bt in labels
    ]

    # pending requests
    pending = DispenseRequest.objects.filter(status=DispenseRequest.Status.PENDING).order_by(
        "-urgency", "created_at"
    )

    # audit events table
    events_qs = AuditEvent.objects.select_related("user").order_by("-created_at")
    events_pager = Paginator(events_qs, 25)
    epage = request.GET.get("epage")
    events = events_pager.get_page(epage)

    context = {
        "near_days": near_days,
        "labels": labels,
        "values": values,
        "near_values": near_values,
        "rows": rows,
        "show_portal_logout": True,
        "urgent_pending_count": _urgent_pending_count(),
        "pending_requests": pending,
        "events": events,
        "user_role": _get_role(request),
        "low_stock_threshold": low_threshold,
    }
    return render(request, "blood/inventory_dashboard.html", context)


# ------------------------ manager actions ------------------------
def donation_delete(request, pk: int):
    if request.method != "POST":
        return redirect("records")
    pwd = (request.POST.get("portal_password") or "").strip()
    if pwd != (getattr(settings, "PORTAL_PASSWORD", "") or "change-me"):
        messages.error(request, "Incorrect password — donation was NOT deleted.")
        next_url = request.POST.get("next") or reverse("records")
        return redirect(next_url)

    donation = get_object_or_404(DonationUnit, pk=pk)
    bt, dn = donation.blood_type, donation.donor.full_name
    donation.delete()
    log_event(request, "donation_delete", blood_type=bt, donor=dn)
    messages.success(request, "Donation deleted permanently.")
    next_url = request.POST.get("next") or reverse("records")
    return redirect(next_url)


def request_approve(request, pk: int):
    if request.method != "POST":
        return redirect("inventory")

    req = get_object_or_404(DispenseRequest, pk=pk)
    if req.status != DispenseRequest.Status.PENDING:
        messages.info(request, "Request already processed.")
        return redirect("inventory")

    pwd = (request.POST.get("portal_password") or "").strip()
    if pwd != (getattr(settings, "PORTAL_PASSWORD", "") or "change-me"):
        messages.error(request, "Incorrect password — request not approved.")
        return redirect("inventory")

    now = timezone.now()
    counts_qs = (
        DonationUnit.objects.filter(status=DonationUnit.Status.AVAILABLE)
        .filter(Q(expiry_at__isnull=True) | Q(expiry_at__gt=now))
        .values("blood_type")
        .annotate(cnt=Count("id"))
    )
    inventory_counts = {row["blood_type"]: row["cnt"] for row in counts_qs}
    plan, shortfall = plan_dispense(req.requested_type, req.quantity, inventory_counts)

    if shortfall != 0 or not plan:
        messages.error(request, "Not enough compatible inventory to fulfill this request right now.")
        req.plan = plan or {}
        req.shortfall = shortfall or 0
        req.save(update_fields=["plan", "shortfall"])
        return redirect("inventory")

    with transaction.atomic():
        for dtype, take in plan.items():
            units = (
                DonationUnit.objects.select_for_update(skip_locked=True)
                .filter(blood_type=dtype, status=DonationUnit.Status.AVAILABLE)
                .filter(Q(expiry_at__isnull=True) | Q(expiry_at__gt=now))
                .order_by("expiry_at", "donation_date")[:take]
            )
            ids = list(units.values_list("id", flat=True))
            if len(ids) != take:
                messages.error(request, "Inventory changed; try again.")
                return redirect("inventory")
            DonationUnit.objects.filter(id__in=ids).update(
                status=DonationUnit.Status.DISPENSED, dispensed_at=now
            )

        DispenseLog.objects.create(
            requested_type=req.requested_type, quantity=req.quantity, dispensed_map=plan
        )
        log_event(
            request,
            "request_approved",
            req_id=req.id,
            blood_type=req.requested_type,
            qty=req.quantity,
        )
        req.delete()

    messages.success(request, "Request approved and fulfilled.")
    return redirect("inventory")


def request_reject(request, pk: int):
    if request.method != "POST":
        return redirect("inventory")

    req = get_object_or_404(DispenseRequest, pk=pk)
    if req.status != DispenseRequest.Status.PENDING:
        messages.info(request, "Request already processed.")
        return redirect("inventory")

    log_event(
        request,
        "request_rejected",
        req_id=req.id,
        blood_type=req.requested_type,
        qty=req.quantity,
    )
    req.delete()
    messages.success(request, "Request rejected and removed.")
    return redirect("inventory")


# ------------------------ NEW: profile page (fix for missing view) ------------------------
@login_required(login_url="login")
def profile(request):
    """
    עמוד פרופיל:
    - מציג פרטי Profile (כולל ת"ז, סוג דם ותאריך לידה)
    - מאפשר עדכון פרטים + העלאת תמונת פרופיל
    - שינוי סיסמה בלחיצה (טופס מוסתר/גלוי ב־template)
    - מציג תרומות של התורם (אם role=DONOR ויש ת"ז)
    """
    if not hasattr(request.user, "profile"):
        messages.error(request, "Profile is not available.")
        return redirect("home")

    prof = request.user.profile

    donor = None
    donations = DonationUnit.objects.none()
    if prof.role == Profile.Role.DONOR and prof.national_id:
        donor = Donor.objects.filter(national_id=prof.national_id).first()
        if donor:
            donations = DonationUnit.objects.filter(donor=donor).order_by("-donation_date")

    if request.method == "POST":
        if "save_profile" in request.POST:
            pform = ProfileUpdateForm(request.POST, request.FILES, instance=prof)
            pwform = PasswordChangeForm(user=request.user)  # להשאיר ריק בסשן הזה
            if pform.is_valid():
                pform.save()
                messages.success(request, "Profile updated.")
                return redirect("profile")
        elif "change_password" in request.POST:
            pform = ProfileUpdateForm(instance=prof)  # שלא נאבד את הטופס בצד
            pwform = PasswordChangeForm(user=request.user, data=request.POST)
            if pwform.is_valid():
                user = pwform.save()
                update_session_auth_hash(request, user)  # שלא יתנתק
                messages.success(request, "Password changed successfully.")
                return redirect("profile")
    else:
        pform = ProfileUpdateForm(instance=prof)
        pwform = PasswordChangeForm(user=request.user)

    return render(request, "blood/profile.html", {
        "profile": prof, "pform": pform, "pwform": pwform,
        "donations": donations, "donor": donor,
        "user_role": prof.role,
    })

from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_POST
import csv
import json
import os

from .catalog import DEFAULT_TEMPLATES
from .analytics import dashboard_payload, send_quota
from .forms import (
    CampaignForm,
    ContactForm,
    ContactImportForm,
    LeadForm,
    LeadImportForm,
    NoteForm,
    RecipientUploadForm,
    SettingsForm,
    TemplateForm,
    TestEmailForm,
)
from .importers import add_contacts_to_campaign, import_contacts, import_leads, parse_contact_rows
from .mailer import (
    _RUNNING,
    prepare_campaign_for_send,
    preview_sample_html,
    run_campaign,
    send_test,
    smtp_kwargs,
    start_campaign_async,
)
from .models import Activity, AppSettings, Campaign, Contact, EmailTemplate, Lead, Recipient, Unsubscribe
from .utils import ensure_templates
from .auth_views import CrmLoginView, CrmLogoutView

login_view = CrmLoginView.as_view()
logout_view = CrmLogoutView.as_view()


def dashboard(request):
    ensure_templates()
    payload = dashboard_payload()
    return render(request, "campaigns/dashboard.html", payload)


def template_gallery(request):
    ensure_templates()
    templates = list(EmailTemplate.objects.filter(is_active=True))
    app = AppSettings.load()
    for template in templates:
        template.preview_html = preview_sample_html(template, app)
        template.preview_sid = f"tpl-html-{template.pk}"
        template.preview_fid = f"tpl-frame-{template.pk}"
    return render(request, "campaigns/templates.html", {"templates": templates})


def campaign_create(request):
    ensure_templates()
    initial = {}
    template_id = request.GET.get("template")
    if template_id:
        initial["template"] = template_id
    form = CampaignForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        campaign = form.save()
        messages.success(request, "Campaign saved. Add recipients next.")
        return redirect("campaigns:recipients", pk=campaign.pk)
    return render(
        request,
        "campaigns/campaign_form.html",
        {"form": form, "templates": EmailTemplate.objects.filter(is_active=True), "title": "New campaign"},
    )


def campaign_list(request):
    campaigns = Campaign.objects.select_related("template")
    return render(request, "campaigns/campaign_list.html", {"campaigns": campaigns})


def campaign_edit(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    if campaign.editor_mode != Campaign.EditorMode.TEMPLATE:
        return redirect("campaigns:editor_open", pk=pk)
    if campaign.status == Campaign.Status.SENDING:
        messages.warning(request, "Pause the campaign before editing.")
        return redirect("campaigns:detail", pk=pk)
    form = CampaignForm(request.POST or None, instance=campaign)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Campaign updated.")
        return redirect("campaigns:detail", pk=pk)
    return render(
        request,
        "campaigns/campaign_form.html",
        {
            "form": form,
            "campaign": campaign,
            "templates": EmailTemplate.objects.filter(is_active=True),
            "title": "Edit campaign",
        },
    )


SEND_BATCH_SIZES = (20, 100, 500)


def _parse_send_batch(request, default=20) -> int:
    raw = (request.POST.get("batch") or request.GET.get("batch") or str(default)).strip()
    try:
        size = int(raw)
    except (TypeError, ValueError):
        size = default
    if size in SEND_BATCH_SIZES:
        return size
    if size < 20:
        return 20
    if size > 500:
        return 500
    return min(SEND_BATCH_SIZES, key=lambda n: abs(n - size))


def _wants_json(request) -> bool:
    requested = (request.headers.get("X-Requested-With") or "").lower()
    accept = (request.headers.get("Accept") or "").lower()
    return requested in {"fetch", "xmlhttprequest"} or "application/json" in accept


def _complete_idle_campaign(campaign: Campaign) -> Campaign:
    if (
        campaign.status == Campaign.Status.SENDING
        and campaign.pending_count == 0
        and campaign.pk not in _RUNNING
    ):
        campaign.status = Campaign.Status.COMPLETED
        campaign.finished_at = campaign.finished_at or timezone.now()
        campaign.save(update_fields=["status", "finished_at", "updated_at"])
    return campaign


def campaign_detail(request, pk):
    campaign = get_object_or_404(Campaign.objects.select_related("template"), pk=pk)
    campaign = _complete_idle_campaign(campaign)
    status = (request.GET.get("rstatus") or "").strip()
    q = (request.GET.get("rq") or "").strip()
    recipients_qs = campaign.recipients.all()
    if status in {choice[0] for choice in Recipient.Status.choices}:
        recipients_qs = recipients_qs.filter(status=status)
    if q:
        recipients_qs = recipients_qs.filter(Q(email__icontains=q) | Q(name__icontains=q) | Q(error_message__icontains=q))
    recipients = Paginator(recipients_qs, 100).get_page(request.GET.get("page") or 1)
    status_counts = {
        row["status"]: row["n"]
        for row in campaign.recipients.values("status").annotate(n=Count("id"))
    }
    test_form = TestEmailForm()
    preview_html = preview_sample_html(campaign.template, campaign=campaign)
    return render(
        request,
        "campaigns/campaign_detail.html",
        {
            "campaign": campaign,
            "recipients": recipients,
            "recipient_status": status,
            "recipient_q": q,
            "recipient_total": recipients_qs.count(),
            "status_counts": status_counts,
            "test_form": test_form,
            "preview_html": preview_html,
            "send_batch_sizes": SEND_BATCH_SIZES,
        },
    )


def delivery_report(request):
    status = (request.GET.get("status") or "").strip()
    q = (request.GET.get("q") or "").strip()
    campaign_id = (request.GET.get("campaign") or "").strip()
    rows = Recipient.objects.select_related("campaign").order_by("-id")
    if status:
        rows = rows.filter(status=status)
    if campaign_id.isdigit():
        rows = rows.filter(campaign_id=int(campaign_id))
    if q:
        rows = rows.filter(Q(email__icontains=q) | Q(name__icontains=q))
    summary = {
        key: Recipient.objects.filter(status=key).count() for key, _ in Recipient.Status.choices
    }
    return render(
        request,
        "campaigns/delivery_report.html",
        {
            "rows": rows[:500],
            "summary": summary,
            "status": status,
            "q": q,
            "campaign_id": campaign_id,
            "campaigns": Campaign.objects.all()[:50],
        },
    )


def campaign_recipients(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    form = RecipientUploadForm(request.POST or None, request.FILES or None)
    contacts = Contact.objects.all()
    leads = Lead.objects.exclude(status=Lead.Status.LOST)
    if request.method == "POST":
        if request.POST.get("action") == "from_contacts":
            queryset, mode = _contacts_from_post(request)
            if mode == "selected" and not request.POST.getlist("contact_ids"):
                messages.error(request, "Tick contacts or tap 20 / 50 / 100 / 500 first.")
                return redirect("campaigns:recipients", pk=pk)
            added, skipped = add_contacts_to_campaign(campaign, queryset)
            messages.success(request, f"Added {added} from contacts. Skipped {skipped}.")
            return redirect("campaigns:detail", pk=campaign.pk)
        if request.POST.get("action") == "from_leads":
            selected_ids = request.POST.getlist("lead_ids")
            queryset = leads.filter(pk__in=selected_ids) if selected_ids else leads
            added, skipped = add_contacts_to_campaign(campaign, queryset)
            messages.success(request, f"Added {added} from leads. Skipped {skipped}.")
            return redirect("campaigns:detail", pk=campaign.pk)
        if form.is_valid():
            chunks = []
            upload = form.cleaned_data.get("csv_file")
            paste = form.cleaned_data.get("paste_list") or ""
            if upload:
                chunks.append(upload.read().decode("utf-8-sig", errors="replace"))
            if paste.strip():
                chunks.append(paste)
            if not chunks:
                messages.error(request, "Upload a CSV, paste a list, or import from Contacts.")
            else:
                added, skipped = 0, 0
                from .models import Recipient as RecipientModel

                unsub_emails = set(Unsubscribe.objects.values_list("email", flat=True))
                existing = set(campaign.recipients.values_list("email", flat=True))
                for chunk in chunks:
                    try:
                        rows = parse_contact_rows(chunk)
                    except Exception:
                        rows = [
                            {"email": line.strip(), "name": "", "company": ""}
                            for line in chunk.splitlines()
                            if line.strip()
                        ]
                    for row in rows:
                        email = (row.get("email") or "").strip().lower()
                        if not email or email in {"email", "e-mail"}:
                            continue
                        from django.core.exceptions import ValidationError
                        from django.core.validators import validate_email

                        try:
                            validate_email(email)
                        except ValidationError:
                            skipped += 1
                            continue
                        if email in existing or email in unsub_emails:
                            skipped += 1
                            continue
                        RecipientModel.objects.create(
                            campaign=campaign,
                            email=email,
                            name=row.get("name") or "",
                            company=row.get("company") or "",
                        )
                        Contact.objects.get_or_create(
                            email=email,
                            defaults={"name": row.get("name") or "", "company": row.get("company") or ""},
                        )
                        existing.add(email)
                        added += 1
                messages.success(request, f"Added {added} recipients. Skipped {skipped}.")
                return redirect("campaigns:detail", pk=campaign.pk)
    return render(
        request,
        "campaigns/recipients.html",
        {
            "campaign": campaign,
            "form": form,
            "contacts": contacts[:1500],
            "contact_count": contacts.count(),
            "leads": leads,
        },
    )


def _contacts_from_post(request):
    qs = Contact.objects.all()
    q = (request.POST.get("q") or "").strip()
    if q:
        qs = qs.filter(
            Q(email__icontains=q) | Q(name__icontains=q) | Q(company__icontains=q) | Q(phone__icontains=q)
        )
    mode = (request.POST.get("mode") or "selected").strip()
    if mode == "selected":
        return qs.filter(pk__in=request.POST.getlist("contact_ids")), mode
    if mode != "all":
        try:
            limit = int(mode)
        except ValueError:
            limit = 50
        qs = qs[: max(1, min(limit, 5000))]
    return qs, mode


def contacts_list(request):
    form = ContactForm(request.POST or None) if request.POST.get("action") == "add" else ContactForm()
    import_form = ContactImportForm()
    if request.method == "POST" and request.POST.get("action") == "add":
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Contact saved.")
            return redirect("campaigns:contacts")
    contacts = Contact.objects.all()
    q = (request.GET.get("q") or "").strip()
    if q:
        contacts = contacts.filter(
            Q(email__icontains=q) | Q(name__icontains=q) | Q(company__icontains=q) | Q(phone__icontains=q)
        )
    contact_count = contacts.count()
    return render(
        request,
        "campaigns/contacts.html",
        {
            "contacts": contacts[:1500],
            "contact_count": contact_count,
            "form": form,
            "import_form": import_form,
            "q": q,
            "campaigns": Campaign.objects.exclude(status=Campaign.Status.SENDING),
        },
    )


@require_POST
def contacts_bulk_send(request):
    campaign_id = (request.POST.get("campaign_id") or "").strip()
    if not campaign_id:
        messages.error(request, "Pick a campaign first, then choose 20 / 50 / 100 / 500.")
        return redirect("campaigns:contacts")
    campaign = get_object_or_404(Campaign, pk=campaign_id)
    qs, mode = _contacts_from_post(request)
    if mode == "selected" and not request.POST.getlist("contact_ids"):
        messages.error(request, "Tick contacts or tap 20 / 50 / 100 / 500 first.")
        return redirect("campaigns:contacts")
    added, skipped = add_contacts_to_campaign(campaign, qs)
    messages.success(request, f"Added {added} contacts to “{campaign.name}”. Skipped {skipped}.")
    if request.POST.get("send_now") == "1" and added:
        return campaign_send(request, campaign.pk)
    return redirect("campaigns:detail", pk=campaign.pk)


@require_POST
def contacts_import(request):
    form = ContactImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        chunks = []
        upload = form.cleaned_data.get("csv_file")
        paste = form.cleaned_data.get("paste_list") or ""
        if upload:
            chunks.append(upload.read().decode("utf-8-sig", errors="replace"))
        if paste.strip():
            chunks.append(paste)
        if not chunks:
            messages.error(request, "Upload a CSV or paste emails.")
            return redirect("campaigns:contacts")
        added, skipped = import_contacts(chunks)
        messages.success(request, f"Imported {added} contacts. Skipped {skipped} duplicates/invalid.")
    return redirect("campaigns:contacts")


@require_POST
def contact_delete(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    contact.delete()
    messages.success(request, "Contact removed.")
    return redirect("campaigns:contacts")


@xframe_options_exempt
def campaign_preview(request, pk):
    campaign = get_object_or_404(Campaign.objects.select_related("template"), pk=pk)
    return HttpResponse(preview_sample_html(campaign.template, campaign=campaign))


@xframe_options_exempt
def template_preview(request, pk):
    template = get_object_or_404(EmailTemplate, pk=pk)
    return HttpResponse(preview_sample_html(template))


@require_POST
def campaign_send(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    batch = _parse_send_batch(request)

    def reply(ok, message, *, level="success"):
        campaign.refresh_from_db()
        payload = {
            "ok": ok,
            "message": message,
            "status": campaign.status,
            "sent": campaign.sent_count,
            "failed": campaign.failed_count,
            "skipped": campaign.skipped_count,
            "pending": campaign.pending_count,
            "percent": campaign.progress_percent,
            "delivery_rate": campaign.delivery_rate,
            "last_error": campaign.last_error,
            "batch": batch,
        }
        if _wants_json(request):
            return JsonResponse(payload, status=200 if ok else 400)
        if ok:
            messages.success(request, message)
        else:
            messages.error(request, message)
        if not ok and "SMTP" in message:
            return redirect("campaigns:settings")
        if not ok and campaign.total_recipients == 0:
            return redirect("campaigns:recipients", pk=pk)
        return redirect("campaigns:detail", pk=pk)

    if campaign.total_recipients == 0:
        return reply(False, "Add recipients before sending.")
    app = AppSettings.load()
    mail = smtp_kwargs(app)
    if not (mail.get("host") and mail.get("username") and mail.get("password")):
        return reply(False, "Configure SMTP in Settings first, or set EMAIL_HOST_PASSWORD on Vercel.")
    if campaign.status == Campaign.Status.SENDING and campaign.pk in _RUNNING:
        return reply(True, "Already sending.")
    pending_now = campaign.recipients.filter(status=Recipient.Status.PENDING).count()
    this_batch = min(batch, pending_now) if pending_now else batch
    quota = send_quota(app)
    if quota["exhausted"]:
        return reply(
            False,
            f"Daily send limit reached ({quota['limit']}/day). Wait until tomorrow or raise the limit in Brand & SMTP.",
        )
    if this_batch > quota["remaining"]:
        return reply(
            False,
            f"Only {quota['remaining']} emails left today (limit {quota['limit']}). Send a smaller batch.",
        )
    pending = prepare_campaign_for_send(campaign)
    if pending == 0:
        return reply(False, "No recipients left to send (unsubscribed).")
    limit = min(batch, pending)
    campaign.status = Campaign.Status.QUEUED
    campaign.save(update_fields=["status", "updated_at"])
    run_campaign(campaign.pk, limit=limit)
    campaign.refresh_from_db()
    left = campaign.pending_count
    if left:
        message = (
            f"Batch of {limit} done. Sent {campaign.sent_count}, failed {campaign.failed_count}. "
            f"{left} still waiting — send 20 / 100 / 500 again."
        )
    else:
        message = f"Done. Sent {campaign.sent_count}, failed {campaign.failed_count}."
    return reply(True, message)


@require_POST
def campaign_pause(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    campaign.status = Campaign.Status.PAUSED
    campaign.save(update_fields=["status", "updated_at"])
    messages.success(request, "Campaign paused. You can resume later.")
    return redirect("campaigns:detail", pk=pk)


@require_POST
def campaign_test(request, pk):
    campaign = get_object_or_404(Campaign.objects.select_related("template"), pk=pk)
    form = TestEmailForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter a valid test email address.")
        return redirect("campaigns:detail", pk=pk)
    try:
        send_test(campaign, form.cleaned_data["to_email"])
        messages.success(request, f"Test email sent to {form.cleaned_data['to_email']}. Check inbox and spam.")
    except Exception as exc:
        messages.error(request, f"Test send failed: {exc}")
    return redirect("campaigns:detail", pk=pk)


def campaign_progress(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    campaign = _complete_idle_campaign(campaign)
    return JsonResponse(
        {
            "status": campaign.status,
            "sent": campaign.sent_count,
            "failed": campaign.failed_count,
            "skipped": campaign.skipped_count,
            "pending": campaign.pending_count,
            "total": campaign.total_recipients,
            "percent": campaign.progress_percent,
            "last_error": campaign.last_error,
            "delivery_rate": campaign.delivery_rate,
        }
    )


def settings_view(request):
    app = AppSettings.load()
    form = SettingsForm(request.POST or None, request.FILES or None, instance=app)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Settings saved.")
        return redirect("campaigns:settings")
    return render(request, "campaigns/settings.html", {"form": form, "test_form": TestEmailForm(), "app": app})


def leads_list(request):
    form = LeadForm(request.POST or None) if request.POST.get("action") == "add" else LeadForm()
    import_form = LeadImportForm()
    if request.method == "POST" and request.POST.get("action") == "add":
        form = LeadForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Lead saved.")
            return redirect("campaigns:leads")
    leads = Lead.objects.all()
    status = (request.GET.get("status") or "").strip()
    q = (request.GET.get("q") or "").strip()
    view = (request.GET.get("view") or "board").strip()
    if view not in {"board", "table"}:
        view = "board"
    filtered = leads
    if q:
        filtered = filtered.filter(Q(email__icontains=q) | Q(name__icontains=q) | Q(company__icontains=q))
    table_leads = filtered.filter(status=status) if status else filtered
    columns = []
    status_cards = []
    for key, label in Lead.Status.choices:
        col_qs = filtered.filter(status=key)
        cards = list(col_qs[:80])
        count = col_qs.count()
        value = sum((lead.value or 0) for lead in cards)
        columns.append({"key": key, "label": label, "leads": cards, "count": count, "value": value})
        status_cards.append((key, label, count, value))
    return render(
        request,
        "campaigns/leads.html",
        {
            "leads": table_leads,
            "form": form,
            "import_form": import_form,
            "q": q,
            "status": status,
            "view": view,
            "columns": columns,
            "status_cards": status_cards,
            "statuses": Lead.Status.choices,
            "total_leads": filtered.count(),
        },
    )


def pipeline(request):
    return redirect("campaigns:leads")


def lead_detail(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    form = LeadForm(request.POST or None, instance=lead) if request.POST.get("action") == "edit" else LeadForm(instance=lead)
    note_form = NoteForm()
    if request.method == "POST" and request.POST.get("action") == "edit":
        form = LeadForm(request.POST, instance=lead)
        if form.is_valid():
            old_status = lead.status
            saved = form.save()
            if saved.status != old_status:
                Activity.objects.create(
                    lead=saved,
                    kind=Activity.Kind.STATUS,
                    message=f"Moved from {old_status} to {saved.status}",
                )
                if saved.status == Lead.Status.WON:
                    saved.to_contact()
                    Activity.objects.create(
                        lead=saved, kind=Activity.Kind.CONVERT, message="Won — saved as a contact"
                    )
            messages.success(request, "Lead updated.")
            return redirect("campaigns:lead_detail", pk=pk)
    activities = lead.activities.all()[:50]
    return render(
        request,
        "campaigns/lead_detail.html",
        {
            "lead": lead,
            "form": form,
            "note_form": note_form,
            "activities": activities,
            "statuses": Lead.Status.choices,
        },
    )


@require_POST
def lead_move(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    is_json = "application/json" in (request.content_type or "")
    if is_json:
        try:
            payload = json.loads(request.body.decode() or "{}")
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = request.POST
    status = (payload.get("status") or "").strip()
    valid = {choice[0] for choice in Lead.Status.choices}
    if status not in valid:
        if is_json:
            return JsonResponse({"ok": False, "error": "Invalid stage"}, status=400)
        messages.error(request, "Invalid stage.")
        return redirect("campaigns:lead_detail", pk=pk)
    old = lead.status
    if old != status:
        lead.status = status
        lead.save(update_fields=["status", "updated_at"])
        Activity.objects.create(
            lead=lead,
            kind=Activity.Kind.STATUS,
            message=f"Moved from {old} to {status}",
        )
        if status == Lead.Status.WON:
            lead.to_contact()
            Activity.objects.create(lead=lead, kind=Activity.Kind.CONVERT, message="Won — saved as a contact")
    if is_json:
        return JsonResponse({"ok": True, "status": lead.status})
    messages.success(request, f"Status set to {lead.get_status_display()}.")
    return redirect("campaigns:lead_detail", pk=pk)


@require_POST
def lead_note(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    form = NoteForm(request.POST)
    if form.is_valid():
        Activity.objects.create(lead=lead, kind=Activity.Kind.NOTE, message=form.cleaned_data["message"])
        messages.success(request, "Note added.")
    else:
        messages.error(request, "Write a note first.")
    return redirect("campaigns:lead_detail", pk=pk)


@require_POST
def leads_import(request):
    form = LeadImportForm(request.POST, request.FILES)
    if form.is_valid():
        chunks = []
        upload = form.cleaned_data.get("csv_file")
        paste = form.cleaned_data.get("paste_list") or ""
        if upload:
            chunks.append(upload.read().decode("utf-8-sig", errors="replace"))
        if paste.strip():
            chunks.append(paste)
        if not chunks:
            messages.error(request, "Upload a CSV or paste leads.")
            return redirect("campaigns:leads")
        added, skipped = import_leads(chunks)
        messages.success(request, f"Imported {added} leads. Skipped {skipped} duplicates/invalid.")
    return redirect("campaigns:leads")


@require_POST
def lead_delete(request, pk):
    get_object_or_404(Lead, pk=pk).delete()
    messages.success(request, "Lead removed.")
    return redirect("campaigns:leads")


@require_POST
def lead_convert(request, pk):
    lead = get_object_or_404(Lead, pk=pk)
    lead.to_contact()
    Activity.objects.create(lead=lead, kind=Activity.Kind.CONVERT, message="Converted to a contact")
    messages.success(request, f"{lead.email} moved to Contacts.")
    next_url = request.POST.get("next") or reverse("campaigns:leads")
    if not str(next_url).startswith("/"):
        next_url = reverse("campaigns:leads")
    return redirect(next_url)


def template_create(request):
    ensure_templates()
    form = TemplateForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Template saved. You can now use it in a campaign.")
        return redirect("campaigns:templates")
    if request.method == "POST":
        messages.error(request, "Please fix the highlighted fields and try again.")
    return render(
        request,
        "campaigns/template_form.html",
        {"form": form, "title": "New email template", "layouts": DEFAULT_TEMPLATES, "is_create": True},
    )


def template_edit(request, pk):
    template = get_object_or_404(EmailTemplate, pk=pk)
    form = TemplateForm(request.POST or None, request.FILES or None, instance=template)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Template updated.")
        return redirect("campaigns:templates")
    if request.method == "POST":
        messages.error(request, "Please fix the highlighted fields and try again.")
    preview_html = preview_sample_html(template)
    return render(
        request,
        "campaigns/template_form.html",
        {
            "form": form,
            "title": "Edit template",
            "template": template,
            "layouts": DEFAULT_TEMPLATES,
            "is_create": False,
            "preview_html": preview_html,
        },
    )


@login_not_required
def unsubscribe(request, token):
    recipient = get_object_or_404(Recipient, unsubscribe_token=token)
    Unsubscribe.objects.get_or_create(email=recipient.email.lower())
    Recipient.objects.filter(email__iexact=recipient.email, status=Recipient.Status.PENDING).update(
        status=Recipient.Status.SKIPPED, error_message="Unsubscribed"
    )
    return render(request, "campaigns/unsubscribe.html", {"email": recipient.email})


@require_POST
def campaign_retry_failed(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    if campaign.status == Campaign.Status.SENDING:
        messages.info(request, "Already sending.")
        return redirect("campaigns:detail", pk=pk)
    failed = campaign.recipients.filter(status=Recipient.Status.FAILED)
    count = failed.count()
    if not count:
        messages.info(request, "No failed emails to retry.")
        return redirect("campaigns:detail", pk=pk)
    failed.update(status=Recipient.Status.PENDING, error_message="")
    campaign.failed_count = 0
    campaign.last_error = ""
    campaign.status = Campaign.Status.QUEUED
    campaign.save(update_fields=["failed_count", "last_error", "status", "updated_at"])
    batch = _parse_send_batch(request)
    limit = min(batch, count)
    run_campaign(campaign.pk, limit=limit)
    campaign.refresh_from_db()
    left = campaign.pending_count
    if left:
        messages.success(
            request,
            f"Retried a batch of {limit}. Sent {campaign.sent_count}, failed {campaign.failed_count}. {left} still waiting.",
        )
    else:
        messages.success(request, f"Retried {count}. Sent {campaign.sent_count}, failed {campaign.failed_count}.")
    return redirect("campaigns:detail", pk=pk)


def campaign_export(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    status = (request.GET.get("status") or "").strip()
    qs = campaign.recipients.all()
    if status in {choice[0] for choice in Recipient.Status.choices}:
        qs = qs.filter(status=status)
    response = HttpResponse(content_type="text/csv")
    suffix = status or "all"
    response["Content-Disposition"] = f'attachment; filename="campaign-{campaign.pk}-{suffix}.csv"'
    writer = csv.writer(response)
    writer.writerow(["email", "name", "company", "status", "error", "sent_at"])
    for row in qs.iterator():
        writer.writerow([row.email, row.name, row.company, row.status, row.error_message, row.sent_at or ""])
    return response


def statistics(request):
    ensure_templates()
    sent = Recipient.objects.filter(status=Recipient.Status.SENT).count()
    failed = Recipient.objects.filter(status=Recipient.Status.FAILED).count()
    pending = Recipient.objects.filter(status=Recipient.Status.PENDING).count()
    skipped = Recipient.objects.filter(status=Recipient.Status.SKIPPED).count()
    total = Recipient.objects.count()
    attempted = sent + failed
    campaigns = list(Campaign.objects.select_related("template")[:50])
    recent_failed = list(
        Recipient.objects.filter(status=Recipient.Status.FAILED)
        .select_related("campaign")
        .order_by("-id")[:25]
    )
    return render(
        request,
        "campaigns/statistics.html",
        {
            "sent": sent,
            "failed": failed,
            "pending": pending,
            "skipped": skipped,
            "total": total,
            "attempted": attempted,
            "delivery_rate": int((sent / attempted) * 100) if attempted else 0,
            "campaigns": campaigns,
            "recent_failed": recent_failed,
        },
    )

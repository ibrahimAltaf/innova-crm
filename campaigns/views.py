from django.core.paginator import Paginator
from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_POST
import csv
import json

from .catalog import DEFAULT_TEMPLATES
from .analytics import dashboard_payload
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
    start_campaign_async,
)
from .models import Activity, AppSettings, Campaign, Contact, EmailTemplate, Lead, Recipient, Unsubscribe
from .utils import ensure_templates


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
        },
    )


def campaign_recipients(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    form = RecipientUploadForm(request.POST or None, request.FILES or None)
    contacts = Contact.objects.all()
    leads = Lead.objects.exclude(status=Lead.Status.LOST)
    if request.method == "POST":
        if request.POST.get("action") == "from_contacts":
            selected_ids = request.POST.getlist("contact_ids")
            queryset = contacts.filter(pk__in=selected_ids) if selected_ids else contacts
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
        {"campaign": campaign, "form": form, "contacts": contacts, "leads": leads},
    )


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
        contacts = contacts.filter(Q(email__icontains=q) | Q(name__icontains=q) | Q(company__icontains=q))
    return render(
        request,
        "campaigns/contacts.html",
        {"contacts": contacts, "form": form, "import_form": import_form, "q": q},
    )


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
    if campaign.total_recipients == 0:
        messages.error(request, "Add recipients before sending.")
        return redirect("campaigns:recipients", pk=pk)
    app = AppSettings.load()
    if not (app.smtp_host or app.from_email):
        messages.error(request, "Configure SMTP in Settings first.")
        return redirect("campaigns:settings")
    if campaign.status == Campaign.Status.SENDING:
        messages.info(request, "Already sending.")
        return redirect("campaigns:detail", pk=pk)
    pending = prepare_campaign_for_send(campaign)
    if pending == 0:
        messages.error(request, "No recipients left to send (unsubscribed).")
        return redirect("campaigns:detail", pk=pk)
    campaign.status = Campaign.Status.QUEUED
    campaign.save(update_fields=["status", "updated_at"])
    if pending <= 25:
        run_campaign(campaign.pk)
        campaign.refresh_from_db()
        messages.success(
            request,
            f"Done. Sent {campaign.sent_count}, failed {campaign.failed_count}. Check inbox and Hostinger Sent.",
        )
    else:
        start_campaign_async(campaign.pk)
        messages.success(request, "Sending started in the background. Keep this app running until it finishes.")
    return redirect("campaigns:detail", pk=pk)


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
    if count <= 25:
        run_campaign(campaign.pk)
        campaign.refresh_from_db()
        messages.success(request, f"Retried {count}. Sent {campaign.sent_count}, failed {campaign.failed_count}.")
    else:
        start_campaign_async(campaign.pk)
        messages.success(request, f"Retrying {count} failed emails in the background.")
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

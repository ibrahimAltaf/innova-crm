import json

from django.contrib import messages
from django.core.mail import EmailMultiAlternatives, get_connection
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import TestEmailForm
from .mailer import preview_sample_html, send_test, smtp_kwargs
from .models import AppSettings, Campaign
from .utils import ensure_custom_template


def _editor_campaign(pk):
    if not pk:
        return None
    return get_object_or_404(Campaign.objects.select_related("template"), pk=pk)


def _save_custom_campaign(request, *, mode, pk=None):
    campaign = _editor_campaign(pk)
    name = (request.POST.get("name") or "").strip() or "Untitled campaign"
    subject = (request.POST.get("subject") or "").strip() or name
    preheader = (request.POST.get("preheader") or "").strip()
    html_content = request.POST.get("html_content") or ""
    blocks_raw = request.POST.get("blocks_json") or "[]"
    try:
        blocks = json.loads(blocks_raw)
        if not isinstance(blocks, list):
            blocks = []
    except json.JSONDecodeError:
        blocks = []
    template = ensure_custom_template()
    fields = {
        "name": name[:160],
        "subject": subject[:200],
        "preheader": preheader[:140],
        "heading": subject[:200],
        "body": "",
        "html_content": html_content,
        "blocks_json": blocks,
        "editor_mode": mode,
        "template": template,
    }
    if campaign:
        if campaign.status == Campaign.Status.SENDING:
            messages.warning(request, "Pause the campaign before editing.")
            return campaign, False
        for key, value in fields.items():
            setattr(campaign, key, value)
        campaign.save()
    else:
        campaign = Campaign.objects.create(**fields)
    return campaign, True


def campaign_picker(request):
    return render(request, "campaigns/campaign_picker.html")


def editor_simple(request, pk=None):
    return _editor_page(request, mode=Campaign.EditorMode.SIMPLE, pk=pk, template_name="campaigns/simple_editor.html")


def editor_html(request, pk=None):
    return _editor_page(request, mode=Campaign.EditorMode.HTML, pk=pk, template_name="campaigns/html_editor.html")


def editor_dragdrop(request, pk=None):
    return _editor_page(
        request, mode=Campaign.EditorMode.DRAGDROP, pk=pk, template_name="campaigns/dragdrop_editor.html"
    )


def editor_open(request, pk):
    campaign = get_object_or_404(Campaign, pk=pk)
    if campaign.editor_mode == Campaign.EditorMode.SIMPLE:
        return redirect("campaigns:editor_simple", pk=pk)
    if campaign.editor_mode == Campaign.EditorMode.HTML:
        return redirect("campaigns:editor_html", pk=pk)
    if campaign.editor_mode == Campaign.EditorMode.DRAGDROP:
        return redirect("campaigns:editor_dragdrop", pk=pk)
    return redirect("campaigns:edit", pk=pk)


def _editor_page(request, *, mode, pk, template_name):
    campaign = _editor_campaign(pk)
    if request.method == "POST":
        campaign, ok = _save_custom_campaign(request, mode=mode, pk=pk)
        if not ok:
            return redirect("campaigns:detail", pk=campaign.pk)
        action = request.POST.get("action") or "save"
        if action == "test":
            form = TestEmailForm(request.POST)
            if not form.is_valid():
                messages.error(request, "Enter a valid test email address.")
                return redirect(_editor_url(mode, campaign.pk))
            try:
                send_test(campaign, form.cleaned_data["to_email"])
                messages.success(request, f"Test email sent to {form.cleaned_data['to_email']}. Check inbox and spam.")
            except Exception as exc:
                messages.error(request, f"Test send failed: {exc}")
            return redirect(_editor_url(mode, campaign.pk))
        if action == "quit":
            messages.success(request, "Campaign saved. Add people, then send.")
            return redirect("campaigns:detail", pk=campaign.pk)
        messages.success(request, "Draft saved.")
        return redirect(_editor_url(mode, campaign.pk))

    preview_html = ""
    if campaign:
        preview_html = preview_sample_html(campaign.template, campaign=campaign)
    return render(
        request,
        template_name,
        {
            "campaign": campaign,
            "mode": mode,
            "preview_html": preview_html,
            "test_form": TestEmailForm(),
            "blocks_seed": [],
        },
    )


def _editor_url(mode, pk):
    if mode == Campaign.EditorMode.HTML:
        return reverse("campaigns:editor_html", args=[pk])
    if mode == Campaign.EditorMode.DRAGDROP:
        return reverse("campaigns:editor_dragdrop", args=[pk])
    return reverse("campaigns:editor_simple", args=[pk])


@require_POST
def settings_test(request):
    app = AppSettings.load()
    form = TestEmailForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter a valid email to test SMTP.")
        return redirect("campaigns:settings")
    to_email = form.cleaned_data["to_email"]
    try:
        with get_connection(**smtp_kwargs(app)) as connection:
            msg = EmailMultiAlternatives(
                subject="Innova CRM SMTP test",
                body="SMTP is working. You can send campaigns from this mailbox.",
                from_email=app.from_email or app.smtp_user,
                to=[to_email],
                connection=connection,
            )
            msg.send()
        messages.success(request, f"SMTP test sent to {to_email}.")
    except Exception as exc:
        messages.error(request, f"SMTP test failed: {exc}")
    return redirect("campaigns:settings")

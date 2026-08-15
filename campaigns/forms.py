from django import forms
from django.utils.text import slugify

from .catalog import DEFAULT_TEMPLATES
from .models import AppSettings, Campaign, Contact, EmailTemplate, Lead


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = [
            "name",
            "template",
            "subject",
            "preheader",
            "heading",
            "body",
            "cta_text",
            "cta_url",
            "image_url",
            "extra_note",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "August client update"}),
            "template": forms.Select(attrs={"class": "form-select"}),
            "subject": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Keep under 50 characters when possible"}
            ),
            "preheader": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Inbox preview text (not the subject)"}
            ),
            "heading": forms.TextInput(attrs={"class": "form-control"}),
            "body": forms.Textarea(attrs={"class": "form-control", "rows": 8}),
            "cta_text": forms.TextInput(attrs={"class": "form-control", "placeholder": "View details"}),
            "cta_url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://yourdomain.com"}),
            "image_url": forms.URLInput(
                attrs={"class": "form-control", "placeholder": "https://yourdomain.com/banner.jpg"}
            ),
            "extra_note": forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional subtitle or date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["template"].queryset = EmailTemplate.objects.filter(is_active=True)


class RecipientUploadForm(forms.Form):
    csv_file = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".csv,text/csv"}),
    )
    paste_list = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 8,
                "placeholder": "email,name,company\nana@client.com,Ana Khan,Acme\nbilal@client.com,Bilal,Acme",
            }
        ),
    )


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ["email", "name", "phone", "company", "job_title", "notes", "source"]
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "name@client.com"}),
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Full name"}),
            "company": forms.TextInput(attrs={"class": "form-control", "placeholder": "Company"}),
            "phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "0300 0000000"}),
            "job_title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Owner / Manager"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Optional note"}),
            "source": forms.TextInput(attrs={"class": "form-control", "placeholder": "manual / csv / website"}),
        }


class ContactImportForm(forms.Form):
    csv_file = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".csv,text/csv"}),
    )
    paste_list = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 8,
                "placeholder": "email,name,company\nana@client.com,Ana Khan,Acme",
            }
        ),
    )


class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ["email", "name", "phone", "company", "job_title", "source", "status", "value", "next_follow_up", "notes"]
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "company": forms.TextInput(attrs={"class": "form-control"}),
            "job_title": forms.TextInput(attrs={"class": "form-control"}),
            "source": forms.TextInput(attrs={"class": "form-control", "placeholder": "csv / website / referral"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "value": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "next_follow_up": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["next_follow_up"].input_formats = ["%Y-%m-%d"]
        self.fields["value"].required = False
        self.fields["next_follow_up"].required = False


class LeadImportForm(forms.Form):
    csv_file = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".csv,text/csv"}),
    )
    paste_list = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 8,
                "placeholder": "email,name,phone,company,source\nana@client.com,Ana Khan,03001234567,Acme,csv",
            }
        ),
    )


def unique_template_slug(name: str, pk=None) -> str:
    base = slugify(name)[:40] or "template"
    slug = base
    n = 2
    while True:
        qs = EmailTemplate.objects.filter(slug=slug)
        if pk:
            qs = qs.exclude(pk=pk)
        if not qs.exists():
            return slug
        slug = f"{base}-{n}"
        n += 1


class TemplateForm(forms.ModelForm):
    layout = forms.ChoiceField(
        required=False,
        widget=forms.RadioSelect(attrs={"class": "layout-radio"}),
        help_text="Start from a professional inbox-safe layout.",
    )

    class Meta:
        model = EmailTemplate
        fields = ["name", "description", "preview_color", "logo", "logo_url", "html_body", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "August client update"}),
            "description": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Short note about when to use this layout"}
            ),
            "preview_color": forms.TextInput(attrs={"class": "form-control", "type": "color"}),
            "logo": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "logo_url": forms.URLInput(
                attrs={"class": "form-control", "placeholder": "https://innovafior.online/logo.png"}
            ),
            "html_body": forms.Textarea(attrs={"class": "form-control font-monospace", "rows": 10}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["layout"].choices = [(item["slug"], item["name"]) for item in DEFAULT_TEMPLATES]
        self.fields["html_body"].required = False
        self.fields["description"].required = False
        self.fields["layout"].initial = self.fields["layout"].initial or "newsletter"
        if not self.instance.pk:
            self.fields["is_active"].initial = True

    def save(self, commit=True):
        obj = super().save(commit=False)
        if not obj.slug:
            obj.slug = unique_template_slug(obj.name, obj.pk)
        layout = self.cleaned_data.get("layout") or "newsletter"
        catalog = next((item for item in DEFAULT_TEMPLATES if item["slug"] == layout), DEFAULT_TEMPLATES[0])
        if not (obj.html_body or "").strip():
            obj.html_body = catalog["html_body"]
        if not obj.preview_color:
            obj.preview_color = catalog["preview_color"]
        if not (obj.description or "").strip():
            obj.description = catalog["description"]
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class NoteForm(forms.Form):
    message = forms.CharField(
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": 3, "placeholder": "Log a call, meeting, or next step"}
        )
    )


class TestEmailForm(forms.Form):
    to_email = forms.EmailField(
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "you@yourdomain.com"})
    )


class SettingsForm(forms.ModelForm):
    class Meta:
        model = AppSettings
        fields = [
            "smtp_host",
            "smtp_port",
            "smtp_user",
            "smtp_password",
            "smtp_use_tls",
            "smtp_use_ssl",
            "from_email",
            "from_name",
            "reply_to",
            "company_name",
            "company_address",
            "website_url",
            "logo",
            "logo_url",
            "brand_color",
            "delay_seconds",
            "batch_pause_every",
            "batch_pause_seconds",
        ]
        widgets = {
            "smtp_host": forms.TextInput(attrs={"class": "form-control"}),
            "smtp_port": forms.NumberInput(attrs={"class": "form-control"}),
            "smtp_user": forms.TextInput(attrs={"class": "form-control"}),
            "smtp_password": forms.PasswordInput(attrs={"class": "form-control", "render_value": True}),
            "smtp_use_tls": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "smtp_use_ssl": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "from_email": forms.EmailInput(attrs={"class": "form-control"}),
            "from_name": forms.TextInput(attrs={"class": "form-control"}),
            "reply_to": forms.EmailInput(attrs={"class": "form-control"}),
            "company_name": forms.TextInput(attrs={"class": "form-control"}),
            "company_address": forms.TextInput(attrs={"class": "form-control"}),
            "website_url": forms.URLInput(attrs={"class": "form-control"}),
            "logo": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "logo_url": forms.URLInput(
                attrs={"class": "form-control", "placeholder": "https://innovafior.online/logo.png"}
            ),
            "brand_color": forms.TextInput(attrs={"class": "form-control", "type": "color"}),
            "delay_seconds": forms.NumberInput(attrs={"class": "form-control", "step": "0.1", "min": "0.05"}),
            "batch_pause_every": forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
            "batch_pause_seconds": forms.NumberInput(attrs={"class": "form-control", "step": "0.5", "min": "0"}),
        }

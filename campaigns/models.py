import secrets

from django.db import models


class EmailTemplate(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    preview_color = models.CharField(max_length=20, default="#2563eb")
    logo = models.ImageField(upload_to="templates/logos/", blank=True)
    logo_url = models.URLField(blank=True, help_text="Public https logo URL so Gmail can load the image.")
    html_body = models.TextField(help_text="Use {{placeholders}} such as {{name}}, {{heading}}, {{body}}, {{logo_block}}")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Campaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        QUEUED = "queued", "Queued"
        SENDING = "sending", "Sending"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    class EditorMode(models.TextChoices):
        TEMPLATE = "template", "Template"
        SIMPLE = "simple", "Simple editor"
        HTML = "html", "HTML custom code"
        DRAGDROP = "dragdrop", "Drag and drop"

    name = models.CharField(max_length=160)
    template = models.ForeignKey(EmailTemplate, on_delete=models.PROTECT, related_name="campaigns")
    editor_mode = models.CharField(max_length=20, choices=EditorMode.choices, default=EditorMode.TEMPLATE)
    html_content = models.TextField(blank=True, help_text="Full or fragment HTML from Simple / HTML / Drag-drop editors.")
    blocks_json = models.JSONField(default=list, blank=True)
    subject = models.CharField(max_length=200)
    preheader = models.CharField(max_length=140, blank=True)
    heading = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    cta_text = models.CharField(max_length=80, blank=True, default="Learn more")
    cta_url = models.URLField(blank=True)
    image_url = models.URLField(blank=True)
    extra_note = models.CharField(max_length=240, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def total_recipients(self):
        return self.recipients.count()

    @property
    def pending_count(self):
        return self.recipients.filter(status=Recipient.Status.PENDING).count()

    @property
    def progress_percent(self):
        total = self.total_recipients
        if not total:
            return 0
        done = self.sent_count + self.failed_count + self.skipped_count
        return min(100, int((done / total) * 100))

    @property
    def attempted_count(self):
        return self.sent_count + self.failed_count

    @property
    def delivery_rate(self):
        attempted = self.attempted_count
        if not attempted:
            return 0
        return int((self.sent_count / attempted) * 100)

    @property
    def editor_label(self):
        return self.get_editor_mode_display()


class Recipient(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="recipients")
    email = models.EmailField()
    name = models.CharField(max_length=160, blank=True)
    company = models.CharField(max_length=160, blank=True)
    extra = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    unsubscribe_token = models.CharField(max_length=64, unique=True, editable=False)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("campaign", "email")
        ordering = ["id"]

    def save(self, *args, **kwargs):
        if not self.unsubscribe_token:
            self.unsubscribe_token = secrets.token_urlsafe(32)[:48]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class Contact(models.Model):
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=160, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    company = models.CharField(max_length=160, blank=True)
    job_title = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    source = models.CharField(max_length=80, blank=True, default="manual")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["email"]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)


class Lead(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        QUALIFIED = "qualified", "Qualified"
        WON = "won", "Won"
        LOST = "lost", "Lost"

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=160, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    company = models.CharField(max_length=160, blank=True)
    job_title = models.CharField(max_length=120, blank=True)
    source = models.CharField(max_length=80, blank=True, default="csv")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    value = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    next_follow_up = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    def to_contact(self):
        contact, _ = Contact.objects.update_or_create(
            email=self.email,
            defaults={
                "name": self.name,
                "phone": self.phone,
                "company": self.company,
                "job_title": self.job_title,
                "notes": self.notes,
                "source": self.source or "lead",
            },
        )
        if self.status == self.Status.NEW:
            self.status = self.Status.CONTACTED
            self.save(update_fields=["status", "updated_at"])
        return contact


class Activity(models.Model):
    class Kind(models.TextChoices):
        NOTE = "note", "Note"
        STATUS = "status", "Stage change"
        EMAIL = "email", "Email"
        CONVERT = "convert", "Converted"

    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="activities")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.NOTE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.lead.email}: {self.message[:40]}"


class Unsubscribe(models.Model):
    email = models.EmailField(unique=True)
    reason = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class AppSettings(models.Model):
    smtp_host = models.CharField(max_length=200, blank=True)
    smtp_port = models.PositiveIntegerField(default=587)
    smtp_user = models.CharField(max_length=200, blank=True)
    smtp_password = models.CharField(max_length=200, blank=True)
    smtp_use_tls = models.BooleanField(default=True)
    smtp_use_ssl = models.BooleanField(default=False)
    from_email = models.EmailField(blank=True)
    from_name = models.CharField(max_length=120, blank=True)
    reply_to = models.EmailField(blank=True)
    company_name = models.CharField(max_length=160, default="Your Company")
    company_address = models.CharField(
        max_length=240,
        default="123 Business Street, City, Country",
        help_text="Required by CAN-SPAM / anti-spam laws. Shown in every email footer.",
    )
    website_url = models.URLField(blank=True, default="https://example.com")
    logo = models.ImageField(upload_to="brand/", blank=True)
    logo_url = models.URLField(
        blank=True,
        help_text="Public https:// logo. Gmail cannot load images from localhost.",
    )
    brand_color = models.CharField(max_length=20, default="#2563eb")
    delay_seconds = models.FloatField(
        default=0.6,
        help_text="Pause between each email. 0.6s ≈ 100 emails/min. Safer for inbox placement.",
    )
    batch_pause_every = models.PositiveIntegerField(default=80)
    batch_pause_seconds = models.FloatField(default=8.0)

    class Meta:
        verbose_name = "App settings"
        verbose_name_plural = "App settings"

    def __str__(self):
        return "Mail settings"

    @classmethod
    def load(cls):
        from django.conf import settings as dj

        obj = cls.objects.first()
        smtp = {
            "smtp_host": dj.EMAIL_HOST or "smtp.hostinger.com",
            "smtp_port": dj.EMAIL_PORT or 465,
            "smtp_user": dj.EMAIL_HOST_USER,
            "smtp_password": dj.EMAIL_HOST_PASSWORD,
            "smtp_use_tls": dj.EMAIL_USE_TLS,
            "smtp_use_ssl": dj.EMAIL_USE_SSL,
            "from_email": dj.DEFAULT_FROM_EMAIL,
            "from_name": dj.DEFAULT_FROM_NAME,
            "reply_to": dj.REPLY_TO_EMAIL,
        }
        if obj:
            env_user = (dj.EMAIL_HOST_USER or "").strip()
            env_pass = (dj.EMAIL_HOST_PASSWORD or "").strip()
            if env_user and env_pass:
                if smtp["smtp_host"] and smtp["smtp_host"] != "localhost":
                    obj.smtp_host = smtp["smtp_host"]
                    obj.smtp_port = smtp["smtp_port"]
                    obj.smtp_use_tls = smtp["smtp_use_tls"]
                    obj.smtp_use_ssl = smtp["smtp_use_ssl"]
                obj.smtp_user = smtp["smtp_user"]
                obj.smtp_password = smtp["smtp_password"]
                if not obj.from_email:
                    obj.from_email = smtp["from_email"]
                if not obj.from_name:
                    obj.from_name = smtp["from_name"]
                if not obj.reply_to:
                    obj.reply_to = smtp["reply_to"]
                obj.save(
                    update_fields=[
                        "smtp_host",
                        "smtp_port",
                        "smtp_user",
                        "smtp_password",
                        "smtp_use_tls",
                        "smtp_use_ssl",
                        "from_email",
                        "from_name",
                        "reply_to",
                    ]
                )
            return obj
        return cls.objects.create(
            **smtp,
            company_name=dj.DEFAULT_FROM_NAME or "Your Company",
            website_url="https://innovafior.online",
        )

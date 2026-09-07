from django.contrib import admin

from .models import (
    Activity,
    AppSettings,
    Campaign,
    Contact,
    EmailDeliveryAttempt,
    EmailJob,
    EmailTemplate,
    Lead,
    Recipient,
    SenderAccount,
    SuppressionEntry,
    Unsubscribe,
    UnsubscribeToken,
)


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "updated_at")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "sent_count", "failed_count", "created_at")
    list_filter = ("status",)


@admin.register(Recipient)
class RecipientAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "campaign", "status", "sent_at")
    list_filter = ("status", "campaign")
    search_fields = ("email", "name")


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "company", "created_at")
    search_fields = ("email", "name", "company")


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("email", "name", "company", "status", "value", "source", "created_at")
    list_filter = ("status", "source")
    search_fields = ("email", "name", "company")


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ("lead", "kind", "created_at")
    list_filter = ("kind",)


@admin.register(Unsubscribe)
class UnsubscribeAdmin(admin.ModelAdmin):
    list_display = ("email", "created_at")
    search_fields = ("email",)


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    list_display = ("from_email", "smtp_host", "delay_seconds")


@admin.register(SenderAccount)
class SenderAccountAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "is_active",
        "sent_today",
        "sent_this_hour",
        "daily_limit",
        "hourly_limit",
        "failure_count",
        "cooldown_until",
    )
    list_filter = ("is_active",)
    search_fields = ("email", "username")
    readonly_fields = (
        "password_encrypted",
        "sent_today",
        "sent_this_hour",
        "day_key",
        "hour_key",
        "last_sent_at",
        "cooldown_until",
        "failure_count",
        "last_smtp_error",
        "created_at",
        "updated_at",
    )
    exclude = ()

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)


@admin.register(EmailJob)
class EmailJobAdmin(admin.ModelAdmin):
    list_display = ("idempotency_key", "status", "sender", "attempt_count", "next_attempt_at")
    list_filter = ("status",)
    search_fields = ("idempotency_key", "last_error")
    readonly_fields = ("idempotency_key",)


@admin.register(EmailDeliveryAttempt)
class EmailDeliveryAttemptAdmin(admin.ModelAdmin):
    list_display = ("job", "sender", "outcome", "smtp_code", "created_at")
    list_filter = ("outcome",)
    readonly_fields = ("job", "sender", "outcome", "smtp_code", "smtp_response", "created_at")


@admin.register(SuppressionEntry)
class SuppressionEntryAdmin(admin.ModelAdmin):
    list_display = ("email", "reason", "source", "created_at")
    list_filter = ("reason",)
    search_fields = ("email",)


@admin.register(UnsubscribeToken)
class UnsubscribeTokenAdmin(admin.ModelAdmin):
    list_display = ("token", "recipient", "used_at")
    search_fields = ("token",)
    readonly_fields = ("token", "recipient", "used_at", "created_at")

from django.contrib import admin

from .models import Activity, AppSettings, Campaign, Contact, EmailTemplate, Lead, Recipient, Unsubscribe


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

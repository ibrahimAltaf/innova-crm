from django.urls import path

from . import views

app_name = "campaigns"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("templates/", views.template_gallery, name="templates"),
    path("campaigns/", views.campaign_list, name="list"),
    path("campaigns/new/", views.campaign_create, name="create"),
    path("campaigns/<int:pk>/", views.campaign_detail, name="detail"),
    path("campaigns/<int:pk>/edit/", views.campaign_edit, name="edit"),
    path("campaigns/<int:pk>/preview/", views.campaign_preview, name="preview"),
    path("campaigns/<int:pk>/recipients/", views.campaign_recipients, name="recipients"),
    path("campaigns/<int:pk>/send/", views.campaign_send, name="send"),
    path("campaigns/<int:pk>/pause/", views.campaign_pause, name="pause"),
    path("campaigns/<int:pk>/test/", views.campaign_test, name="test"),
    path("campaigns/<int:pk>/progress/", views.campaign_progress, name="progress"),
    path("pipeline/", views.pipeline, name="pipeline"),
    path("leads/", views.leads_list, name="leads"),
    path("leads/import/", views.leads_import, name="leads_import"),
    path("leads/<int:pk>/", views.lead_detail, name="lead_detail"),
    path("leads/<int:pk>/move/", views.lead_move, name="lead_move"),
    path("leads/<int:pk>/note/", views.lead_note, name="lead_note"),
    path("leads/<int:pk>/delete/", views.lead_delete, name="lead_delete"),
    path("leads/<int:pk>/convert/", views.lead_convert, name="lead_convert"),
    path("templates/new/", views.template_create, name="template_create"),
    path("templates/<int:pk>/preview/", views.template_preview, name="template_preview"),
    path("templates/<int:pk>/edit/", views.template_edit, name="template_edit"),
    path("contacts/", views.contacts_list, name="contacts"),
    path("contacts/import/", views.contacts_import, name="contacts_import"),
    path("contacts/<int:pk>/delete/", views.contact_delete, name="contact_delete"),
    path("settings/", views.settings_view, name="settings"),
    path("unsubscribe/<str:token>/", views.unsubscribe, name="unsubscribe"),
]

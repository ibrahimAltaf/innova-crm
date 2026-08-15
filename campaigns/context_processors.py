from .models import AppSettings


def site_settings(request):
    try:
        app = AppSettings.objects.first()
    except Exception:
        app = None
    return {"app_settings": app}

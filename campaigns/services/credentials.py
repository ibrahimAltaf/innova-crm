import base64
import hashlib
import logging
import os
import re

from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_SECRET_RE = re.compile(r"(password|passwd|pwd|secret|api[_-]?key)\s*[:=]\s*\S+", re.I)


def credential_fernet() -> Fernet:
    raw = (getattr(settings, "EMAIL_CREDENTIALS_KEY", "") or os.getenv("EMAIL_CREDENTIALS_KEY") or settings.SECRET_KEY).encode()
    digest = hashlib.sha256(raw).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plain: str) -> str:
    value = (plain or "").strip()
    if not value:
        return ""
    return credential_fernet().encrypt(value.encode()).decode()


def decrypt_secret(token: str) -> str:
    value = (token or "").strip()
    if not value:
        return ""
    try:
        return credential_fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        logger.warning("Could not decrypt SMTP credential; check EMAIL_CREDENTIALS_KEY")
        return ""


def sender_password(sender) -> str:
    key = (sender.credential_env_key or "").strip()
    if key:
        return (os.getenv(key) or "").strip().strip('"').strip("'")
    return decrypt_secret(sender.password_encrypted)


def set_sender_password(sender, plain: str) -> None:
    sender.password_encrypted = encrypt_secret(plain)


def redact_smtp_text(text: str) -> str:
    cleaned = _SECRET_RE.sub(r"\1=***", text or "")
    return " ".join(cleaned.split())[:400]

from cryptography.fernet import Fernet
from django.conf import settings
import base64
import hashlib


def _get_key():
    """Derive a Fernet-compatible key from Django SECRET_KEY."""
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(key)


def encrypt_value(value):
    """Encrypt a string value using Fernet symmetric encryption."""
    if not value:
        return ""
    f = Fernet(_get_key())
    return f.encrypt(value.encode()).decode()


def decrypt_value(value):
    """Decrypt a Fernet-encrypted string value."""
    if not value:
        return ""
    f = Fernet(_get_key())
    return f.decrypt(value.encode()).decode()

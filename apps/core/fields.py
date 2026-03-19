"""Fernet-based encrypted model fields for storing sensitive data."""
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _get_fernet():
    """Get Fernet instance using FIELD_ENCRYPTION_KEY from settings."""
    key = getattr(settings, 'FIELD_ENCRYPTION_KEY', '')
    if not key:
        raise ValueError(
            "settings.FIELD_ENCRYPTION_KEY must be set. "
            "Generate one with: python -c "
            "'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


class EncryptedCharField(models.CharField):
    """CharField that transparently encrypts/decrypts values using Fernet.

    - Stored as base64-encoded ciphertext in DB (max_length auto-expanded)
    - Decrypted on read, encrypted on save
    - Supports blank/null like normal CharField
    """

    def __init__(self, *args, **kwargs):
        # Fernet ciphertext is ~2.4x the plaintext size; ensure DB column is large enough
        kwargs.setdefault('max_length', 500)
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        return name, path, args, kwargs

    def get_prep_value(self, value):
        """Encrypt before saving to database."""
        if value is None or value == '':
            return value
        f = _get_fernet()
        return f.encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        """Decrypt when reading from database."""
        if value is None or value == '':
            return value
        try:
            f = _get_fernet()
            return f.decrypt(value.encode()).decode()
        except (InvalidToken, UnicodeDecodeError, TypeError):
            # Decryption failed: value may be plaintext (pre-migration)
            return value

    def value_from_object(self, obj):
        """Return decrypted value for serialization/forms."""
        return getattr(obj, self.attname)


class EncryptedTextField(models.TextField):
    """TextField variant with Fernet encryption for longer secrets."""

    def get_prep_value(self, value):
        if value is None or value == '':
            return value
        f = _get_fernet()
        return f.encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None or value == '':
            return value
        try:
            f = _get_fernet()
            return f.decrypt(value.encode()).decode()
        except (InvalidToken, UnicodeDecodeError, TypeError):
            # Decryption failed: value may be plaintext (pre-migration)
            return value

    def value_from_object(self, obj):
        return getattr(obj, self.attname)

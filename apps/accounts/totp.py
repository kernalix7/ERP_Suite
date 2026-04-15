"""Pure Python TOTP implementation (RFC 6238) — no external dependencies.

Uses standard library: hmac, hashlib, struct, time, base64, secrets.
"""
import base64
import hashlib
import hmac
import secrets
import struct
import time
import urllib.parse


def generate_secret(length=20):
    """Generate a random base32-encoded secret key."""
    random_bytes = secrets.token_bytes(length)
    return base64.b32encode(random_bytes).decode('ascii')


def generate_backup_codes(count=10, length=8):
    """Generate a list of single-use backup codes."""
    codes = []
    for _ in range(count):
        code = secrets.token_hex(length // 2)
        codes.append(code)
    return codes


def _hotp(secret_b32, counter, digits=6):
    """HOTP algorithm (RFC 4226)."""
    key = base64.b32decode(secret_b32.upper())
    msg = struct.pack('>Q', counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    truncated = struct.unpack('>I', h[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(truncated % (10 ** digits)).zfill(digits)


def totp(secret_b32, period=30, digits=6, now=None):
    """Generate a TOTP code for the current time."""
    if now is None:
        now = time.time()
    counter = int(now) // period
    return _hotp(secret_b32, counter, digits)


def verify_totp(secret_b32, code, period=30, digits=6, window=1):
    """Verify a TOTP code, checking +/- window time steps."""
    try:
        now = time.time()
        counter = int(now) // period
        for offset in range(-window, window + 1):
            expected = _hotp(secret_b32, counter + offset, digits)
            if hmac.compare_digest(expected, code):
                return True
    except Exception:
        return False
    return False


def get_totp_uri(secret_b32, username, issuer='ERP Suite'):
    """Generate an otpauth:// URI for QR code generation."""
    label = urllib.parse.quote(f'{issuer}:{username}')
    params = urllib.parse.urlencode({
        'secret': secret_b32,
        'issuer': issuer,
        'algorithm': 'SHA1',
        'digits': 6,
        'period': 30,
    })
    return f'otpauth://totp/{label}?{params}'

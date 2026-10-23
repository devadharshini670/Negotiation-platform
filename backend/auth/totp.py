"""RFC 6238 time-based one-time passwords (Google Authenticator, 1Password, Authy, ...)
using only the standard library, plus recovery codes. `segno` (pure Python) draws the QR."""
import base64
import hashlib
import hmac
import re
import secrets
import struct
import time
from urllib.parse import quote

ISSUER = 'Negotiation Platform'
STEP = 30


def new_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')


def _code_at(secret, step):
    key = base64.b32decode(secret + '=' * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack('>Q', step), hashlib.sha1).digest()
    offset = digest[-1] & 15
    return f'{(struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000:06d}'


def verify(secret, code, last_step=0, now=None, window=1):
    """Returns the matched time-step, or None. Steps at or before `last_step` are rejected,
    so a code that was already used can't be replayed."""
    code = re.sub(r'\s', '', code or '')
    if not re.fullmatch(r'\d{6}', code):
        return None
    current = int((time.time() if now is None else now) // STEP)
    for step in range(current - window, current + window + 1):
        if step > last_step and hmac.compare_digest(_code_at(secret, step), code):
            return step
    return None


def provisioning_uri(secret, account):
    return f'otpauth://totp/{quote(ISSUER)}:{quote(account)}?secret={secret}&issuer={quote(ISSUER)}&digits=6&period={STEP}'


def qr_svg(uri):
    import segno
    return segno.make(uri, error='m').svg_inline(scale=4, dark='#2f2925', light='#ffffff', border=2)


def new_recovery_codes(n=8):
    return [f'{secrets.token_hex(2)}-{secrets.token_hex(2)}-{secrets.token_hex(2)}' for _ in range(n)]


def hash_recovery(code):
    return hashlib.sha256(re.sub(r'[\s-]', '', (code or '').lower()).encode()).hexdigest()

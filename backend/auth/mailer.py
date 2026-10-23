"""Real SMTP sending when credentials are configured (the same pattern the LLM
providers use). In development mode only, and only while no SMTP server is
configured, emails are recorded in a local Dev Outbox so the verification/reset
flow can be completed without a mail account. In production nothing is ever
stored: if mail can't be delivered, the send simply reports failure.
Never labelled as "sent" when it was only logged, and never the reverse."""
import logging
import os
import smtplib
import ssl
import uuid
from datetime import datetime, timezone
from email.mime.text import MIMEText

from . import config, db

log = logging.getLogger(__name__)


def configured():
    return bool(os.getenv('SMTP_HOST') and os.getenv('SMTP_USER') and os.getenv('SMTP_PASS'))


def dev_outbox_enabled():
    """The Dev Outbox exists only in development mode and only without real SMTP."""
    return config.is_dev() and not configured()


def can_send():
    """True when an email address can actually be reached (real SMTP, or the dev outbox)."""
    return configured() or dev_outbox_enabled()


def _scrub(text):
    pw = os.getenv('SMTP_PASS')
    text = str(text)
    if pw and len(pw) >= 3:
        text = text.replace(pw, '***')
    return text[:300]


def _record_outbox(to_email, subject, body):
    with db.LOCK, db.connect() as conn:
        conn.execute('INSERT INTO outbox (id,to_email,subject,body,created_at) VALUES (?,?,?,?,?)',
                     (uuid.uuid4().hex, to_email, subject, body, datetime.now(timezone.utc).isoformat()))
        conn.commit()


def send(to_email, subject, body):
    """Returns (delivered, detail). delivered=True with detail='dev-outbox' means
    it was recorded locally (development only), not actually transmitted."""
    if configured():
        host, port = os.environ['SMTP_HOST'], int(os.getenv('SMTP_PORT', '587'))
        user, pw = os.environ['SMTP_USER'], os.environ['SMTP_PASS']
        from_addr = os.getenv('SMTP_FROM', user)
        msg = MIMEText(body)
        msg['Subject'], msg['From'], msg['To'] = subject, from_addr, to_email
        try:
            with smtplib.SMTP(host, port, timeout=10) as server:
                server.starttls(context=ssl.create_default_context())
                server.login(user, pw)
                server.sendmail(from_addr, [to_email], msg.as_string())
            return True, 'smtp'
        except Exception as exc:
            detail = _scrub(f'{type(exc).__name__}: {exc}')
            log.warning('SMTP delivery failed: %s', detail)
            return False, detail
    if config.is_dev():
        _record_outbox(to_email, subject, body)
        return True, 'dev-outbox'
    log.warning('Email not sent: no SMTP server is configured and APP_ENV is not development.')
    return False, 'email-not-configured'


def outbox_list(limit=25):
    with db.LOCK, db.connect() as conn:
        rows = conn.execute('SELECT * FROM outbox ORDER BY created_at DESC LIMIT ?', (limit,)).fetchall()
    return [dict(r) for r in rows]

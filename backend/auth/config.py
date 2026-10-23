"""Runtime configuration shared by the auth modules.

Everything is read from the environment at call time (not import time) so the
test suite — and `python app.py` — can set values after the module is loaded.

APP_ENV decides whether development shortcuts exist at all:
  * development / dev / local / test  -> the Dev Outbox may be used (only while
    no SMTP server is configured), OAuth buttons show setup hints.
  * anything else, including unset    -> production behaviour: no dev endpoints,
    no setup hints, no emails stored in the database.
`python app.py` on a loopback address defaults to development (see app.py);
any other way of starting the app (gunicorn, a container, ...) defaults to
production, so a forgotten setting can never expose the dev outbox.
"""
import os

PROVIDERS = ('google', 'github')
_DEV_VALUES = {'development', 'dev', 'local', 'test', 'testing'}


def is_dev():
    return os.getenv('APP_ENV', '').strip().lower() in _DEV_VALUES


def base_url():
    """Public origin used in emailed links and default OAuth callbacks. Set
    APP_BASE_URL in production so links never depend on the (spoofable) Host
    header; the request's own origin is only a development fallback."""
    configured = os.getenv('APP_BASE_URL', '').strip().rstrip('/')
    if configured:
        return configured
    from flask import request
    return request.host_url.rstrip('/')


def provider_credentials(name):
    prefix = name.upper()
    client_id = os.getenv(f'{prefix}_CLIENT_ID', '').strip()
    client_secret = os.getenv(f'{prefix}_CLIENT_SECRET', '').strip()
    return (client_id, client_secret) if client_id and client_secret else None


def provider_configured(name):
    return provider_credentials(name) is not None


def redirect_uri(name):
    return os.getenv(f'{name.upper()}_REDIRECT_URI', '').strip() or f'{base_url()}/api/auth/{name}/callback'

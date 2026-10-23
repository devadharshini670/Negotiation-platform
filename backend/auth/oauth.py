"""Google & GitHub sign-in: the OAuth 2.0 authorization-code flow, done by Authlib.

  browser ──GET /api/auth/<provider>/start──▶ 302 to the provider's consent page
  provider ──GET /api/auth/<provider>/callback?code&state──▶ this server
      Authlib checks `state` against the signed session cookie (CSRF defence),
      exchanges the code for a token over a back-channel TLS call (the client
      secret never reaches the browser), and for Google also verifies the ID
      token's signature, issuer, audience, expiry and nonce, and uses PKCE.
      We read the identity, link/create the local account (service.oauth_login),
      create the *same* session as password login, then redirect into the app.

Provider access tokens are used once to read the profile and then discarded —
they are never stored, logged, or sent to the browser. Raw provider errors are
logged server-side only; the browser only ever receives a short error code that
the login page maps to a friendly message.
"""
import copy
import logging
import re
from urllib.parse import quote

from authlib.integrations.flask_client import OAuth
from flask import current_app, redirect, request, session

from . import config, service

log = logging.getLogger(__name__)

PROVIDERS = config.PROVIDERS
STATE_TTL_SECONDS = 600
DEFAULT_NEXT = '/index.html'
_NEXT_RE = re.compile(r'^/(?!/)[A-Za-z0-9_\-./?=&%:+,]{0,300}$')
_GITHUB_NOREPLY = '@users.noreply.github.com'

_SPECS = {
    'google': dict(
        authorize_url='https://accounts.google.com/o/oauth2/v2/auth',
        access_token_url='https://oauth2.googleapis.com/token',
        jwks_uri='https://www.googleapis.com/oauth2/v3/certs',
        userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
        issuer='https://accounts.google.com',
        client_kwargs={'scope': 'openid email profile', 'code_challenge_method': 'S256'},
    ),
    'github': dict(
        authorize_url='https://github.com/login/oauth/authorize',
        access_token_url='https://github.com/login/oauth/access_token',
        api_base_url='https://api.github.com/',
        client_kwargs={'scope': 'read:user user:email'},
    ),
}


def safe_next(value):
    """Only same-site absolute paths are allowed as a post-login destination
    (no scheme, no host, no protocol-relative '//' and no backslashes)."""
    return value if isinstance(value, str) and _NEXT_RE.match(value) else DEFAULT_NEXT


def _client(provider):
    creds = config.provider_credentials(provider)
    if creds is None:
        return None
    oauth = OAuth(current_app._get_current_object())
    client = oauth.register(provider, client_id=creds[0], client_secret=creds[1], **copy.deepcopy(_SPECS[provider]))
    client.framework.expires_in = STATE_TTL_SECONDS
    return client


def _login_error(provider, reason):
    return redirect(f'/login.html?error={provider}_{reason}')


def _drop_pending_states(provider):
    """Abandoned sign-in attempts leave their state in the session cookie; clear
    them before starting a new one so the cookie can't grow past browser limits."""
    prefix = f'_state_{provider}_'
    for key in [k for k in session.keys() if k.startswith(prefix)]:
        session.pop(key, None)


def start(provider, next_url=None):
    client = _client(provider)
    if client is None:
        return _login_error(provider, 'not_configured')
    _drop_pending_states(provider)
    session['oauth_next'] = safe_next(next_url)
    try:
        extra = {'prompt': 'select_account'} if provider == 'google' else {}
        return client.authorize_redirect(config.redirect_uri(provider), **extra)
    except Exception as exc:  # never show internals to the user
        log.warning('OAuth start failed for %s: %s', provider, type(exc).__name__, exc_info=current_app.debug)
        session.pop('oauth_next', None)
        return _login_error(provider, 'failed')


# ────────────────────────────  identity extraction  ────────────────────────────
def _google_identity(client, token):
    # Authlib already verified the ID token (signature, iss, aud, exp, nonce) and
    # put its claims in token['userinfo']; fall back to the userinfo endpoint.
    info = token.get('userinfo') or client.userinfo(token=token)
    verified = info.get('email_verified')
    return dict(subject=info.get('sub'), email=info.get('email'),
                verified=verified is True or str(verified).lower() == 'true',
                hint=info.get('given_name') or info.get('name'))


def pick_github_email(rows):
    """Primary verified address, else any verified one. GitHub's private
    no-reply addresses are skipped: they can't receive mail from us, and the
    profile's public `email` field is never used because it isn't verified."""
    usable = [r for r in rows if isinstance(r, dict) and r.get('verified') and isinstance(r.get('email'), str)
              and r['email'] and not r['email'].lower().endswith(_GITHUB_NOREPLY)]
    primary = next((r for r in usable if r.get('primary')), None)
    chosen = primary or (usable[0] if usable else None)
    return chosen['email'] if chosen else None


def _github_identity(client, token):
    profile = client.get('user', token=token)
    profile.raise_for_status()
    profile = profile.json()
    emails = client.get('user/emails', token=token)
    emails.raise_for_status()
    email = pick_github_email(emails.json())
    return dict(subject=profile.get('id'), email=email, verified=bool(email),
                hint=profile.get('login') or profile.get('name'))


_IDENTITY = {'google': _google_identity, 'github': _github_identity}


def complete(provider):
    client = _client(provider)
    if client is None:
        return _login_error(provider, 'not_configured')
    next_url = safe_next(session.pop('oauth_next', None))

    provider_error = request.args.get('error')
    if provider_error:
        _drop_pending_states(provider)
        return _login_error(provider, 'cancelled' if provider_error == 'access_denied' else 'failed')

    try:
        token = client.authorize_access_token()          # validates `state`, exchanges the code
        who = _IDENTITY[provider](client, token)
        _, csrf = service.oauth_login(provider, who['subject'], who['email'], who['verified'], who['hint'])
    except service.AuthError as exc:
        reason = 'email_unverified' if exc.code == 'email_unverified' else 'failed'
        return _login_error(provider, reason)
    except Exception as exc:  # bad/mismatched state, provider outage, malformed response, ...
        log.warning('OAuth callback failed for %s: %s', provider, type(exc).__name__, exc_info=current_app.debug)
        return _login_error(provider, 'failed')
    if csrf is None:      # two-factor is on for this account: the login page asks for the code
        return redirect('/login.html?mfa=1&next=' + quote(next_url, safe=''))
    return redirect(next_url)

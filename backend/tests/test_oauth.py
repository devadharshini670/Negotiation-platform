"""Google / GitHub sign-in, account linking, email login and production-mode behaviour.

The real Flask routes and the real Authlib client run in these tests, including
OAuth `state` validation and PKCE. Only the calls that would leave the machine
(the provider's token endpoint and API) are replaced with fakes, so no network
and no real OAuth credentials are needed."""
import itertools
import os
import re
from contextlib import contextmanager
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

import pytest
from authlib.integrations.flask_client.apps import FlaskOAuth2App

from app import app
from auth import db as auth_db, mailer

auth_db.reset_for_tests()
_seq = itertools.count(1)

GOOGLE_ENV = {'GOOGLE_CLIENT_ID': 'gid-123.apps.googleusercontent.com', 'GOOGLE_CLIENT_SECRET': 'g-SECRET-do-not-leak',
              'GOOGLE_REDIRECT_URI': 'http://127.0.0.1:5000/api/auth/google/callback'}
GITHUB_ENV = {'GITHUB_CLIENT_ID': 'gh-client-456', 'GITHUB_CLIENT_SECRET': 'gh-SECRET-do-not-leak',
              'GITHUB_REDIRECT_URI': 'http://127.0.0.1:5000/api/auth/github/callback'}
SECRETS = (GOOGLE_ENV['GOOGLE_CLIENT_SECRET'], GITHUB_ENV['GITHUB_CLIENT_SECRET'])


@pytest.fixture
def configured():
    with mock.patch.dict(os.environ, {**GOOGLE_ENV, **GITHUB_ENV}):
        yield


@pytest.fixture
def production():
    with mock.patch.dict(os.environ, {'APP_ENV': 'production'}):
        yield


def new_email():
    return f'social{next(_seq)}@example.com'


class FakeResponse:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError('provider error')


@contextmanager
def fake_google(sub='google-sub-1', email='x@example.com', verified=True, name='Gina Example', captured=None):
    def fetch(self, redirect_uri=None, **kw):
        if captured is not None:
            captured.update(kw, redirect_uri=redirect_uri)
        return {'access_token': 'at', 'token_type': 'Bearer',
                'userinfo': {'sub': sub, 'email': email, 'email_verified': verified, 'name': name, 'given_name': name.split()[0]}}
    with mock.patch.object(FlaskOAuth2App, 'fetch_access_token', fetch):
        yield


@contextmanager
def fake_github(gid=4242, login='octo-cat', emails=None):
    def request(self, method, url, **kw):
        if url == 'user':
            return FakeResponse({'id': gid, 'login': login, 'email': 'public-unverified@example.com'})
        if url == 'user/emails':
            return FakeResponse(emails)
        raise AssertionError(f'unexpected GitHub call: {url}')
    with mock.patch.object(FlaskOAuth2App, 'fetch_access_token', lambda self, **kw: {'access_token': 'at', 'token_type': 'Bearer'}), \
            mock.patch.object(FlaskOAuth2App, 'request', request):
        yield


def start(client, provider, next_url=None):
    r = client.get(f'/api/auth/{provider}/start', query_string={'next': next_url} if next_url else {})
    assert r.status_code == 302, r.data
    return r, parse_qs(urlparse(r.headers['Location']).query)


def sign_in(client, provider, next_url=None, **callback_args):
    _, q = start(client, provider, next_url)
    return client.get(f'/api/auth/{provider}/callback', query_string={'code': 'abc', 'state': q['state'][0], **callback_args})


def me(client):
    return client.get('/api/auth/me').get_json()


def user_count(email):
    with auth_db.connect() as conn:
        return conn.execute('SELECT COUNT(*) FROM users WHERE email=?', (email.lower(),)).fetchone()[0]


def mail_to(email):
    return [m for m in mailer.outbox_list(500) if m['to_email'] == email]


def register(client, email, password='Passw0rd!'):
    username = f'pw_user{next(_seq)}'
    r = client.post('/api/auth/register', json={'username': username, 'email': email, 'password': password})
    assert r.status_code == 201, r.get_json()
    return username, re.search(r'code on the verification page:\s*\n(\S+)', mail_to(email)[0]['body']).group(1)


def register_verified(client, email, password='Passw0rd!'):
    username, token = register(client, email, password)
    assert client.get(f'/api/auth/verify-email?token={token}').status_code == 200
    return username


# ───────────────────────── not configured: never crash, never fake success ─────────────────────────
def test_unconfigured_providers_are_reported_and_do_not_crash():
    c = app.test_client()
    cfg = c.get('/api/auth/config').get_json()
    assert cfg['providers']['google']['enabled'] is False and cfg['providers']['github']['enabled'] is False
    assert 'GOOGLE_CLIENT_ID' in cfg['providers']['google']['hint']          # dev mode explains how to enable it
    for p in ('google', 'github'):
        r = c.get(f'/api/auth/{p}/start')
        assert r.status_code == 302 and r.headers['Location'] == f'/login.html?error={p}_not_configured'
        r = c.get(f'/api/auth/{p}/callback', query_string={'code': 'x', 'state': 'y'})
        assert r.status_code == 302 and r.headers['Location'] == f'/login.html?error={p}_not_configured'
    assert me(c) == {'authenticated': False}


def test_production_config_has_no_setup_hints(production):
    cfg = app.test_client().get('/api/auth/config').get_json()
    assert all('hint' not in v for v in cfg['providers'].values())


def test_config_endpoint_never_contains_secrets(configured):
    body = app.test_client().get('/api/auth/config').get_data(as_text=True)
    assert not any(s in body for s in SECRETS) and '"enabled":true' in body.replace(' ', '')


def test_unknown_provider_is_404():
    c = app.test_client()
    assert c.get('/api/auth/facebook/start').status_code == 404
    assert c.get('/api/auth/facebook/callback').status_code == 404


# ───────────────────────── start routes: real redirects to the provider ─────────────────────────
def test_google_start_redirects_with_state_pkce_nonce_and_no_secret(configured):
    r, q = start(app.test_client(), 'google')
    url = urlparse(r.headers['Location'])
    assert (url.scheme, url.netloc, url.path) == ('https', 'accounts.google.com', '/o/oauth2/v2/auth')
    assert q['client_id'] == [GOOGLE_ENV['GOOGLE_CLIENT_ID']] and q['response_type'] == ['code']
    assert q['redirect_uri'] == [GOOGLE_ENV['GOOGLE_REDIRECT_URI']]
    assert {'openid', 'email', 'profile'} <= set(q['scope'][0].split())
    assert len(q['state'][0]) >= 20 and q['nonce'] and q['code_challenge'] and q['code_challenge_method'] == ['S256']
    assert q['prompt'] == ['select_account']
    assert not any(s in r.headers['Location'] for s in SECRETS)


def test_github_start_redirects_with_state_and_email_scope(configured):
    r, q = start(app.test_client(), 'github')
    url = urlparse(r.headers['Location'])
    assert (url.netloc, url.path) == ('github.com', '/login/oauth/authorize')
    assert q['client_id'] == [GITHUB_ENV['GITHUB_CLIENT_ID']] and q['redirect_uri'] == [GITHUB_ENV['GITHUB_REDIRECT_URI']]
    assert 'user:email' in q['scope'][0].split() and len(q['state'][0]) >= 20
    assert not any(s in r.headers['Location'] for s in SECRETS)


def test_redirect_uri_is_configurable_and_defaults_to_the_app_origin(configured):
    with mock.patch.dict(os.environ, {'GOOGLE_REDIRECT_URI': 'https://app.example.com/api/auth/google/callback'}):
        _, q = start(app.test_client(), 'google')
        assert q['redirect_uri'] == ['https://app.example.com/api/auth/google/callback']
    with mock.patch.dict(os.environ, {'GOOGLE_REDIRECT_URI': '', 'APP_BASE_URL': 'https://prod.example.com/'}):
        _, q = start(app.test_client(), 'google')
        assert q['redirect_uri'] == ['https://prod.example.com/api/auth/google/callback']


def test_repeated_start_clicks_do_not_pile_up_state_in_the_cookie(configured):
    c = app.test_client()
    for _ in range(8):
        start(c, 'google')
    with c.session_transaction() as s:
        assert len([k for k in s if k.startswith('_state_google_')]) == 1


# ───────────────────────── callback security ─────────────────────────
def test_callback_rejects_forged_or_missing_state(configured):
    c = app.test_client()
    with fake_google(email=new_email()):
        r = c.get('/api/auth/google/callback', query_string={'code': 'abc', 'state': 'forged'})     # never started
        assert r.headers['Location'] == '/login.html?error=google_failed'
        start(c, 'google')
        r = c.get('/api/auth/google/callback', query_string={'code': 'abc', 'state': 'forged'})     # started, wrong state
        assert r.headers['Location'] == '/login.html?error=google_failed'
        assert c.get('/api/auth/google/callback', query_string={'code': 'abc'}).headers['Location'] == '/login.html?error=google_failed'
    assert me(c) == {'authenticated': False}


def test_state_cannot_be_replayed_and_is_not_valid_for_another_browser(configured):
    email = new_email()
    victim, attacker = app.test_client(), app.test_client()
    _, q = start(victim, 'google')
    state = q['state'][0]
    with fake_google(email=email):
        # an attacker-supplied callback URL opened in a different browser has no matching state
        assert attacker.get('/api/auth/google/callback', query_string={'code': 'c', 'state': state}).headers['Location'].endswith('google_failed')
        assert me(attacker) == {'authenticated': False}
        assert victim.get('/api/auth/google/callback', query_string={'code': 'c', 'state': state}).headers['Location'] == '/index.html'
        assert victim.get('/api/auth/google/callback', query_string={'code': 'c', 'state': state}).headers['Location'].endswith('google_failed')


@pytest.mark.parametrize('provider', ['google', 'github'])
def test_cancelled_consent_gives_a_cancelled_message_code(configured, provider):
    c = app.test_client()
    _, q = start(c, provider)
    r = c.get(f'/api/auth/{provider}/callback', query_string={'error': 'access_denied', 'state': q['state'][0]})
    assert r.headers['Location'] == f'/login.html?error={provider}_cancelled'
    assert me(c) == {'authenticated': False}


def test_provider_errors_are_hidden_from_the_browser(configured):
    c = app.test_client()
    _, q = start(c, 'google')
    with mock.patch.object(FlaskOAuth2App, 'fetch_access_token', side_effect=RuntimeError('token endpoint exploded: g-SECRET-do-not-leak')):
        r = c.get('/api/auth/google/callback', query_string={'code': 'c', 'state': q['state'][0]})
    assert r.headers['Location'] == '/login.html?error=google_failed' and 'exploded' not in r.get_data(as_text=True) + r.headers['Location']
    r = c.get('/api/auth/google/callback', query_string={'error': 'server_error', 'error_description': '<script>alert(1)</script>'})
    assert r.headers['Location'] == '/login.html?error=google_failed'


def test_next_is_only_honoured_for_same_site_paths(configured):
    with fake_google(email=new_email(), sub='nx-1'):
        assert sign_in(app.test_client(), 'google', '/negotiation.html?id=abc123').headers['Location'] == '/negotiation.html?id=abc123'
    for evil in ('https://evil.example/', '//evil.example', '/\\evil.example', 'javascript:alert(1)', 'evil'):
        with fake_google(email=new_email(), sub=f'nx-{evil}'):
            assert sign_in(app.test_client(), 'google', evil).headers['Location'] == '/index.html', evil


# ───────────────────────── Google: sign-up, session, linking ─────────────────────────
def test_google_sign_up_creates_a_verified_passwordless_account_and_normal_session(configured):
    c, email, captured = app.test_client(), new_email(), {}
    with fake_google(email=email, sub='sub-new', name='Gina Example', captured=captured):
        r = sign_in(c, 'google')
    assert r.status_code == 302 and r.headers['Location'] == '/index.html'
    assert captured['code_verifier'] and captured['redirect_uri'] == GOOGLE_ENV['GOOGLE_REDIRECT_URI']   # PKCE + exact redirect URI
    info = me(c)
    assert info['authenticated'] and info['user']['email'] == email and info['user']['email_verified'] is True
    assert re.fullmatch(r'[A-Za-z0-9_]{3,24}', info['user']['username']) and '@' not in info['user']['username']
    assert info['user']['username'].startswith('Gina')
    with auth_db.connect() as conn:
        assert conn.execute('SELECT password_hash FROM users WHERE email=?', (email,)).fetchone()[0] == ''
    # identical session machinery: CSRF-protected create works, history is scoped, logout ends it
    body = {'scenario_id': 'vendor_pricing', 'personality_a': 'aggressive', 'personality_b': 'collaborative'}
    assert c.post('/api/negotiations', json=body).status_code == 403
    assert c.post('/api/negotiations', json=body, headers={'X-CSRF-Token': info['csrf_token']}).status_code == 201
    assert c.get('/api/negotiations').status_code == 200
    assert c.post('/api/auth/logout').status_code == 200
    assert c.get('/api/negotiations').status_code == 401
    cookie = [h for h in r.headers.getlist('Set-Cookie') if h.startswith('session=')][0]
    assert 'HttpOnly' in cookie and 'SameSite=Lax' in cookie


def test_google_links_to_existing_verified_account_instead_of_duplicating(configured):
    email = new_email()
    username = register_verified(app.test_client(), email)
    original = app.test_client()
    uid = original.post('/api/auth/login', json={'email': email, 'password': 'Passw0rd!'}).get_json()['user']['id']

    c = app.test_client()
    with fake_google(email=email.upper(), sub='sub-link'):
        assert sign_in(c, 'google').headers['Location'] == '/index.html'
    assert me(c)['user']['id'] == uid and me(c)['user']['username'] == username
    assert user_count(email) == 1
    # the password still works, and the Google identity keeps working
    assert app.test_client().post('/api/auth/login', json={'email': email, 'password': 'Passw0rd!'}).status_code == 200
    with fake_google(email=email, sub='sub-link'):
        again = _signed_in(app.test_client(), 'google')
    assert me(again)['user']['id'] == uid


def _signed_in(client, provider):
    assert sign_in(client, provider).headers['Location'] == '/index.html'
    return client


def test_unverified_password_account_cannot_be_used_to_hijack_a_later_google_sign_in(configured):
    victim_email = new_email()
    _, stale_verify_token = register(app.test_client(), victim_email, 'Attacker1!')      # squatter, never verified
    assert app.test_client().post('/api/auth/login', json={'email': victim_email, 'password': 'Attacker1!'}).status_code == 403

    owner = app.test_client()
    with fake_google(email=victim_email, sub='real-owner'):
        assert sign_in(owner, 'google').headers['Location'] == '/index.html'
    assert user_count(victim_email) == 1 and me(owner)['user']['email_verified'] is True

    squatter = app.test_client()
    assert squatter.post('/api/auth/login', json={'email': victim_email, 'password': 'Attacker1!'}).status_code != 200
    assert me(squatter) == {'authenticated': False}
    assert squatter.get(f'/api/auth/verify-email?token={stale_verify_token}').status_code == 400   # old tokens revoked


def test_unverified_google_email_is_rejected_and_creates_nothing(configured):
    c, email = app.test_client(), new_email()
    with fake_google(email=email, verified=False):
        assert sign_in(c, 'google').headers['Location'] == '/login.html?error=google_email_unverified'
    assert me(c) == {'authenticated': False} and user_count(email) == 0
    with fake_google(email=email, verified='true', sub='str-true'):          # some responses encode booleans as strings
        assert sign_in(c, 'google').headers['Location'] == '/index.html'


def test_known_identity_still_signs_in_when_the_provider_email_changes(configured):
    first, second = new_email(), new_email()
    with fake_google(email=first, sub='stable-sub'):
        c = app.test_client(); sign_in(c, 'google'); uid = me(c)['user']['id']
    with fake_google(email=second, sub='stable-sub'):
        c = app.test_client(); sign_in(c, 'google')
    assert me(c)['user']['id'] == uid and me(c)['user']['email'] == first
    assert user_count(second) == 0


# ───────────────────────── GitHub ─────────────────────────
def test_github_sign_up_uses_the_primary_verified_email_and_skips_noreply_addresses(configured):
    email = new_email()
    emails = [{'email': '1+octo@users.noreply.github.com', 'primary': False, 'verified': True},
              {'email': 'other-' + email, 'primary': False, 'verified': True},
              {'email': email, 'primary': True, 'verified': True}]
    c = app.test_client()
    with fake_github(gid=777, login='octo-cat', emails=emails):
        assert sign_in(c, 'github').headers['Location'] == '/index.html'
    u = me(c)['user']
    assert u['email'] == email and u['username'] == 'octocat' and u['email_verified'] is True


@pytest.mark.parametrize('emails', [
    [{'email': 'a@example.com', 'primary': True, 'verified': False}],
    [{'email': '9+x@users.noreply.github.com', 'primary': True, 'verified': True}],
    [],
])
def test_github_without_a_usable_verified_email_is_rejected(configured, emails):
    c = app.test_client()
    with fake_github(gid=next(_seq) + 9000, emails=emails):
        assert sign_in(c, 'github').headers['Location'] == '/login.html?error=github_email_unverified'
    assert me(c) == {'authenticated': False}


def test_github_never_links_through_an_unverified_email(configured):
    victim = new_email()
    register_verified(app.test_client(), victim)
    mine = new_email()
    emails = [{'email': victim, 'primary': True, 'verified': False}, {'email': mine, 'primary': False, 'verified': True}]
    c = app.test_client()
    with fake_github(gid=31337, login='attacker', emails=emails):
        assert sign_in(c, 'github').headers['Location'] == '/index.html'
    assert me(c)['user']['email'] == mine                       # a separate account — the victim's was untouched
    assert user_count(victim) == 1


def test_username_collisions_get_a_numeric_suffix(configured):
    with fake_github(gid=501, login='samename', emails=[{'email': new_email(), 'primary': True, 'verified': True}]):
        a = app.test_client(); sign_in(a, 'github')
    with fake_github(gid=502, login='samename', emails=[{'email': new_email(), 'primary': True, 'verified': True}]):
        b = app.test_client(); sign_in(b, 'github')
    assert me(a)['user']['username'] == 'samename' and me(b)['user']['username'].startswith('samename') and me(b)['user']['username'] != 'samename'


# ───────────────────────── email + password login & messages ─────────────────────────
def test_email_is_the_primary_login_and_errors_are_realistic():
    c, email = app.test_client(), new_email()
    username, token = register(c, email)
    r = c.post('/api/auth/login', json={'email': email, 'password': 'Passw0rd!'})
    assert r.status_code == 403 and r.get_json()['error'] == 'Please verify your email before signing in.'
    c.get(f'/api/auth/verify-email?token={token}')
    assert c.post('/api/auth/login', json={'email': email.upper(), 'password': 'Passw0rd!'}).status_code == 200
    assert app.test_client().post('/api/auth/login', json={'username': username, 'password': 'Passw0rd!'}).status_code == 200   # backward compatible
    wrong = app.test_client().post('/api/auth/login', json={'email': email, 'password': 'nope-nope1'})
    unknown = app.test_client().post('/api/auth/login', json={'email': 'ghost@example.com', 'password': 'nope-nope1'})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.get_json()['error'] == unknown.get_json()['error'] == 'Invalid email or password.'
    assert app.test_client().post('/api/auth/login', json={'email': ['x'], 'password': {'a': 1}}).status_code == 401


def test_social_only_accounts_get_a_helpful_message_instead_of_a_password_login(configured):
    email = new_email()
    with fake_google(email=email, sub='so-g'):
        sign_in(app.test_client(), 'google')
    r = app.test_client().post('/api/auth/login', json={'email': email, 'password': 'Whatever1'})
    assert r.status_code == 400 and r.get_json()['error'] == 'This account was created using Google. Please continue with Google.'
    with fake_github(gid=888, emails=[{'email': new_email(), 'primary': True, 'verified': True}]):
        gh_email = me(_signed_in(app.test_client(), 'github'))['user']['email']
    r = app.test_client().post('/api/auth/login', json={'email': gh_email, 'password': 'Whatever1'})
    assert r.get_json()['error'] == 'This account was created using GitHub. Please continue with GitHub.'
    with fake_github(gid=889, emails=[{'email': email, 'primary': True, 'verified': True}]):
        sign_in(app.test_client(), 'github')                    # same verified email -> linked to the Google-created account
    assert 'Google or GitHub' in app.test_client().post('/api/auth/login', json={'email': email, 'password': 'x'}).get_json()['error']
    assert user_count(email) == 1


def test_forgot_password_gives_one_answer_but_social_accounts_get_guidance_not_a_reset(configured):
    email = new_email()
    with fake_google(email=email, sub='fp-g'):
        sign_in(app.test_client(), 'google')
    c = app.test_client()
    social = c.post('/api/auth/request-password-reset', json={'email': email})
    unknown = c.post('/api/auth/request-password-reset', json={'email': 'nobody-at-all@example.com'})
    assert social.status_code == unknown.status_code == 200 and social.get_json() == unknown.get_json()
    assert 'Google or GitHub' in social.get_json()['message']
    mail = mail_to(email)[-1] if mail_to(email) else None
    assert mail and 'Continue with Google' in mail['body'] and 'reset page' not in mail['body']
    with auth_db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM tokens WHERE kind='reset' AND user_id=(SELECT id FROM users WHERE email=?)", (email,)).fetchone()[0] == 0
    assert c.post('/api/auth/reset-password', json={'token': 'made-up', 'password': 'NewPass1!'}).status_code == 400
    assert not mail_to('nobody-at-all@example.com')


# ───────────────────────── development shortcuts must not exist in production ─────────────────────────
def test_dev_outbox_exists_only_in_development_without_smtp():
    c = app.test_client()
    assert c.get('/api/auth/dev-outbox').status_code == 200 and c.get('/dev-outbox.html').status_code == 200


def test_production_has_no_dev_outbox_and_stores_no_emails(production):
    c, before = app.test_client(), len(mailer.outbox_list(1000))
    assert c.get('/api/auth/dev-outbox').status_code == 404
    assert c.get('/dev-outbox.html').status_code == 404
    r = c.post('/api/auth/register', json={'username': f'prod_user{next(_seq)}', 'email': new_email(), 'password': 'Passw0rd!'})
    assert r.status_code == 503 and 'Google or GitHub' in r.get_json()['error']
    assert c.post('/api/auth/request-password-reset', json={'email': 'someone@example.com'}).status_code == 200
    assert len(mailer.outbox_list(1000)) == before
    assert c.get('/api/auth/config').get_json()['email_signup'] is False


def test_production_with_smtp_still_hides_the_dev_outbox_and_sends_real_mail(production):
    sent = []

    class FakeSMTP:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self, **k): pass
        def login(self, *a): pass
        def sendmail(self, frm, to, msg): sent.append((to, msg))

    env = {'SMTP_HOST': 'smtp.example.com', 'SMTP_USER': 'u@example.com', 'SMTP_PASS': 'pw-123456'}
    with mock.patch.dict(os.environ, env), mock.patch('auth.mailer.smtplib.SMTP', FakeSMTP):
        c, before = app.test_client(), len(mailer.outbox_list(1000))
        assert c.get('/api/auth/dev-outbox').status_code == 404 and c.get('/dev-outbox.html').status_code == 404
        email = new_email()
        assert c.post('/api/auth/register', json={'username': f'prod_user{next(_seq)}', 'email': email, 'password': 'Passw0rd!'}).status_code == 201
        assert sent and sent[0][0] == [email] and len(mailer.outbox_list(1000)) == before


# ───────────────────────── nothing sensitive in the frontend ─────────────────────────
def test_frontend_contains_no_secrets_and_never_persists_provider_tokens():
    frontend = Path(__file__).resolve().parents[2] / 'frontend'
    for path in frontend.glob('*'):
        if path.suffix in ('.html', '.js', '.css'):
            text = path.read_text(encoding='utf-8')
            assert not any(s in text for s in SECRETS), path.name
            assert 'client_secret' not in text.lower() and 'access_token' not in text, path.name
    storage_uses = re.findall(r'localStorage\.\w+\(([^)]*)\)', (frontend / 'api.js').read_text(encoding='utf-8'))
    assert storage_uses and all(u.startswith('THEME_KEY') for u in storage_uses)      # localStorage is only used for the theme

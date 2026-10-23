"""Account settings: username, password, unlinking, two-factor authentication,
data export, deletion — and the in-place upgrade of a pre-existing database."""
import itertools
import os
import re
import sqlite3
import tempfile
import time
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import mock
from urllib.parse import parse_qs, urlparse

from authlib.integrations.flask_client.apps import FlaskOAuth2App

from app import app
from auth import db as auth_db, mailer, totp

auth_db.reset_for_tests()
_n = itertools.count(1)
BASE_STEP = int(time.time() // 30) + 10          # fake-clock steps start well after any real "enable" step
GOOGLE_ENV = {'GOOGLE_CLIENT_ID': 'gid', 'GOOGLE_CLIENT_SECRET': 'gsecret', 'GOOGLE_REDIRECT_URI': 'http://127.0.0.1:5000/api/auth/google/callback'}


@contextmanager
def at_step(k):
    """Pretend it is time-step BASE_STEP+k (so each test can use fresh, increasing codes)."""
    with mock.patch.object(totp, 'time', SimpleNamespace(time=lambda: (BASE_STEP + k) * 30 + 5)):
        yield


def code(secret, k):
    return totp._code_at(secret, BASE_STEP + k)


def new_user(password='Passw0rd!'):
    n = next(_n)
    email, username = f'acct{n}@example.com', f'acct_user{n}'
    c = app.test_client()
    assert c.post('/api/auth/register', json={'username': username, 'email': email, 'password': password}).status_code == 201
    body = next(m['body'] for m in mailer.outbox_list(500) if m['to_email'] == email)
    c.get('/api/auth/verify-email?token=' + re.search(r'code on the verification page:\s*\n(\S+)', body).group(1))
    r = c.post('/api/auth/login', json={'email': email, 'password': password})
    assert r.status_code == 200
    return c, {'X-CSRF-Token': r.get_json()['csrf_token']}, email, username


def google_signup(email, sub):
    with mock.patch.dict(os.environ, GOOGLE_ENV), mock.patch.object(
            FlaskOAuth2App, 'fetch_access_token',
            lambda self, **kw: {'access_token': 't', 'userinfo': {'sub': sub, 'email': email, 'email_verified': True, 'given_name': 'Gia'}}):
        c = app.test_client()
        loc = c.get('/api/auth/google/start').headers['Location']
        state = parse_qs(urlparse(loc).query)['state'][0]
        r = c.get('/api/auth/google/callback', query_string={'code': 'x', 'state': state})
    return c, r


def csrf_of(c):
    return {'X-CSRF-Token': c.get('/api/auth/me').get_json()['csrf_token']}


def enable_2fa(c, h):
    setup = c.post('/api/account/2fa/setup', headers=h).get_json()
    secret = setup['secret']
    assert setup['qr_svg'].startswith('<svg') and setup['uri'].startswith('otpauth://totp/')
    with at_step(0):
        r = c.post('/api/account/2fa/enable', json={'code': code(secret, 0)}, headers=h)
    assert r.status_code == 200
    return secret, r.get_json()['recovery_codes']


# ───────────────────────── username ─────────────────────────
def test_username_change_validates_is_unique_and_needs_csrf():
    c, h, _, username = new_user()
    _, _, _, other = new_user()
    assert c.post('/api/account/username', json={'username': 'fresh_name'}).status_code == 403
    for bad in ('ab', 'has space', 'x' * 25, '', None, ['a']):
        assert c.post('/api/account/username', json={'username': bad}, headers=h).status_code == 400
    assert c.post('/api/account/username', json={'username': other.upper()}, headers=h).status_code == 400   # case-insensitive clash
    assert c.post('/api/account/username', json={'username': username}, headers=h).status_code == 200          # keeping your own is fine
    assert c.post('/api/account/username', json={'username': 'fresh_name'}, headers=h).get_json() == {'username': 'fresh_name'}
    assert c.get('/api/auth/me').get_json()['user']['username'] == 'fresh_name'
    assert app.test_client().post('/api/auth/login', json={'username': 'fresh_name', 'password': 'Passw0rd!'}).status_code == 200


def test_username_change_updates_existing_negotiations_and_leaderboard_name():
    c, h, _, _ = new_user()
    nid = c.post('/api/negotiations', json={'scenario_id': 'vendor_pricing', 'personality_a': 'aggressive', 'personality_b': 'collaborative',
                                           'workflow_mode': 'practice'}, headers=h).get_json()['id']
    c.post('/api/account/username', json={'username': 'renamed_user'}, headers=h)
    from engine import negotiation_engine as engine
    assert engine.get_negotiation(nid).owner_username == 'renamed_user'


# ───────────────────────── password & unlinking ─────────────────────────
def test_password_change_requires_the_current_password():
    c, h, email, _ = new_user()
    assert c.post('/api/account/password', json={'current_password': 'wrong', 'new_password': 'NewPass1!'}, headers=h).status_code == 403
    assert c.post('/api/account/password', json={'current_password': 'Passw0rd!', 'new_password': 'short'}, headers=h).status_code == 400
    assert c.post('/api/account/password', json={'current_password': 'Passw0rd!', 'new_password': 'NewPass1!'}, headers=h).status_code == 200
    assert app.test_client().post('/api/auth/login', json={'email': email, 'password': 'NewPass1!'}).status_code == 200
    assert app.test_client().post('/api/auth/login', json={'email': email, 'password': 'Passw0rd!'}).status_code == 401


def test_cannot_unlink_the_only_sign_in_method_but_can_after_setting_a_password():
    email = f'unlink{next(_n)}@example.com'
    c, r = google_signup(email, 'unlink-sub')
    assert r.headers['Location'] == '/index.html'
    h = csrf_of(c)
    info = c.get('/api/account').get_json()
    assert info['has_password'] is False and [i['provider'] for i in info['identities']] == ['google']
    blocked = c.post('/api/account/unlink', json={'provider': 'google'}, headers=h)
    assert blocked.status_code == 409 and 'Set a password' in blocked.get_json()['error']
    assert c.post('/api/account/password', json={'new_password': 'Brand1New!'}, headers=h).status_code == 200      # no current password needed
    assert c.post('/api/account/unlink', json={'provider': 'github'}, headers=h).status_code == 404
    assert c.post('/api/account/unlink', json={'provider': 'google'}, headers=h).status_code == 200
    assert c.get('/api/account').get_json()['identities'] == []
    assert app.test_client().post('/api/auth/login', json={'email': email, 'password': 'Brand1New!'}).status_code == 200


# ───────────────────────── two-factor authentication ─────────────────────────
def test_two_factor_setup_enable_and_login_flow():
    c, h, email, _ = new_user()
    secret, recovery = enable_2fa(c, h)
    assert len(recovery) == 8 and c.get('/api/account').get_json()['two_factor'] == {'enabled': True, 'recovery_codes_left': 8}
    assert c.post('/api/account/2fa/setup', headers=h).status_code == 409                   # already on

    d = app.test_client()
    r = d.post('/api/auth/login', json={'email': email, 'password': 'Passw0rd!'})
    assert r.status_code == 200 and r.get_json() == {'mfa_required': True}                  # password alone is not enough
    assert d.get('/api/negotiations').status_code == 401 and d.get('/api/auth/me').get_json() == {'authenticated': False}
    with at_step(1):
        assert d.post('/api/auth/2fa/verify', json={'code': '000000'}).status_code == 401
        ok = d.post('/api/auth/2fa/verify', json={'code': code(secret, 1)})
    assert ok.status_code == 200 and ok.get_json()['csrf_token'] and d.get('/api/negotiations').status_code == 200

    e = app.test_client()                                                                    # the same code can't be replayed
    e.post('/api/auth/login', json={'email': email, 'password': 'Passw0rd!'})
    with at_step(1):
        assert e.post('/api/auth/2fa/verify', json={'code': code(secret, 1)}).status_code == 401
    with at_step(2):
        assert e.post('/api/auth/2fa/verify', json={'code': code(secret, 2)}).status_code == 200


def test_enabling_requires_a_valid_code_and_nothing_changes_without_it():
    c, h, email, _ = new_user()
    assert c.post('/api/account/2fa/enable', json={'code': '123456'}, headers=h).status_code == 409   # no setup yet
    c.post('/api/account/2fa/setup', headers=h)
    assert c.post('/api/account/2fa/enable', json={'code': '000000'}, headers=h).status_code == 400
    assert app.test_client().post('/api/auth/login', json={'email': email, 'password': 'Passw0rd!'}).get_json().get('mfa_required') is None


def test_recovery_codes_work_once_and_wrong_codes_lock_the_account():
    c, h, email, _ = new_user()
    secret, recovery = enable_2fa(c, h)
    d = app.test_client()
    d.post('/api/auth/login', json={'email': email, 'password': 'Passw0rd!'})
    assert d.post('/api/auth/2fa/verify', json={'code': recovery[0].upper()}).status_code == 200
    e = app.test_client()
    e.post('/api/auth/login', json={'email': email, 'password': 'Passw0rd!'})
    assert e.post('/api/auth/2fa/verify', json={'code': recovery[0]}).status_code == 401           # already used
    assert c.get('/api/account').get_json()['two_factor']['recovery_codes_left'] == 7
    with at_step(3):
        for _ in range(4):                      # 1 wrong above + 4 = 5 -> locked, even with a fresh cookie each time
            f = app.test_client()
            f.post('/api/auth/login', json={'email': email, 'password': 'Passw0rd!'})
            assert f.post('/api/auth/2fa/verify', json={'code': '111111'}).status_code in (401, 429)
        g = app.test_client()
        assert g.post('/api/auth/login', json={'email': email, 'password': 'Passw0rd!'}).status_code == 429
        assert g.post('/api/auth/2fa/verify', json={'code': code(secret, 3)}).status_code == 401      # no pending session


def test_verify_without_a_pending_login_is_rejected():
    assert app.test_client().post('/api/auth/2fa/verify', json={'code': '123456'}).status_code == 401


def test_google_sign_in_also_requires_the_second_factor():
    email = f'g2fa{next(_n)}@example.com'
    c, _ = google_signup(email, 'g2fa-sub')
    h = csrf_of(c)
    c.post('/api/account/password', json={'new_password': 'Brand1New!'}, headers=h)
    secret, _ = enable_2fa(c, h)
    d, r = google_signup(email, 'g2fa-sub')
    assert r.headers['Location'].startswith('/login.html?mfa=1&next=')
    assert d.get('/api/negotiations').status_code == 401
    with at_step(5):
        assert d.post('/api/auth/2fa/verify', json={'code': code(secret, 5)}).status_code == 200
    assert d.get('/api/negotiations').status_code == 200


def test_disabling_two_factor_needs_a_code():
    c, h, email, _ = new_user()
    secret, _ = enable_2fa(c, h)
    assert c.post('/api/account/2fa/disable', json={'code': '000000'}, headers=h).status_code == 403
    with at_step(7):
        assert c.post('/api/account/2fa/disable', json={'code': code(secret, 7)}, headers=h).status_code == 200
    assert c.get('/api/account').get_json()['two_factor']['enabled'] is False
    assert 'mfa_required' not in app.test_client().post('/api/auth/login', json={'email': email, 'password': 'Passw0rd!'}).get_json()


# ───────────────────────── export & deletion ─────────────────────────
def test_export_contains_my_data_only_and_no_credentials():
    c, h, email, username = new_user()
    other, oh, _, _ = new_user()
    mine = c.post('/api/negotiations', json={'scenario_id': 'vendor_pricing', 'personality_a': 'aggressive', 'personality_b': 'collaborative'}, headers=h).get_json()['id']
    other.post('/api/negotiations', json={'scenario_id': 'vendor_pricing', 'personality_a': 'aggressive', 'personality_b': 'collaborative'}, headers=oh)
    r = c.get('/api/account/export')
    assert r.status_code == 200 and 'attachment' in r.headers['Content-Disposition']
    data = r.get_json()
    assert data['account']['email'] == email and data['account']['username'] == username
    assert [n['id'] for n in data['negotiations']] == [mine]
    body = r.get_data(as_text=True).lower()
    assert 'password_hash' not in body and 'totp_secret' not in body and 'pbkdf2' not in body and 'scrypt' not in body
    assert app.test_client().get('/api/account/export').status_code == 401


def test_account_deletion_removes_everything_and_needs_confirmation():
    c, h, email, username = new_user()
    other, oh, _, _ = new_user()
    nid = c.post('/api/negotiations', json={'scenario_id': 'vendor_pricing', 'personality_a': 'aggressive', 'personality_b': 'collaborative'}, headers=h).get_json()['id']
    keep = other.post('/api/negotiations', json={'scenario_id': 'vendor_pricing', 'personality_a': 'aggressive', 'personality_b': 'collaborative'}, headers=oh).get_json()['id']
    assert c.post('/api/account/delete', json={'confirm_username': username, 'password': 'Passw0rd!'}).status_code == 403          # CSRF
    assert c.post('/api/account/delete', json={'confirm_username': 'nope', 'password': 'Passw0rd!'}, headers=h).status_code == 400
    assert c.post('/api/account/delete', json={'confirm_username': username, 'password': 'wrong'}, headers=h).status_code == 403
    assert c.post('/api/account/delete', json={'confirm_username': username, 'password': 'Passw0rd!'}, headers=h).status_code == 200
    assert c.get('/api/negotiations').status_code == 401                                   # session ended
    assert app.test_client().post('/api/auth/login', json={'email': email, 'password': 'Passw0rd!'}).status_code == 401
    with auth_db.connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM users WHERE email=?', (email,)).fetchone()[0] == 0
        assert conn.execute('SELECT COUNT(*) FROM outbox WHERE to_email=?', (email,)).fetchone()[0] == 0
    from engine import negotiation_engine as engine
    assert engine.get_negotiation(nid) is None and engine.get_negotiation(keep) is not None
    assert other.get(f'/api/negotiations/{keep}').status_code == 200


def test_deletion_of_a_social_only_account_and_with_two_factor():
    email = f'del{next(_n)}@example.com'
    c, _ = google_signup(email, 'del-sub')
    h = csrf_of(c)
    name = c.get('/api/account').get_json()['username']
    secret, _ = enable_2fa(c, h)
    assert c.post('/api/account/delete', json={'confirm_username': name}, headers=h).status_code == 403          # needs the 2FA code
    with at_step(9):
        assert c.post('/api/account/delete', json={'confirm_username': name, 'code': code(secret, 9)}, headers=h).status_code == 200
    with auth_db.connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM oauth_identities WHERE provider_user_id=?', ('del-sub',)).fetchone()[0] == 0


# ───────────────────────── upgrading an existing database ─────────────────────────
def test_existing_database_is_upgraded_in_place_without_losing_accounts():
    path = os.path.join(tempfile.mkdtemp(), 'old.db')
    old = sqlite3.connect(path)
    old.executescript("""CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL, email_verified INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
        failed_logins INTEGER NOT NULL DEFAULT 0, locked_until TEXT);
        INSERT INTO users VALUES ('u1','olduser','old@example.com','x',1,'2026-01-01',0,NULL);""")
    old.commit(); old.close()
    with mock.patch.object(auth_db, 'DB_PATH', path):
        auth_db.init(); auth_db.init()                                   # idempotent
        with auth_db.connect() as conn:
            cols = {r['name'] for r in conn.execute('PRAGMA table_info(users)')}
            assert {'totp_secret', 'totp_enabled', 'totp_last_step'} <= cols
            assert conn.execute("SELECT username, totp_enabled FROM users").fetchone()[:] == ('olduser', 0)
            assert conn.execute('SELECT COUNT(*) FROM oauth_identities').fetchone()[0] == 0

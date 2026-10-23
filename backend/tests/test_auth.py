"""Registration, email verification, login/lockout, sessions, CSRF, password
reset, per-user ownership, and gamification — exercised through the real
Flask app and the local SQLite-backed accounts store (no network required;
emails are captured by the Dev Outbox since no SMTP is configured in tests)."""
import itertools
import os
import re
from unittest import mock

from app import app
from auth import db as auth_db, mailer, service as auth

auth_db.reset_for_tests()
_seq = itertools.count()


def uniq():
    n = next(_seq)
    return f'user{n}', f'user{n}@example.com'


def token_for(email, kind='verification'):
    body = next(e['body'] for e in mailer.outbox_list(200) if e['to_email'] == email)
    return re.search(rf'code on the {kind} page:\s*\n(\S+)', body).group(1)


def register_and_verify(client, username=None, email=None, password='Passw0rd!'):
    username, email = username or uniq()[0], email or f'{username or uniq()[0]}@example.com'
    r = client.post('/api/auth/register', json={'username': username, 'email': email, 'password': password})
    assert r.status_code == 201, r.get_json()
    client.get(f'/api/auth/verify-email?token={token_for(email)}')
    return username, email, password


def login(client, username, password):
    return client.post('/api/auth/login', json={'username': username, 'password': password})


def logged_in_client():
    c = app.test_client()
    u, e = uniq()
    username, email, pw = register_and_verify(c, u, e)
    r = login(c, username, pw)
    assert r.status_code == 200, r.get_json()
    return c, r.get_json()['csrf_token'], r.get_json()['user']


def auth_headers(csrf):
    return {'X-CSRF-Token': csrf}


# ─────────────────────────── registration & validation ───────────────────────────
def test_registration_validates_username_email_and_password():
    c = app.test_client()
    u, e = uniq()
    bad = [
        {'username': 'ab', 'email': e, 'password': 'Passw0rd!'},          # too short
        {'username': u, 'email': 'not-an-email', 'password': 'Passw0rd!'},
        {'username': u, 'email': e, 'password': 'short1'},                # too short
        {'username': u, 'email': e, 'password': 'alletters'},             # no digit
        {'username': u, 'email': e, 'password': '12345678'},              # no letter
    ]
    for body in bad:
        r = c.post('/api/auth/register', json=body)
        assert r.status_code == 400, body


def test_duplicate_username_and_email_are_rejected():
    c = app.test_client()
    u, e = uniq()
    assert c.post('/api/auth/register', json={'username': u, 'email': e, 'password': 'Passw0rd!'}).status_code == 201
    u2, _ = uniq()
    assert c.post('/api/auth/register', json={'username': u, 'email': f'{u2}@example.com', 'password': 'Passw0rd!'}).status_code == 400
    assert c.post('/api/auth/register', json={'username': u2, 'email': e, 'password': 'Passw0rd!'}).status_code == 400


def test_login_blocked_until_email_verified_then_works_after_verification():
    c = app.test_client()
    u, e = uniq()
    c.post('/api/auth/register', json={'username': u, 'email': e, 'password': 'Passw0rd!'})
    r = login(c, u, 'Passw0rd!')
    assert r.status_code == 403 and 'verify' in r.get_json()['error'].lower()
    c.get(f'/api/auth/verify-email?token={token_for(e)}')
    ok = login(c, u, 'Passw0rd!')
    assert ok.status_code == 200 and ok.get_json()['user']['username'] == u


def test_password_reset_via_dev_outbox():
    c = app.test_client()
    u, e, pw = register_and_verify(c)
    c.post('/api/auth/request-password-reset', json={'email': e})
    token = token_for(e, 'reset')
    r = c.post('/api/auth/reset-password', json={'token': token, 'password': 'NewPass1!'})
    assert r.status_code == 200
    assert login(app.test_client(), u, pw).status_code == 401          # old password no longer works
    assert login(app.test_client(), u, 'NewPass1!').status_code == 200  # new one does
    assert c.post('/api/auth/reset-password', json={'token': token, 'password': 'AnotherOne1!'}).status_code == 400  # one-time use


def test_password_reset_request_does_not_reveal_whether_email_exists():
    c = app.test_client()
    r1 = c.post('/api/auth/request-password-reset', json={'email': 'nobody-here@example.com'})
    r2 = c.post('/api/auth/request-password-reset', json={'email': uniq()[1]})
    assert r1.status_code == 200 and r2.status_code == 200 and r1.get_json() == r2.get_json()


def test_login_lockout_after_repeated_failures():
    c = app.test_client()
    u, e, pw = register_and_verify(c)
    for _ in range(4):
        assert login(c, u, 'WrongPass1!').status_code == 401
    locked = login(c, u, 'WrongPass1!')
    assert locked.status_code == 429 and 'locked' in locked.get_json()['error'].lower()
    assert login(c, u, pw).status_code == 429   # even the correct password is blocked while locked


# ─────────────────────────── sessions, CSRF, protected routes ───────────────────────────
def test_protected_routes_require_login():
    c = app.test_client()
    assert c.get('/api/negotiations').status_code == 401
    assert c.post('/api/negotiations', json={}).status_code == 401
    assert c.get('/api/dashboard').status_code == 401
    assert c.get('/api/me/profile').status_code == 401


def test_me_endpoint_reports_auth_state_without_401():
    c = app.test_client()
    assert c.get('/api/auth/me').get_json() == {'authenticated': False}
    c2, csrf, user = logged_in_client()
    me = c2.get('/api/auth/me').get_json()
    assert me['authenticated'] and me['user']['username'] == user['username'] and me['csrf_token'] == csrf


def test_csrf_required_and_enforced_on_mutating_requests():
    c, csrf, _ = logged_in_client()
    body = {'scenario_id': 'vendor_pricing', 'personality_a': 'aggressive', 'personality_b': 'collaborative'}
    assert c.post('/api/negotiations', json=body).status_code == 403               # missing token
    assert c.post('/api/negotiations', json=body, headers={'X-CSRF-Token': 'wrong'}).status_code == 403
    ok = c.post('/api/negotiations', json=body, headers=auth_headers(csrf))
    assert ok.status_code == 201


def test_logout_ends_the_session():
    c, csrf, _ = logged_in_client()
    assert c.get('/api/negotiations').status_code == 200
    assert c.post('/api/auth/logout').status_code == 200
    assert c.get('/api/negotiations').status_code == 401


# ─────────────────────────── per-user ownership ───────────────────────────
def _create(client, csrf, **over):
    body = {'scenario_id': 'vendor_pricing', 'personality_a': 'aggressive', 'personality_b': 'collaborative'}
    body.update(over)
    return client.post('/api/negotiations', json=body, headers=auth_headers(csrf)).get_json()['id']


def test_users_cannot_access_or_act_on_each_others_negotiations():
    a, csrf_a, _ = logged_in_client()
    b, csrf_b, _ = logged_in_client()
    nid = _create(a, csrf_a)
    assert b.get(f'/api/negotiations/{nid}').status_code == 404
    assert b.post(f'/api/negotiations/{nid}/step', headers=auth_headers(csrf_b)).status_code == 404
    assert b.post(f'/api/negotiations/{nid}/human-action', json={'action': 'open', 'value': 33}, headers=auth_headers(csrf_b)).status_code == 404
    assert b.get(f'/api/negotiations/{nid}/report').status_code == 404
    assert b.get(f'/api/negotiations/{nid}/transcript').status_code == 404
    assert b.get(f'/api/negotiations/{nid}/certificate').status_code == 404
    assert a.get(f'/api/negotiations/{nid}').status_code == 200


def test_history_only_returns_the_callers_own_sessions():
    a, csrf_a, _ = logged_in_client()
    b, csrf_b, _ = logged_in_client()
    nid_a = _create(a, csrf_a)
    _create(b, csrf_b)
    hist_a = a.get('/api/negotiations').get_json()
    assert {x['id'] for x in hist_a} == {nid_a}


# ─────────────────────────── dev outbox visibility ───────────────────────────
def test_dev_outbox_disabled_once_smtp_is_configured():
    c = app.test_client()
    assert c.get('/api/auth/dev-outbox').status_code == 200
    with mock.patch.dict(os.environ, {'SMTP_HOST': 'smtp.example.com', 'SMTP_USER': 'a@b.com', 'SMTP_PASS': 'x'}):
        assert c.get('/api/auth/dev-outbox').status_code == 404


# ─────────────────────────── gamification ───────────────────────────
def test_gamification_only_counts_practice_mode_and_matches_recorded_outcomes():
    c, csrf, user = logged_in_client()
    sim_id = _create(c, csrf, workflow_mode='simulation')
    c.post(f'/api/negotiations/{sim_id}/run', headers=auth_headers(csrf))
    prof = c.get('/api/me/profile').get_json()['gamification']
    assert prof['completed'] == 0 and prof['average_score'] is None and not prof['badges']

    prac_id = _create(c, csrf, workflow_mode='practice', personality_b='collaborative')
    c.post(f'/api/negotiations/{prac_id}/human-action', json={'action': 'open', 'value': 48}, headers=auth_headers(csrf))  # buyer's own hard limit: generous, vendor accepts immediately
    r = c.get(f'/api/negotiations/{prac_id}').get_json()
    assert r['status'] == 'agreed'
    prof2 = c.get('/api/me/profile').get_json()['gamification']
    assert prof2['completed'] == 1 and prof2['agreements'] == 1
    assert any(b['id'] == 'first_agreement' for b in prof2['badges'])
    assert all(b['id'] not in [x['id'] for x in prof2['badges']] for b in prof2['locked_badges'])


def test_leaderboard_exposes_only_username_and_score_never_negotiation_ids():
    c, csrf, user = logged_in_client()
    prac_id = _create(c, csrf, workflow_mode='practice', personality_b='collaborative')
    c.post(f'/api/negotiations/{prac_id}/human-action', json={'action': 'open', 'value': 48}, headers=auth_headers(csrf))
    assert c.get(f'/api/negotiations/{prac_id}').get_json()['status'] == 'agreed'
    board = c.get('/api/leaderboard').get_json()
    assert isinstance(board, list)
    row = next((x for x in board if x['username'] == user['username']), None)
    if row:
        assert set(row) == {'username', 'average_score', 'best_score', 'completed', 'badge_count'}

"""Account security: registration, email verification, login with rate limiting,
server-side sessions, CSRF enforcement, password reset, and Google/GitHub
account linking. No plaintext passwords are ever stored — only salted hashes
(werkzeug.security). Accounts created through a social provider have no
password at all (password_hash == NO_PASSWORD)."""
import re
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from . import config, db, mailer, totp

TOKEN_TTL = {'verify': timedelta(hours=24), 'reset': timedelta(hours=1)}
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
SESSION_LIFETIME_MINUTES = 120

USERNAME_RE = re.compile(r'^[A-Za-z0-9_]{3,24}$')
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

NO_PASSWORD = ''   # password_hash of social-only accounts; never matches any password
PROVIDER_LABEL = {'google': 'Google', 'github': 'GitHub'}
INVALID_LOGIN = 'Invalid email or password.'
RESET_MESSAGE = ('If that email belongs to an account, we have sent instructions to it. '
                 'Accounts created with Google or GitHub have no password \u2014 use that sign-in option instead.')
# Used only to spend the same time hashing when the account doesn't exist.
_DUMMY_HASH = generate_password_hash('timing-equaliser-not-a-real-password')


class AuthError(ValueError):
    def __init__(self, message, status=400, code=None):
        super().__init__(message)
        self.status = status
        self.code = code


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat()


def _parse(s):
    return datetime.fromisoformat(s) if s else None


def validate_password(pw):
    if not pw or len(pw) < 8:
        raise AuthError('Password must be at least 8 characters.')
    if not re.search(r'[A-Za-z]', pw) or not re.search(r'[0-9]', pw):
        raise AuthError('Password must include at least one letter and one number.')


# ────────────────────────────  registration & verification  ────────────────────────────
def register(username, email, password):
    username = (username or '').strip()
    email = (email or '').strip().lower()
    if not USERNAME_RE.match(username):
        raise AuthError('Username must be 3-24 characters: letters, numbers or underscore.')
    if not EMAIL_RE.match(email):
        raise AuthError('Enter a valid email address.')
    validate_password(password)
    if not mailer.can_send():
        raise AuthError('Email sign-up is temporarily unavailable. Please continue with Google or GitHub.', 503)
    uid = secrets.token_hex(8)
    with db.LOCK, db.connect() as conn:
        if conn.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone():
            raise AuthError('That username is already taken.')
        if conn.execute('SELECT 1 FROM users WHERE email=?', (email,)).fetchone():
            raise AuthError('An account with that email already exists.')
        conn.execute('INSERT INTO users (id,username,email,password_hash,email_verified,created_at,failed_logins)'
                     ' VALUES (?,?,?,?,0,?,0)', (uid, username, email, generate_password_hash(password), _iso(_now())))
        conn.commit()
    send_verification_email(uid, email)
    return {'id': uid, 'username': username, 'email': email}


def _issue_token(user_id, kind):
    token = secrets.token_urlsafe(32)
    with db.LOCK, db.connect() as conn:
        conn.execute('INSERT INTO tokens (token,user_id,kind,expires_at,used) VALUES (?,?,?,?,0)',
                     (token, user_id, kind, _iso(_now() + TOKEN_TTL[kind])))
        conn.commit()
    return token


def send_verification_email(user_id, email):
    token = _issue_token(user_id, 'verify')
    link = f"{config.base_url()}/verify-email.html?token={token}"
    body = (f'Welcome to the AI Multi-Agent Negotiation Platform!\n\n'
            f'Verify your email by opening this link:\n{link}\n\n'
            f'Or paste this code on the verification page:\n{token}\n\n'
            f'This link expires in 24 hours. If you did not create this account, ignore this email.')
    return mailer.send(email, 'Verify your account', body)


def verify_email(token):
    token = (token or '').strip()
    with db.LOCK, db.connect() as conn:
        row = conn.execute('SELECT * FROM tokens WHERE token=? AND kind="verify"', (token,)).fetchone()
        if not row or row['used'] or _parse(row['expires_at']) < _now():
            raise AuthError('This verification link is invalid or has expired.')
        conn.execute('UPDATE tokens SET used=1 WHERE token=?', (token,))
        conn.execute('UPDATE users SET email_verified=1 WHERE id=?', (row['user_id'],))
        conn.commit()
        u = conn.execute('SELECT username FROM users WHERE id=?', (row['user_id'],)).fetchone()
    return u['username']


def resend_verification(email):
    email = (email or '').strip().lower()
    with db.connect() as conn:
        u = conn.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
    if u and not u['email_verified']:
        send_verification_email(u['id'], u['email'])
    # Same response whether or not the account exists — avoids confirming an email is registered.


# ────────────────────────────  login / session / CSRF  ────────────────────────────
def _join(names):
    return ' or '.join(names)


def linked_providers(conn, user_id):
    rows = conn.execute('SELECT provider FROM oauth_identities WHERE user_id=? ORDER BY created_at', (user_id,)).fetchall()
    return [PROVIDER_LABEL.get(r['provider'], r['provider']) for r in rows]


def _find_login_user(conn, identifier):
    """Email is the primary login. A bare username is still accepted so that
    existing clients and accounts keep working (usernames can't contain '@')."""
    identifier = (identifier or '').strip()
    if '@' in identifier:
        return conn.execute('SELECT * FROM users WHERE email=?', (identifier.lower(),)).fetchone()
    return conn.execute('SELECT * FROM users WHERE username=?', (identifier,)).fetchone()


def _start_session(u):
    """Single place that creates the application session, used by password login
    and by Google/GitHub sign-in alike. Returns the new CSRF token."""
    session.clear()           # also prevents session fixation
    session.permanent = True
    session['user_id'], session['username'] = u['id'], u['username']
    session['csrf'] = secrets.token_urlsafe(24)
    session['last_active'] = _iso(_now())
    return session['csrf']


def login(identifier, password):
    identifier = identifier if isinstance(identifier, str) else ''
    password = password if isinstance(password, str) else ''
    with db.LOCK, db.connect() as conn:
        u = _find_login_user(conn, identifier)
        if not u:
            check_password_hash(_DUMMY_HASH, password)
            raise AuthError(INVALID_LOGIN, 401)
        if u['password_hash'] == NO_PASSWORD:
            providers = linked_providers(conn, u['id'])
            if providers:
                names = _join(providers)
                raise AuthError(f'This account was created using {names}. Please continue with {names}.', 400, 'use_social')
            raise AuthError(INVALID_LOGIN, 401)
        locked_until = _parse(u['locked_until'])
        if locked_until and locked_until > _now():
            mins = max(1, int((locked_until - _now()).total_seconds() // 60) + 1)
            raise AuthError(f'Too many failed attempts. Try again in {mins} minute(s).', 429)
        if not check_password_hash(u['password_hash'], password):
            failed = u['failed_logins'] + 1
            new_lock = _iso(_now() + timedelta(minutes=LOCKOUT_MINUTES)) if failed >= MAX_FAILED_LOGINS else None
            conn.execute('UPDATE users SET failed_logins=?, locked_until=? WHERE id=?', (failed, new_lock, u['id']))
            conn.commit()
            if new_lock:
                raise AuthError(f'Too many failed attempts. Account locked for {LOCKOUT_MINUTES} minutes.', 429)
            raise AuthError(INVALID_LOGIN, 401)
        if not u['email_verified']:
            raise AuthError('Please verify your email before signing in.', 403)
        if not u['totp_enabled']:
            # With two-factor on, the counter is cleared only after the second factor succeeds
            # (check_second_factor). Otherwise a correct password would keep resetting the
            # lockout and allow unlimited guessing of the code.
            conn.execute('UPDATE users SET failed_logins=0, locked_until=NULL WHERE id=?', (u['id'],))
            conn.commit()
    return _finish_login(u)


def _finish_login(u):
    """Returns (user, csrf). With two-factor enabled no session is created yet:
    the browser only gets a short-lived 'pending' marker and (None, None) comes
    back, meaning "ask for the code" (see verify_mfa)."""
    if u['totp_enabled']:
        session.clear()
        session['mfa_user'] = u['id']
        session['mfa_exp'] = _iso(_now() + timedelta(minutes=5))
        return None, None
    csrf = _start_session(u)
    return {'id': u['id'], 'username': u['username'], 'email': u['email']}, csrf


def check_second_factor(conn, u, code):
    """True if `code` is a valid authenticator code (each time-step usable once) or an
    unused recovery code (consumed on use). Wrong codes count toward the same lockout
    as wrong passwords, and that counter lives in the database, so discarding the
    cookie doesn't reset it."""
    locked_until = _parse(u['locked_until'])
    if locked_until and locked_until > _now():
        raise AuthError('Too many failed attempts. Try again later.', 429)
    ok = False
    step = totp.verify(u['totp_secret'] or '', code, u['totp_last_step'] or 0) if u['totp_secret'] else None
    if step is not None:
        conn.execute('UPDATE users SET totp_last_step=? WHERE id=?', (step, u['id']))
        ok = True
    elif code and conn.execute('UPDATE recovery_codes SET used=1 WHERE user_id=? AND code_hash=? AND used=0',
                               (u['id'], totp.hash_recovery(code))).rowcount == 1:
        ok = True
    if ok:
        conn.execute('UPDATE users SET failed_logins=0, locked_until=NULL WHERE id=?', (u['id'],))
    else:
        failed = u['failed_logins'] + 1
        lock = _iso(_now() + timedelta(minutes=LOCKOUT_MINUTES)) if failed >= MAX_FAILED_LOGINS else None
        conn.execute('UPDATE users SET failed_logins=?, locked_until=? WHERE id=?', (failed, lock, u['id']))
    conn.commit()
    return ok


def verify_mfa(code):
    uid, exp = session.get('mfa_user'), _parse(session.get('mfa_exp'))
    if not uid or not exp or exp < _now():
        session.clear()
        raise AuthError('Your sign-in session expired. Please sign in again.', 401)
    with db.LOCK, db.connect() as conn:
        u = conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
        if not u or not u['totp_enabled']:
            session.clear()
            raise AuthError('Your sign-in session expired. Please sign in again.', 401)
        if not check_second_factor(conn, u, code if isinstance(code, str) else ''):
            raise AuthError('Invalid code. Please try again.', 401)
    csrf = _start_session(u)
    return {'id': u['id'], 'username': u['username'], 'email': u['email']}, csrf


# ────────────────────────────  Google / GitHub sign-in  ────────────────────────────
def _unique_username(conn, hint, email):
    """Usernames still drive profiles/leaderboards, so social sign-ups get one
    derived from the provider's display/login name (never the full email)."""
    def clean(text):
        return re.sub(r'[^A-Za-z0-9_]', '', text or '')
    base = clean((hint or '').strip().split(' ')[0]) or clean(email.split('@')[0]) or 'user'
    base = base[:18]
    if len(base) < 3:
        base = (base + 'user')[:18]
    candidate = base
    for _ in range(25):
        if not conn.execute('SELECT 1 FROM users WHERE lower(username)=lower(?)', (candidate,)).fetchone():
            return candidate
        candidate = f'{base}{secrets.randbelow(9000) + 1000}'
    return f'user{secrets.token_hex(6)}'


def oauth_login(provider, subject, email, email_verified, name_hint=None):
    """Sign in (or sign up) with an identity the provider has already authenticated.

    1. A known (provider, subject) pair signs straight in — the subject is the
       provider's stable id, so a changed email address can't hijack anything.
    2. Otherwise the provider's email must be *verified by the provider*. If it
       matches an existing account, the identity is linked to it instead of
       creating a duplicate. This is safe because both sides have proven they
       control that mailbox.
    3. If the matching local account never verified its email, whoever
       registered it never proved they own the address (it may be someone
       squatting on it). The provider has now proven ownership, so we keep the
       account but wipe its password and outstanding tokens: the squatter loses
       access, the real owner gains it.
    4. No match -> a new, already-verified, password-less account is created.
    """
    if provider not in PROVIDER_LABEL:
        raise AuthError('Unable to complete sign-in. Please try again.', 400)
    subject = str(subject or '').strip()
    email = (email or '').strip().lower()
    if not subject:
        raise AuthError('Unable to complete sign-in. Please try again.', 400)
    if not email_verified or not EMAIL_RE.match(email):
        raise AuthError(f'{PROVIDER_LABEL[provider]} did not return a verified email address, so we could not sign you in with it.',
                        400, 'email_unverified')
    now = _iso(_now())
    with db.LOCK, db.connect() as conn:
        u = conn.execute('SELECT u.* FROM oauth_identities i JOIN users u ON u.id=i.user_id '
                         'WHERE i.provider=? AND i.provider_user_id=?', (provider, subject)).fetchone()
        if u is None:
            u = conn.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
            if u is not None and not u['email_verified']:
                conn.execute('UPDATE users SET password_hash=?, email_verified=1, failed_logins=0, locked_until=NULL WHERE id=?',
                             (NO_PASSWORD, u['id']))
                conn.execute('DELETE FROM tokens WHERE user_id=?', (u['id'],))
            if u is None:
                uid = secrets.token_hex(8)
                conn.execute('INSERT INTO users (id,username,email,password_hash,email_verified,created_at,failed_logins)'
                             ' VALUES (?,?,?,?,1,?,0)', (uid, _unique_username(conn, name_hint, email), email, NO_PASSWORD, now))
                u = conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
            conn.execute('INSERT INTO oauth_identities (provider,provider_user_id,user_id,email,created_at) VALUES (?,?,?,?,?)',
                         (provider, subject, u['id'], email, now))
            conn.commit()
            u = conn.execute('SELECT * FROM users WHERE id=?', (u['id'],)).fetchone()
    return _finish_login(u)


def logout():
    session.clear()


def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    last = _parse(session.get('last_active'))
    if last and _now() - last > timedelta(minutes=SESSION_LIFETIME_MINUTES):
        session.clear()
        return None
    session['last_active'] = _iso(_now())
    with db.connect() as conn:
        u = conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
    if not u:
        session.clear()
        return None
    return {'id': u['id'], 'username': u['username'], 'email': u['email'], 'email_verified': bool(u['email_verified'])}


def require_login(fn):
    @wraps(fn)
    def wrapper(*a, **k):
        u = current_user()
        if not u:
            return jsonify({'error': 'Please log in to continue.'}), 401
        g.user = u
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            token = request.headers.get('X-CSRF-Token')
            if not token or token != session.get('csrf'):
                return jsonify({'error': 'Invalid or missing CSRF token. Please reload and try again.'}), 403
        return fn(*a, **k)
    return wrapper


# ────────────────────────────  password reset  ────────────────────────────
def request_password_reset(email):
    """Always returns normally, so the caller can give the same answer whether or
    not the address belongs to an account. Password accounts get a reset link;
    accounts that only use Google/GitHub get an email explaining that there is
    no password to reset and where to sign in instead."""
    email = (email or '').strip().lower()
    with db.connect() as conn:
        u = conn.execute('SELECT * FROM users WHERE email=?', (email,)).fetchone()
        providers = linked_providers(conn, u['id']) if u and u['password_hash'] == NO_PASSWORD else []
    if not u:
        return
    if u['password_hash'] != NO_PASSWORD:
        token = _issue_token(u['id'], 'reset')
        link = f"{config.base_url()}/reset-password.html?token={token}"
        body = (f'Reset your password using this link (valid for 1 hour):\n{link}\n\n'
                f'Or paste this code on the reset page:\n{token}\n\n'
                f'If you did not request this, you can safely ignore this email.')
        mailer.send(u['email'], 'Reset your password', body)
    elif providers:
        names = _join(providers)
        body = (f'Someone asked to reset the password for this account.\n\n'
                f'This account was created using {names} and has no password, so there is nothing to reset. '
                f'To sign in, open {config.base_url()}/login.html and choose "Continue with {names}".\n\n'
                f'If you did not request this, you can safely ignore this email.')
        mailer.send(u['email'], 'Signing in to your account', body)
    # Same response whether or not the account exists.


def reset_password(token, new_password):
    validate_password(new_password)
    token = (token or '').strip()
    with db.LOCK, db.connect() as conn:
        row = conn.execute('SELECT * FROM tokens WHERE token=? AND kind="reset"', (token,)).fetchone()
        if not row or row['used'] or _parse(row['expires_at']) < _now():
            raise AuthError('This reset link is invalid or has expired.')
        conn.execute('UPDATE tokens SET used=1 WHERE token=?', (token,))
        conn.execute('UPDATE users SET password_hash=?, failed_logins=0, locked_until=NULL WHERE id=?',
                     (generate_password_hash(new_password), row['user_id']))
        conn.commit()

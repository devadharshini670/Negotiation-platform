"""Account management for a signed-in user: username, password, connected sign-in
methods, two-factor authentication, data export and account deletion.

Rule of thumb throughout: an account must always keep at least one way to sign in
(a password or a linked Google/GitHub identity), and destructive actions re-check
who is asking (password and/or two-factor code) instead of trusting the session alone."""
from flask import session
from werkzeug.security import check_password_hash, generate_password_hash

from . import db, service, totp
from .service import AuthError, NO_PASSWORD, PROVIDER_LABEL, USERNAME_RE


def _user(conn, user_id):
    u = conn.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if not u:
        raise AuthError('Please log in to continue.', 401)
    return u


def _identities(conn, user_id):
    rows = conn.execute('SELECT provider, email, created_at FROM oauth_identities WHERE user_id=? ORDER BY created_at', (user_id,)).fetchall()
    return [{'provider': r['provider'], 'label': PROVIDER_LABEL.get(r['provider'], r['provider']),
             'email': r['email'], 'linked_at': r['created_at']} for r in rows]


def overview(user_id):
    with db.connect() as conn:
        u = _user(conn, user_id)
        left = conn.execute('SELECT COUNT(*) FROM recovery_codes WHERE user_id=? AND used=0', (user_id,)).fetchone()[0]
        return {'username': u['username'], 'email': u['email'], 'created_at': u['created_at'],
                'has_password': u['password_hash'] != NO_PASSWORD, 'identities': _identities(conn, user_id),
                'two_factor': {'enabled': bool(u['totp_enabled']), 'recovery_codes_left': left}}


def change_username(user_id, new_name):
    new_name = (new_name or '').strip() if isinstance(new_name, str) else ''
    if not USERNAME_RE.match(new_name):
        raise AuthError('Username must be 3-24 characters: letters, numbers or underscore.')
    with db.LOCK, db.connect() as conn:
        _user(conn, user_id)
        if conn.execute('SELECT 1 FROM users WHERE lower(username)=lower(?) AND id<>?', (new_name, user_id)).fetchone():
            raise AuthError('That username is already taken.')
        conn.execute('UPDATE users SET username=? WHERE id=?', (new_name, user_id))
        conn.commit()
    session['username'] = new_name
    return new_name


def set_password(user_id, current, new):
    """Change the password, or create one for an account that signed up with Google/GitHub."""
    service.validate_password(new)
    with db.LOCK, db.connect() as conn:
        u = _user(conn, user_id)
        if u['password_hash'] != NO_PASSWORD and not (isinstance(current, str) and check_password_hash(u['password_hash'], current)):
            raise AuthError('Your current password is incorrect.', 403)
        conn.execute('UPDATE users SET password_hash=? WHERE id=?', (generate_password_hash(new), user_id))
        conn.execute("DELETE FROM tokens WHERE user_id=? AND kind='reset'", (user_id,))
        conn.commit()


def unlink(user_id, provider):
    with db.LOCK, db.connect() as conn:
        u = _user(conn, user_id)
        linked = _identities(conn, user_id)
        if provider not in [i['provider'] for i in linked]:
            raise AuthError('That sign-in method is not connected to your account.', 404)
        if u['password_hash'] == NO_PASSWORD and len(linked) <= 1:
            raise AuthError('Set a password first. Otherwise you would be locked out of your account.', 409)
        conn.execute('DELETE FROM oauth_identities WHERE user_id=? AND provider=?', (user_id, provider))
        conn.commit()


# ────────────────────────────  two-factor authentication  ────────────────────────────
def two_factor_setup(user_id):
    with db.LOCK, db.connect() as conn:
        u = _user(conn, user_id)
        if u['totp_enabled']:
            raise AuthError('Two-factor authentication is already on.', 409)
        secret = totp.new_secret()
        conn.execute('UPDATE users SET totp_secret=?, totp_last_step=0 WHERE id=?', (secret, user_id))
        conn.commit()
        uri = totp.provisioning_uri(secret, u['email'])
    return {'secret': secret, 'uri': uri, 'qr_svg': totp.qr_svg(uri)}


def two_factor_enable(user_id, code):
    with db.LOCK, db.connect() as conn:
        u = _user(conn, user_id)
        if u['totp_enabled'] or not u['totp_secret']:
            raise AuthError('Start the two-factor setup first.', 409)
        step = totp.verify(u['totp_secret'], code if isinstance(code, str) else '')
        if step is None:
            raise AuthError('That code is not correct. Check your authenticator app and try again.', 400)
        codes = totp.new_recovery_codes()
        conn.execute('DELETE FROM recovery_codes WHERE user_id=?', (user_id,))
        conn.executemany('INSERT INTO recovery_codes (user_id, code_hash, used) VALUES (?,?,0)',
                         [(user_id, totp.hash_recovery(c)) for c in codes])
        conn.execute('UPDATE users SET totp_enabled=1, totp_last_step=? WHERE id=?', (step, user_id))
        conn.commit()
    return codes


def two_factor_disable(user_id, code):
    with db.LOCK, db.connect() as conn:
        u = _user(conn, user_id)
        if not u['totp_enabled']:
            raise AuthError('Two-factor authentication is not on.', 409)
        if not service.check_second_factor(conn, u, code if isinstance(code, str) else ''):
            raise AuthError('That code is not correct.', 403)
        conn.execute('UPDATE users SET totp_enabled=0, totp_secret=NULL, totp_last_step=0 WHERE id=?', (user_id,))
        conn.execute('DELETE FROM recovery_codes WHERE user_id=?', (user_id,))
        conn.commit()


# ────────────────────────────  export & deletion  ────────────────────────────
def export_profile(user_id):
    info = overview(user_id)
    return {'username': info['username'], 'email': info['email'], 'created_at': info['created_at'],
            'sign_in_methods': (['password'] if info['has_password'] else []) + [i['provider'] for i in info['identities']],
            'two_factor_enabled': info['two_factor']['enabled']}


def delete_account(user_id, confirm_username, password, code):
    """Permanently removes the account. Requires typing the username, plus the password
    (if the account has one) and a two-factor code (if enabled)."""
    with db.LOCK, db.connect() as conn:
        u = _user(conn, user_id)
        if confirm_username != u['username']:
            raise AuthError('Type your username exactly to confirm.', 400)
        if u['password_hash'] != NO_PASSWORD and not (isinstance(password, str) and check_password_hash(u['password_hash'], password)):
            raise AuthError('Your password is incorrect.', 403)
        if u['totp_enabled'] and not service.check_second_factor(conn, u, code if isinstance(code, str) else ''):
            raise AuthError('That two-factor code is not correct.', 403)
        for table in ('oauth_identities', 'tokens', 'recovery_codes'):
            conn.execute(f'DELETE FROM {table} WHERE user_id=?', (user_id,))
        conn.execute('DELETE FROM outbox WHERE to_email=?', (u['email'],))
        conn.execute('DELETE FROM users WHERE id=?', (user_id,))
        conn.commit()
    session.clear()

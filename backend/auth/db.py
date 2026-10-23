"""Tiny SQLite persistence for accounts, OAuth identities, tokens and the dev mail outbox.
Negotiation sessions themselves stay in-memory (see engine/negotiation_engine.py)
but accounts must survive a server restart, so they live here instead."""
import os
import sqlite3
import threading

# AUTH_DB_PATH lets the test suite use a throw-away database instead of the real one.
DB_PATH = os.getenv('AUTH_DB_PATH') or os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'app.db')
LOCK = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,          -- '' = no password (account created through Google/GitHub)
  email_verified INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  failed_logins INTEGER NOT NULL DEFAULT 0,
  locked_until TEXT
);
CREATE TABLE IF NOT EXISTS tokens (
  token TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  used INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS oauth_identities (
  provider TEXT NOT NULL,
  provider_user_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  email TEXT,
  created_at TEXT NOT NULL,
  PRIMARY KEY (provider, provider_user_id)
);
CREATE INDEX IF NOT EXISTS idx_oauth_identities_user ON oauth_identities(user_id);
CREATE TABLE IF NOT EXISTS recovery_codes (
  user_id TEXT NOT NULL,
  code_hash TEXT NOT NULL,
  used INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, code_hash)
);
CREATE TABLE IF NOT EXISTS outbox (
  id TEXT PRIMARY KEY,
  to_email TEXT NOT NULL,
  subject TEXT NOT NULL,
  body TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=8)
    conn.row_factory = sqlite3.Row
    return conn


# Columns added after the first release; applied to existing databases in place.
_USER_COLUMNS = (('totp_secret', 'TEXT'), ('totp_enabled', 'INTEGER NOT NULL DEFAULT 0'),
                 ('totp_last_step', 'INTEGER NOT NULL DEFAULT 0'))


def init():
    with LOCK, connect() as conn:
        conn.executescript(SCHEMA)
        have = {r['name'] for r in conn.execute('PRAGMA table_info(users)')}
        for name, ddl in _USER_COLUMNS:
            if name not in have:
                conn.execute(f'ALTER TABLE users ADD COLUMN {name} {ddl}')
        conn.commit()


def reset_for_tests():
    """Used only by the test suite to start from a clean, isolated database."""
    with LOCK:
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
    init()

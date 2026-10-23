"""Test isolation. Runs before any test module imports `app`.

* a throw-away accounts database, so the suite can never wipe real accounts;
* development mode (Dev Outbox available) with no SMTP and no OAuth credentials,
  regardless of what a developer has in their own backend/.env."""
import os
import tempfile

_tmp = tempfile.mkdtemp(prefix='negotiation-tests-')
os.environ['AUTH_DB_PATH'] = os.path.join(_tmp, 'app.db')
os.environ['APP_ENV'] = 'development'
for _key in ('SMTP_HOST', 'SMTP_USER', 'SMTP_PASS', 'APP_BASE_URL',
             'GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_REDIRECT_URI',
             'GITHUB_CLIENT_ID', 'GITHUB_CLIENT_SECRET', 'GITHUB_REDIRECT_URI'):
    os.environ[_key] = ''


# LLM tests never touch the internet or a developer's real keys: both providers point at a local fake
# server and start with no API key. (Live checks: backend/tools/check_llm.py.)
from tests import fake_llm_server   # noqa: E402

_srv, _base = fake_llm_server.start()
os.environ['GROQ_BASE_URL'] = _base + '/groq'
os.environ['GEMINI_BASE_URL'] = _base + '/gemini'
for _key in ('GROQ_API_KEY', 'GEMINI_API_KEY', 'GROQ_MODEL', 'GEMINI_MODEL'):
    os.environ[_key] = ''
os.environ['LLM_RETRY_DELAY'] = '0'
os.environ['LLM_TIMEOUT_SECONDS'] = '5'

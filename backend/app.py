import os
import secrets
from datetime import timedelta

from flask import Flask, g, jsonify, request, Response, send_from_directory, session
from dotenv import load_dotenv

load_dotenv()

# `python app.py` on a loopback address is a local development run, so it defaults to
# development mode. Every other way of starting the app (gunicorn, containers, a public
# HOST) defaults to production unless APP_ENV says otherwise.
if __name__ == '__main__' and not os.getenv('APP_ENV') and os.getenv('HOST', '127.0.0.1') in ('127.0.0.1', 'localhost', '::1'):
    os.environ['APP_ENV'] = 'development'

from models.scenarios import list_scenarios
from llm import provider as llm_provider
from llm._http import LLMError
from llm.provider import status as llm_status
from engine import negotiation_engine as engine
from assistant import memory as assistant_memory, service as assistant_service
from engine import assistant_context
from auth import account, config as auth_config, db as auth_db, mailer, oauth as auth_oauth, service as auth

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))
STATIC_EXT = {'.html', '.css', '.js', '.svg', '.png', '.ico'}

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY') or secrets.token_hex(32)
app.permanent_session_lifetime = timedelta(minutes=auth.SESSION_LIFETIME_MINUTES)
_secure_cookie = (os.getenv('SESSION_COOKIE_SECURE', '').strip().lower() in ('1', 'true', 'yes')
                  or os.getenv('APP_BASE_URL', '').strip().lower().startswith('https://'))
# Lax (not Strict) is required so the session survives the redirect back from Google/GitHub.
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=_secure_cookie)
auth_db.init()


def _startup_checks():
    if auth_config.is_dev():
        app.logger.warning('Running in DEVELOPMENT mode (APP_ENV=development).%s',
                           ' Verification/reset emails go to /dev-outbox.html.' if mailer.dev_outbox_enabled() else '')
        return
    if not mailer.configured():
        app.logger.warning('No SMTP server configured and APP_ENV is not "development": email/password sign-up is disabled '
                           '(Google/GitHub sign-in still works). For local work set APP_ENV=development in backend/.env.')
    if not os.getenv('FLASK_SECRET_KEY'):
        app.logger.warning('FLASK_SECRET_KEY is not set: sessions will not survive a restart or work across several workers.')
    if not os.getenv('APP_BASE_URL'):
        app.logger.warning('APP_BASE_URL is not set: emailed links fall back to the request Host header. Set it in production.')


_startup_checks()


@app.after_request
def cors(r):
    r.headers['Access-Control-Allow-Origin'] = '*'
    r.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    r.headers['Access-Control-Allow-Headers'] = 'Content-Type,X-CSRF-Token'
    r.headers['Access-Control-Expose-Headers'] = 'Content-Disposition'
    return r


@app.route('/api/<path:x>', methods=['OPTIONS'])
def options(x):
    return ('', 204)


def _json_body():
    d = request.get_json(silent=True)
    return d if isinstance(d, dict) else {}


def err(msg, code):
    return jsonify({'error': msg}), code


@app.errorhandler(404)
def not_found(_):
    return err('Not found', 404)


@app.errorhandler(405)
def bad_method(_):
    return err('Method not allowed', 405)


@app.errorhandler(Exception)
def unexpected(e):
    # Never leak internals or secrets to the client.
    app.logger.exception('Unhandled error')
    return err('Internal server error. Please retry.', 500)


# ─────────────────────────────  auth  ─────────────────────────────
@app.post('/api/auth/register')
def register():
    d = _json_body()
    try:
        auth.register(d.get('username'), d.get('email'), d.get('password'))
    except auth.AuthError as e:
        return err(str(e), e.status)
    return jsonify({'message': 'Account created. Check your email to verify your address before signing in.'}), 201


@app.get('/api/auth/verify-email')
def verify_email_get():
    try:
        username = auth.verify_email(request.args.get('token'))
    except auth.AuthError as e:
        return err(str(e), e.status)
    return jsonify({'message': 'Email verified. You can now sign in.', 'username': username})


@app.post('/api/auth/verify-email')
def verify_email_post():
    try:
        username = auth.verify_email(_json_body().get('token'))
    except auth.AuthError as e:
        return err(str(e), e.status)
    return jsonify({'message': 'Email verified. You can now sign in.', 'username': username})


@app.post('/api/auth/resend-verification')
def resend_verification():
    auth.resend_verification(_json_body().get('email'))
    return jsonify({'message': 'If that email is registered and unverified, a new link has been sent.'})


@app.post('/api/auth/login')
def login():
    d = _json_body()
    try:
        # `email` is the primary identifier; `username` is still accepted for older clients.
        user, csrf_token = auth.login(d.get('email') or d.get('username'), d.get('password'))
    except auth.AuthError as e:
        return err(str(e), e.status)
    if csrf_token is None:      # two-factor is on: no session until the code is verified
        return jsonify({'mfa_required': True})
    return jsonify({'user': user, 'csrf_token': csrf_token})


@app.post('/api/auth/2fa/verify')
def verify_2fa():
    try:
        user, csrf_token = auth.verify_mfa(_json_body().get('code'))
    except auth.AuthError as e:
        return err(str(e), e.status)
    return jsonify({'user': user, 'csrf_token': csrf_token})


@app.post('/api/auth/logout')
def logout():
    auth.logout()
    return jsonify({'message': 'Logged out.'})


@app.get('/api/auth/me')
def me():
    u = auth.current_user()
    if not u:
        return jsonify({'authenticated': False})
    from flask import session
    return jsonify({'authenticated': True, 'user': u, 'csrf_token': session.get('csrf')})


@app.post('/api/auth/request-password-reset')
def request_password_reset():
    auth.request_password_reset(_json_body().get('email'))
    # One answer for every address (registered or not, password or social account).
    return jsonify({'message': auth.RESET_MESSAGE})


@app.post('/api/auth/reset-password')
def reset_password():
    d = _json_body()
    try:
        auth.reset_password(d.get('token'), d.get('password'))
    except auth.AuthError as e:
        return err(str(e), e.status)
    return jsonify({'message': 'Password updated. You can now sign in.'})


@app.get('/api/auth/dev-outbox')
def dev_outbox():
    # Development only, and only while no real SMTP server is configured. In production
    # (or once SMTP is set up) this endpoint does not exist.
    if not mailer.dev_outbox_enabled():
        return err('Not found', 404)
    return jsonify({'dev_mode': True, 'emails': mailer.outbox_list()})


@app.get('/api/auth/config')
def auth_options():
    """Tells the login/register pages which sign-in options to offer. Never contains secrets;
    setup hints are only included in development mode."""
    providers = {}
    for name in auth_oauth.PROVIDERS:
        ok = auth_config.provider_configured(name)
        entry = {'enabled': ok}
        if not ok and auth_config.is_dev():
            entry['hint'] = f'Not configured: set {name.upper()}_CLIENT_ID and {name.upper()}_CLIENT_SECRET in backend/.env (see README).'
        providers[name] = entry
    return jsonify({'providers': providers, 'email_signup': mailer.can_send()})


@app.get('/api/auth/<provider>/start')
def oauth_start(provider):
    if provider not in auth_oauth.PROVIDERS:
        return err('Not found', 404)
    return auth_oauth.start(provider, request.args.get('next'))


@app.get('/api/auth/<provider>/callback')
def oauth_callback(provider):
    if provider not in auth_oauth.PROVIDERS:
        return err('Not found', 404)
    return auth_oauth.complete(provider)


# ─────────────────────────────  account settings (all require login + CSRF on writes)  ─────────────────────────────
def _account_call(fn, *args, status=200, **ok):
    try:
        result = fn(*args)
    except auth.AuthError as e:
        return err(str(e), e.status)
    return jsonify(ok or result or {'ok': True}), status


@app.get('/api/account')
@auth.require_login
def account_overview():
    return _account_call(account.overview, g.user['id'])


@app.post('/api/account/username')
@auth.require_login
def account_username():
    try:
        name = account.change_username(g.user['id'], _json_body().get('username'))
    except auth.AuthError as e:
        return err(str(e), e.status)
    engine.rename_owner(g.user['id'], name)
    return jsonify({'username': name})


@app.post('/api/account/password')
@auth.require_login
def account_password():
    d = _json_body()
    return _account_call(account.set_password, g.user['id'], d.get('current_password'), d.get('new_password'), message='Password updated.')


@app.post('/api/account/unlink')
@auth.require_login
def account_unlink():
    return _account_call(account.unlink, g.user['id'], _json_body().get('provider'), message='Sign-in method disconnected.')


@app.post('/api/account/2fa/setup')
@auth.require_login
def account_2fa_setup():
    return _account_call(account.two_factor_setup, g.user['id'])


@app.post('/api/account/2fa/enable')
@auth.require_login
def account_2fa_enable():
    try:
        codes = account.two_factor_enable(g.user['id'], _json_body().get('code'))
    except auth.AuthError as e:
        return err(str(e), e.status)
    return jsonify({'recovery_codes': codes})


@app.post('/api/account/2fa/disable')
@auth.require_login
def account_2fa_disable():
    return _account_call(account.two_factor_disable, g.user['id'], _json_body().get('code'), message='Two-factor authentication turned off.')


@app.get('/api/account/export')
@auth.require_login
def account_export():
    import json
    from datetime import datetime, timezone
    body = json.dumps({'exported_at': datetime.now(timezone.utc).isoformat(), 'account': account.export_profile(g.user['id']),
                       'gamification': engine.user_gamification(g.user['id']),
                       'negotiations': engine.export_owner_data(g.user['id'])}, indent=2, default=str)
    return _download(body, f"negotiation-account-{g.user['username']}.json", 'application/json')


@app.post('/api/account/delete')
@auth.require_login
def account_delete():
    d = _json_body()
    uid = g.user['id']
    try:
        account.delete_account(uid, d.get('confirm_username'), d.get('password'), d.get('code'))
    except auth.AuthError as e:
        return err(str(e), e.status)
    engine.delete_owner_data(uid)
    return jsonify({'message': 'Your account and its data have been deleted.'})


# ─────────────────────────────  Negotiation Assistant (explain-only; read access, no write access)  ─────────────────────────────
# The assistant receives a detached, read-only snapshot built by engine.read_only_context(); it is never
# given the negotiation object, the engine or the orchestrator. Conversation memory is keyed by
# (user, login session) and lives apart from negotiation state.
_PAGE_RE = __import__('re').compile(r'^[A-Za-z0-9._\-]{1,40}$')


def _assistant_ids():
    return g.user['id'], session.get('csrf', '')


@app.post('/api/assistant/chat')
@auth.require_login
def assistant_chat():
    d = _json_body()
    message = d.get('message')
    if not isinstance(message, str) or not message.strip():
        return err('Type a question first.', 400)
    if len(message) > assistant_service.MAX_QUESTION:
        return err(f'Please keep questions under {assistant_service.MAX_QUESTION} characters.', 400)
    uid, sid = _assistant_ids()
    if not assistant_memory.allow(uid):
        return err('You are asking very quickly - please wait a moment.', 429)
    page = d.get('page') if isinstance(d.get('page'), str) and _PAGE_RE.match(d.get('page')) else None
    context = None
    nid = d.get('negotiation_id')
    if nid:
        if not isinstance(nid, str) or not engine.owns(nid, uid):      # someone else's (or unknown) negotiation: never exposed
            return err('Negotiation not found', 404)
        context = engine.read_only_context(nid)
    setup = assistant_context.setup_context(d.get('setup')) if not context else None      # choices made before a negotiation exists
    # Provider: the open negotiation's own provider, else the one selected in the UI, else the first configured one.
    # Never silently swapped for another one - if it fails the user sees the error.
    pid = None
    if context and context.get('available'):
        pid = (engine.get_negotiation(nid).llm_provider if nid else None)
    pid = pid or (d.get('provider') if isinstance(d.get('provider'), str) else None)
    if not pid:
        ids = llm_provider.configured_ids()
        pid = ids[0] if ids else None
    if pid not in llm_provider.REGISTRY and assistant_service.faq.is_action_request(message):
        return jsonify({'reply': assistant_service.faq.REFUSAL, 'source': 'builtin', 'provider': None, 'model': None, 'notice': '', 'used_negotiation_context': False})
    if pid not in llm_provider.REGISTRY:
        return jsonify({'error': 'No AI provider is configured. Add GROQ_API_KEY or GEMINI_API_KEY to backend/.env and restart the server.', 'error_kind': 'not_configured'}), 503
    model = d.get('model') if isinstance(d.get('model'), str) and llm_provider.MODEL_RE.match(d.get('model')) else None
    try:
        out = assistant_service.reply(message, assistant_memory.history(uid, sid), context, assistant_context.platform_facts(), pid, page, setup, model)
    except LLMError as e:
        status = {'auth': 401, 'quota': 429, 'not_configured': 503}.get(e.kind, 502)
        status = 502 if status == 401 else status          # 401 would look like "you are logged out" to the browser
        return jsonify({'error': llm_provider.scrub(e), 'error_kind': e.kind, 'provider': pid}), status
    assistant_memory.append(uid, sid, 'user', message.strip())
    assistant_memory.append(uid, sid, 'assistant', out['reply'], source=out['source'], provider=out['provider'], model=out['model'])
    return jsonify({**out, 'notice': '', 'used_negotiation_context': bool(context and context.get('available'))})


@app.get('/api/assistant/history')
@auth.require_login
def assistant_history():
    return jsonify({'messages': assistant_memory.history(*_assistant_ids())})


@app.post('/api/assistant/reset')
@auth.require_login
def assistant_reset():
    assistant_memory.reset(*_assistant_ids())
    return jsonify({'ok': True})


# ─────────────────────────────  negotiations (all require login)  ─────────────────────────────
@app.get('/api/scenarios')
def scenarios():
    return jsonify(list_scenarios())


@app.get('/api/llm/status')
def llm():
    return jsonify(llm_status())


@app.post('/api/llm/test')
@auth.require_login
def llm_test():
    """One real request to the chosen provider: proves the key, model and response parsing work. Never returns a key."""
    d = _json_body()
    pid, model = d.get('provider'), d.get('model')
    if pid not in llm_provider.REGISTRY:
        return err('Choose Groq or Google Gemini.', 400)
    if model and not (isinstance(model, str) and llm_provider.MODEL_RE.match(model)):
        return err('The model name contains unsupported characters.', 400)
    if not assistant_memory.allow('llmtest:' + str(g.user['id']), limit=8):
        return err('Too many connection tests - please wait a minute.', 429)
    res = llm_provider.test_connection(pid, model or None)
    res.pop('at', None)
    return jsonify(res)


@app.get('/api/health')
def health():
    return jsonify({'status': 'ok', 'llm': llm_status()})


@app.post('/api/negotiations')
@auth.require_login
def create():
    d = _json_body()
    missing = [x for x in ('scenario_id', 'personality_a', 'personality_b') if not d.get(x)]
    if missing:
        return err('Missing fields: ' + ', '.join(missing), 400)
    try:
        max_rounds = d.get('max_rounds')
        max_rounds = int(max_rounds) if max_rounds not in (None, '') else None
        st = engine.create_negotiation(d['scenario_id'], d['personality_a'], d['personality_b'], d.get('mode', 'mock'),
                                       max_rounds, d.get('workflow_mode', 'simulation'), d.get('llm_provider'), None,
                                       owner_id=g.user['id'], owner_username=g.user['username'],
                                       allow_fallback=d.get('allow_fallback', True) is not False)
    except LLMError as e:    # the selected provider did not answer a real test request: say so, don't downgrade quietly
        return jsonify({'error': f'The selected LLM provider is not working: {llm_provider.scrub(e)}', 'error_kind': e.kind}), 502
    except (KeyError, ValueError, TypeError) as e:
        return err(str(e).strip("'\""), 400)
    return jsonify(engine.public_state(st)), 201


@app.get('/api/negotiations')
@auth.require_login
def history():
    return jsonify(engine.list_negotiations(g.user['id']))


@app.get('/api/dashboard')
@auth.require_login
def dashboard():
    return jsonify(engine.dashboard_stats())


@app.get('/api/me/profile')
@auth.require_login
def my_profile():
    return jsonify({'user': g.user, 'gamification': engine.user_gamification(g.user['id'])})


@app.get('/api/leaderboard')
@auth.require_login
def leaderboard_route():
    return jsonify(engine.leaderboard())


def _owned_or_404(i):
    """404 (not 403) on a negotiation that isn't yours — avoids confirming that
    someone else's session ID even exists."""
    if not engine.owns(i, g.user['id']):
        return err('negotiation not found', 404)
    return None


def _run(fn, *a, **k):
    try:
        return jsonify(engine.public_state(fn(*a, **k)))
    except KeyError as e:
        return err(str(e).strip("'\""), 404)
    except ValueError as e:
        return err(str(e), 409)


@app.get('/api/negotiations/<i>')
@auth.require_login
def get(i):
    guard = _owned_or_404(i)
    if guard:
        return guard
    return jsonify(engine.public_state(engine.get_negotiation(i)))


@app.post('/api/negotiations/<i>/step')
@auth.require_login
def step(i):
    guard = _owned_or_404(i)
    if guard:
        return guard
    return _run(engine.step_negotiation, i)


@app.post('/api/negotiations/<i>/run')
@auth.require_login
def run(i):
    guard = _owned_or_404(i)
    if guard:
        return guard
    return _run(engine.run_negotiation, i)


@app.post('/api/negotiations/<i>/human-action')
@auth.require_login
def human(i):
    guard = _owned_or_404(i)
    if guard:
        return guard
    d = _json_body()
    try:
        st = engine.human_action(i, d.get('action', 'counter'), d.get('value'), d.get('rationale'), d.get('message', ''))
    except KeyError as e:
        return err(str(e).strip("'\""), 404)
    except ValueError as e:
        return err(str(e), 400)
    return jsonify(engine.public_state(st))


@app.get('/api/negotiations/<i>/report')
@auth.require_login
def report(i):
    guard = _owned_or_404(i)
    if guard:
        return guard
    return jsonify(engine.build_report(i))


def _download(body, filename, mimetype):
    return Response(body, mimetype=mimetype + '; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="{filename}"'})


@app.get('/api/negotiations/<i>/transcript')
@auth.require_login
def transcript(i):
    guard = _owned_or_404(i)
    if guard:
        return guard
    body, name = engine.transcript(i)
    return _download(body, name, 'text/plain')


@app.get('/api/negotiations/<i>/certificate')
@auth.require_login
def certificate(i):
    guard = _owned_or_404(i)
    if guard:
        return guard
    st = engine.get_negotiation(i)
    if not st.is_terminal():
        return err('The certificate is available once the negotiation has ended.', 409)
    body, name = engine.certificate(i)
    return _download(body, name, 'text/html')


@app.get('/api/negotiations/<i>/report/download')
@auth.require_login
def report_download(i):
    guard = _owned_or_404(i)
    if guard:
        return guard
    fmt = request.args.get('format', 'html')
    if fmt not in ('html', 'json'):
        return err('format must be "html" or "json"', 400)
    body, name, mime = engine.report_document(i, fmt)
    return _download(body, name, mime)


# Serve the frontend from the same origin so `python app.py` runs the whole platform.
@app.get('/')
def root():
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.get('/<path:name>')
def static_files(name):
    if os.path.splitext(name)[1].lower() not in STATIC_EXT:
        return err('Not found', 404)
    if name == 'dev-outbox.html' and not mailer.dev_outbox_enabled():
        return err('Not found', 404)
    return send_from_directory(FRONTEND_DIR, name)


if __name__ == '__main__':
    app.run(host=os.getenv('HOST', '127.0.0.1'), port=int(os.getenv('PORT', 5000)), debug=os.getenv('FLASK_DEBUG', '0') == '1')

"""HTTP helpers shared by the Groq and Gemini providers.

Every failure is converted to an :class:`LLMError` with a *kind* (auth, quota, model_not_found, ...)
and a short human-readable message. Messages are scrubbed so an API key can never reach a log,
an API response or the browser."""
import json
import os
import re
import socket
import urllib.error
import urllib.request

_SECRET_RE = re.compile(r'(gsk_|sk-ant-|sk-|AIza)[A-Za-z0-9_\-]{8,}')


def scrub(text, limit=300):
    """Remove configured secrets (and anything that looks like a provider key) from a message."""
    text = str(text)
    for var in ('GROQ_API_KEY', 'GEMINI_API_KEY'):
        secret = os.getenv(var)
        if secret and len(secret) > 6:
            text = text.replace(secret, '***')
    return _SECRET_RE.sub('***', text)[:limit]


class LLMError(RuntimeError):
    """A failed provider call. ``kind`` is one of: not_configured, auth, quota, model_not_found,
    bad_request, timeout, network, server, bad_response, truncated."""
    RETRYABLE = {'timeout', 'network', 'server'}

    def __init__(self, kind, message, status=None):
        super().__init__(scrub(message))
        self.kind, self.status = kind, status

    @property
    def retryable(self):
        return self.kind in self.RETRYABLE


def timeout():
    try:
        return float(os.getenv('LLM_TIMEOUT_SECONDS', '45'))
    except ValueError:
        return 45.0


def _error_fields(raw):
    """(message, code/status string) out of a Groq or Gemini JSON error body."""
    try:
        body = json.loads(raw)
    except Exception:
        return (raw or '').strip()[:200], ''
    e = body.get('error', body) if isinstance(body, dict) else {}
    if not isinstance(e, dict):
        return str(e)[:200], ''
    code = str(e.get('code') or e.get('status') or e.get('type') or '')
    reason = ''
    for d in e.get('details') or []:
        if isinstance(d, dict) and d.get('reason'):
            reason = str(d['reason'])
    return str(e.get('message') or '')[:240], f'{code} {reason}'.strip()


def classify(label, status, raw):
    """Map an HTTP error response to an LLMError with an actionable message."""
    msg, code = _error_fields(raw)
    low = f'{msg} {code}'.lower()
    if 'model_not_found' in low or 'model_decommissioned' in low or 'model_not_active' in low or \
            (status == 404 and 'model' in low) or ('not found for api version' in low) or \
            ('model' in low and any(w in low for w in ('decommissioned', 'no longer supported', 'does not exist', 'is not supported for generatecontent'))):
        return LLMError('model_not_found', f'{label}: the model is not available to this API key ({code or status}: {msg})', status)
    if status in (401,) or 'api_key_invalid' in low or 'api key not valid' in low or 'invalid_api_key' in low or 'invalid api key' in low:
        return LLMError('auth', f'{label}: the API key was rejected (invalid, revoked or for a different service). Check the key in backend/.env.', status)
    if status == 403 or 'permission_denied' in low:
        return LLMError('auth', f'{label}: access denied for this API key or project ({msg or "permission denied"}).', status)
    if status == 429 or 'resource_exhausted' in low or 'rate_limit' in low or 'quota' in low:
        return LLMError('quota', f'{label}: rate limit or quota exceeded - wait a moment or check your plan/quota ({msg}).', status)
    if status and status >= 500:
        return LLMError('server', f'{label}: the provider is temporarily unavailable (HTTP {status}).', status)
    return LLMError('bad_request', f'{label}: request rejected (HTTP {status}): {msg or code}', status)


def _open(req, label):
    try:
        with urllib.request.urlopen(req, timeout=timeout()) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raise classify(label, e.code, e.read().decode('utf-8', 'ignore'))
    except (socket.timeout, TimeoutError):
        raise LLMError('timeout', f'{label}: the request timed out after {timeout():g}s.')
    except urllib.error.URLError as e:
        if isinstance(e.reason, (socket.timeout, TimeoutError)):
            raise LLMError('timeout', f'{label}: the request timed out after {timeout():g}s.')
        raise LLMError('network', f'{label}: could not reach the API ({e.reason}). Check your internet connection or firewall.')
    except (ValueError, UnicodeDecodeError):
        raise LLMError('bad_response', f'{label}: the API returned a response that is not valid JSON.')


def post_json(url, body, headers, label):
    req = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), method='POST', headers={
        'Content-Type': 'application/json', 'User-Agent': 'multi-agent-negotiation-platform/2.0', **headers})
    return _open(req, label)


def get_json(url, headers, label):
    req = urllib.request.Request(url, method='GET', headers={'User-Agent': 'multi-agent-negotiation-platform/2.0', **headers})
    return _open(req, label)

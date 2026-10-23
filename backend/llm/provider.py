"""Provider registry and routing - Groq and Google Gemini only.

* The provider a negotiation / assistant request names is the provider that is used. There is no
  automatic switching: if the chosen provider is not configured or fails, the user is told.
* Keys are read from environment variables on the server and are never returned by any endpoint.
* ``test_connection`` makes one real request, so "configured" (a key exists) and "working" (a request
  succeeded) are reported separately."""
import threading
import time

from llm import groq_provider, gemini_provider
from llm._http import LLMError, scrub  # noqa: F401  (scrub is re-exported for callers)
from llm.mock_provider import decide as mock_decide

REGISTRY = {
    'groq': {'label': 'Groq', 'module': groq_provider, 'key_var': 'GROQ_API_KEY'},
    'gemini': {'label': 'Google Gemini', 'module': gemini_provider, 'key_var': 'GEMINI_API_KEY'},
}
import re
MODEL_RE = re.compile(r'^[A-Za-z0-9._:/\-]{1,80}$')

_last_test = {}              # provider id -> {'ok', 'at', 'model', 'latency_ms', 'error': {'kind','message'}}
_lock = threading.Lock()
_PREFLIGHT_TTL = 300


def valid_provider(pid):
    return pid in REGISTRY


def configured_ids():
    return [pid for pid, r in REGISTRY.items() if r['module'].available()]


def configured():
    return bool(configured_ids())


def _module(pid):
    if pid not in REGISTRY:
        raise LLMError('bad_request', f'Unknown LLM provider "{pid}". Choose Groq or Google Gemini.')
    return REGISTRY[pid]['module']


def provider_list():
    out = []
    for pid, r in REGISTRY.items():
        t = _last_test.get(pid)
        out.append({'id': pid, 'label': r['label'], 'configured': r['module'].available(), 'model': r['module'].default_model(),
                    'verified': bool(t and t['ok']), 'last_test': t})
    return out


def status():
    """Key presence + the result of the last live test. Makes no network call."""
    ids = configured_ids()
    return {'providers': provider_list(), 'default_provider': ids[0] if ids else None, 'configured': bool(ids)}


def resolve(mode, provider=None, model=None):
    """Validate an LLM request. Returns ``(effective_mode, provider_id, model, notice)``.
    Raises ValueError (clear message) instead of silently switching provider or engine."""
    if mode != 'llm':
        return 'mock', None, None, ''
    ids = configured_ids()
    notice = ''
    if not provider:
        if not ids:
            raise ValueError('Real LLM mode needs a provider. Add GROQ_API_KEY or GEMINI_API_KEY to backend/.env, restart, or choose the rule-based engine.')
        provider, notice = ids[0], f'No provider was specified, so {REGISTRY[ids[0]]["label"]} (the first configured one) is used.'
    if provider not in REGISTRY:
        raise ValueError('Unknown LLM provider. Choose Groq or Google Gemini.')
    if not REGISTRY[provider]['module'].available():
        raise ValueError(f'{REGISTRY[provider]["label"]} is selected but {REGISTRY[provider]["key_var"]} is not set on the server. '
                         f'Add it to backend/.env and restart, pick the other provider, or choose the rule-based engine.')
    if model and not MODEL_RE.match(model):
        raise ValueError('The model name contains unsupported characters.')
    return 'llm', provider, (model or None), notice


def test_connection(pid, model=None, use_cache=False):
    """Make one real API request. Never raises: returns a JSON-safe result and remembers it for status()."""
    r = REGISTRY.get(pid)
    if not r:
        return {'ok': False, 'provider': pid, 'error': {'kind': 'bad_request', 'message': 'Unknown provider. Choose Groq or Google Gemini.'}}
    base = {'provider': pid, 'label': r['label']}
    if use_cache:
        t = _last_test.get(pid)
        if t and t['ok'] and time.time() - t['at'] < _PREFLIGHT_TTL and (not model or model == t['model']):
            return {**base, **t, 'cached': True}
    t0 = time.time()
    try:
        sample, used = r['module'].ping(model)
        res = {'ok': True, 'model': used, 'latency_ms': int((time.time() - t0) * 1000), 'sample': scrub(sample, 40), 'at': time.time()}
    except LLMError as e:
        res = {'ok': False, 'model': model or None, 'latency_ms': int((time.time() - t0) * 1000), 'at': time.time(),
               'error': {'kind': e.kind, 'message': scrub(e)}}
    except Exception as e:       # defensive: never let a test endpoint crash
        res = {'ok': False, 'model': model or None, 'latency_ms': int((time.time() - t0) * 1000), 'at': time.time(),
               'error': {'kind': 'unknown', 'message': scrub(f'{type(e).__name__}: {e}')}}
    with _lock:
        _last_test[pid] = res
    return {**base, **res}


def preflight(pid, model=None):
    """Raise LLMError unless the provider answers a real request. Returns the model that worked."""
    res = test_connection(pid, model, use_cache=True)
    if not res['ok']:
        raise LLMError(res['error']['kind'], res['error']['message'])
    return res['model']


def reason(inp, mode, provider=None, model=None, repair=None):
    """One agent decision from the selected engine -> (AgentDecision, model_used).
    Raises LLMError on any real-LLM failure so the Orchestrator can retry or (if allowed) fall back visibly."""
    if mode == 'llm':
        return _module(provider).decide(inp, model, repair)
    return mock_decide(inp), None


def chat(system, messages, provider, model=None, max_tokens=700):
    """Plain-text completion from the named provider -> (text, model_used)."""
    if provider not in REGISTRY:
        raise LLMError('bad_request', 'Unknown LLM provider. Choose Groq or Google Gemini.')
    return _module(provider).chat(system, messages, model, max_tokens)


def reset_for_tests():
    from llm import models
    models.reset()
    _last_test.clear()

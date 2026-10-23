"""Model discovery shared by both providers.

Model IDs change (Groq moves models to Enterprise, Google retires Gemini versions), so no model is
trusted just because it is hard-coded. Each provider asks its own "list models" endpoint, ranks the
chat-capable results and, when the first choice answers "model not found", tries the next one.
The model that actually worked is remembered and reported to the UI - it is never hidden."""
import threading
import time

from llm._http import LLMError

TTL = 600  # seconds a model list / working-model decision is trusted
_lock = threading.Lock()
_state = {}   # provider id -> {'ids': [...], 'ids_at': ts, 'working': {model: ts}}


def _entry(pid):
    return _state.setdefault(pid, {'ids': None, 'ids_at': 0, 'working': {}, 'failed': {}})


def cached_ids(pid, loader, force=False):
    """Candidate model IDs (ranked) from ``loader()``; cached for TTL seconds."""
    with _lock:
        e = _entry(pid)
        if not force and e['ids'] is not None and time.time() - e['ids_at'] < TTL:
            return list(e['ids'])
    ids = loader()
    with _lock:
        e = _entry(pid)
        e['ids'], e['ids_at'] = list(ids), time.time()
    return list(ids)


def remember_working(pid, model):
    with _lock:
        _entry(pid)['working'][model] = time.time()


def known_working(pid):
    """The most recently verified model, if any is still fresh."""
    with _lock:
        w = {m: t for m, t in _entry(pid)['working'].items() if time.time() - t < TTL}
    return max(w, key=w.get) if w else None


def remember_failed(pid, model):
    with _lock:
        _entry(pid)['failed'][model] = time.time()


def recently_failed(pid, model):
    with _lock:
        t = _entry(pid)['failed'].get(model)
    return bool(t and time.time() - t < TTL)


def reset(pid=None):
    with _lock:
        (_state.pop(pid, None) if pid else _state.clear())


def run(pid, label, preferred, loader, call, requested=None):
    """Call ``call(model)`` choosing the model safely.

    * ``requested`` (a model the user typed in the UI) is strict: it is used as-is and a failure is
      reported, never replaced.
    * ``preferred`` (the server's GROQ_MODEL / GEMINI_MODEL) and the discovered list are tried in order;
      only "model not found / not allowed" moves on to the next candidate.
    Returns ``(result, model_used)``."""
    if requested:
        result = call(requested)
        remember_working(pid, requested)
        return result, requested
    candidates = []
    for m in [known_working(pid), preferred]:
        if m and m not in candidates and not recently_failed(pid, m):
            candidates.append(m)
    try:
        listed = cached_ids(pid, loader)
    except LLMError as e:
        if e.kind in ('not_configured', 'auth', 'quota', 'network', 'timeout'):
            raise                      # the key / connection is the problem - no model can fix that
        listed = []
    for m in listed:
        if m not in candidates and not recently_failed(pid, m):
            candidates.append(m)
    if not candidates:
        raise LLMError('model_not_found', f'{label}: no usable chat model is available for this API key. '
                                          f'Check that your API key has access to a chat-capable model and that the provider model-list endpoint is reachable. The application selects the model automatically.')
    tried, last = [], None
    for m in candidates[:5]:
        try:
            result = call(m)
        except LLMError as e:
            if e.kind != 'model_not_found':
                raise
            remember_failed(pid, m)
            tried.append(m)
            last = e
            continue
        remember_working(pid, m)
        return result, m
    raise LLMError('model_not_found', f'{label}: none of the models tried is available to this API key ({", ".join(tried)}). '
                                      f'Last error: {last}. Check your provider API key and model access; the application selects models automatically.')

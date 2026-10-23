"""Google Gemini provider (REST, standard library only).

The API key is sent in the ``x-goog-api-key`` header (never in the URL, so it cannot show up in an
error message or log). Models are discovered from ``GET /v1beta/models`` and ranked - Google retires
Gemini versions on a schedule (gemini-2.0-flash is gone, gemini-2.5-* is scheduled to follow), so no
model name is trusted blindly. GEMINI_MODEL, if set, is only the first preference."""
import os
import re

from llm import models
from llm._http import LLMError, get_json, post_json
from llm.prompt import build_prompt, to_decision

PID, LABEL = 'gemini', 'Google Gemini'
API_BASE = os.getenv('GEMINI_BASE_URL', 'https://generativelanguage.googleapis.com/v1beta').rstrip('/')
NOT_TEXT = ('image', 'tts', 'live', 'audio', 'embed', 'omni', 'robotics', 'computer-use', 'veo', 'imagen', 'lyria', 'learnlm',
            'aqa', 'vision', 'thinking-exp', 'customtools', 'deep-research')
SYSTEM_DECIDE = 'You are a precise negotiation-agent reasoning engine that replies with strict JSON only.'


def available():
    return bool(os.getenv('GEMINI_API_KEY', '').strip())


def preferred_model():
    return os.getenv('GEMINI_MODEL', '').strip() or None


def default_model():
    return models.known_working(PID) or preferred_model() or 'auto'


def _headers():
    if not available():
        raise LLMError('not_configured', 'Gemini is not configured: set GEMINI_API_KEY in backend/.env and restart the server.')
    return {'x-goog-api-key': os.environ['GEMINI_API_KEY'].strip()}


def _rank(model_id):
    """Sort key: Flash first (fast, free tier), then Flash-Lite, then Pro; newest version first; stable before preview."""
    m = re.match(r'gemini-(\d+(?:\.\d+)?)-(flash-lite|flash|pro)(.*)$', model_id)
    if not m:
        return (9, 0, 1, model_id)
    version, family, rest = float(m.group(1)), m.group(2), m.group(3)
    fam = {'flash': 0, 'flash-lite': 1, 'pro': 2}[family]
    return (fam, -version, 1 if 'preview' in rest or 'exp' in rest else 0, model_id)


def list_models():
    """Ranked text-generation Gemini model IDs this key can use."""
    ids, token = [], None
    for _ in range(4):
        url = f'{API_BASE}/models?pageSize=200' + (f'&pageToken={token}' if token else '')
        payload = get_json(url, _headers(), LABEL)
        for m in payload.get('models', []):
            name = str(m.get('name', '')).replace('models/', '')
            if name.startswith('gemini-') and 'generateContent' in (m.get('supportedGenerationMethods') or []) \
                    and not any(x in name for x in NOT_TEXT):
                ids.append(name)
        token = payload.get('nextPageToken')
        if not token:
            break
    return sorted(set(ids), key=_rank)


def _thinking_config(model, full=True):
    if not full:
        return None
    if re.match(r'gemini-3', model):
        return {'thinkingLevel': 'low'}
    if re.match(r'gemini-2\.5-(flash|flash-lite)', model):
        return {'thinkingBudget': 0}
    return None


def _body(model, system, contents, temperature, max_tokens, json_mode, optimise=True):
    cfg = {'temperature': temperature, 'maxOutputTokens': max_tokens}
    if json_mode:
        cfg['responseMimeType'] = 'application/json'
    think = _thinking_config(model, optimise)
    if think:
        cfg['thinkingConfig'] = think
    return {'contents': contents, 'systemInstruction': {'parts': [{'text': system}]}, 'generationConfig': cfg}


def _text(payload):
    fb = payload.get('promptFeedback') or {}
    if fb.get('blockReason'):
        raise LLMError('bad_response', f'Gemini blocked the request ({fb["blockReason"]}).')
    try:
        cand = payload['candidates'][0]
    except (KeyError, IndexError, TypeError):
        raise LLMError('bad_response', 'Gemini returned no candidates.')
    parts = (cand.get('content') or {}).get('parts') or []
    text = ''.join(p.get('text', '') for p in parts if isinstance(p, dict) and not p.get('thought')).strip()
    if not text:
        reason = cand.get('finishReason', 'unknown')
        if reason == 'MAX_TOKENS':
            raise LLMError('truncated', 'Gemini stopped before writing an answer (token limit reached).')
        raise LLMError('bad_response', f'Gemini returned an empty answer (finish reason: {reason}).')
    return text


def _complete(model, system, contents, temperature, max_tokens, json_mode):
    url = f'{API_BASE}/models/{model}:generateContent'
    headers = _headers()
    try:
        payload = post_json(url, _body(model, system, contents, temperature, max_tokens, json_mode), headers, LABEL)
    except LLMError as e:
        if e.kind != 'bad_request':
            raise
        # An optional setting (thinking config / JSON mime type) was refused by this model: retry once plain.
        payload = post_json(url, _body(model, system, contents, temperature, max_tokens, False, optimise=False), headers, LABEL)
    return _text(payload)


def _run(call, requested):
    return models.run(PID, LABEL, preferred_model(), list_models, call, requested)


def decide(inp, model=None, repair=None):
    """Returns (AgentDecision, model_used)."""
    contents = [{'role': 'user', 'parts': [{'text': build_prompt(inp, repair)}]}]
    text, used = _run(lambda m: _complete(m, SYSTEM_DECIDE, contents, 0.4, 2048, True), model)
    return to_decision(text), used


def chat(system, messages, model=None, max_tokens=700):
    """Plain-text reply for the Negotiation Assistant. Returns (text, model_used)."""
    contents = [{'role': 'model' if m['role'] == 'assistant' else 'user', 'parts': [{'text': m['content']}]} for m in messages]
    return _run(lambda m: _complete(m, system, contents, 0.4, max_tokens + 1500, False), model)


def ping(model=None):
    contents = [{'role': 'user', 'parts': [{'text': 'Reply with exactly the single word: ready'}]}]
    return _run(lambda m: _complete(m, 'You are a connectivity check.', contents, 0, 400, False), model)

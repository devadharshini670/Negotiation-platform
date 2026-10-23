"""Groq provider (OpenAI-compatible REST API, standard library only).

The model is *discovered*, not assumed: ``GET /openai/v1/models`` lists what the key can see and the
ranked candidates are tried until one answers (see llm/models.py). GROQ_MODEL, if set, is only the
first preference - it never forces a model that Groq says is unavailable."""
import os

from llm import models
from llm._http import LLMError, get_json, post_json
from llm.prompt import build_prompt, to_decision

PID, LABEL = 'groq', 'Groq'
BASE_URL = os.getenv('GROQ_BASE_URL', 'https://api.groq.com/openai/v1').rstrip('/')

# Best first. Verified against https://console.groq.com/docs/models; used only to rank what the API reports.
PREFERRED = ['openai/gpt-oss-120b', 'openai/gpt-oss-20b', 'llama-3.3-70b-versatile', 'llama-3.1-8b-instant',
             'qwen/qwen3-32b', 'meta-llama/llama-4-scout-17b-16e-instruct']
NOT_CHAT = ('whisper', 'tts', 'orpheus', 'guard', 'safeguard', 'embed', 'compound', 'playai', 'distil-whisper')

SYSTEM_DECIDE = 'You are a precise negotiation-agent reasoning engine that replies with strict JSON only.'


def available():
    return bool(os.getenv('GROQ_API_KEY', '').strip())


def preferred_model():
    return os.getenv('GROQ_MODEL', '').strip() or None


def default_model():
    """What the UI shows before any call: the verified model, else the configured preference, else 'auto'."""
    return models.known_working(PID) or preferred_model() or 'auto'


def _headers():
    if not available():
        raise LLMError('not_configured', 'Groq is not configured: set GROQ_API_KEY in backend/.env and restart the server.')
    return {'Authorization': f"Bearer {os.environ['GROQ_API_KEY'].strip()}"}


def list_models():
    """Ranked chat-capable model IDs this key can see."""
    payload = get_json(f'{BASE_URL}/models', _headers(), LABEL)
    ids = [m.get('id') for m in payload.get('data', []) if isinstance(m, dict) and m.get('id') and m.get('active', True) is not False]
    ids = [i for i in ids if not any(x in i.lower() for x in NOT_CHAT)]
    ranked = [m for m in PREFERRED if m in ids]
    return ranked + [i for i in ids if i not in ranked]


def _is_reasoning(model):
    return model.startswith('openai/gpt-oss') or 'qwen3' in model


def _body(model, messages, temperature, max_tokens, json_mode):
    body = {'model': model, 'messages': messages, 'temperature': temperature, 'max_tokens': max_tokens}
    if json_mode:
        body['response_format'] = {'type': 'json_object'}
    if model.startswith('openai/gpt-oss'):
        body['reasoning_effort'] = 'low'          # keep hidden reasoning from eating the answer budget
    elif 'qwen3' in model:
        body['reasoning_effort'] = 'none'
    return body


def _text(payload):
    try:
        choice = payload['choices'][0]
        text = (choice['message'].get('content') or '').strip()
    except (KeyError, IndexError, TypeError, AttributeError):
        raise LLMError('bad_response', 'Groq returned an unexpected response shape.')
    if not text:
        if choice.get('finish_reason') == 'length':
            raise LLMError('truncated', 'Groq stopped before writing an answer (token limit reached).')
        raise LLMError('bad_response', 'Groq returned an empty answer.')
    return text


def _complete(model, messages, temperature, max_tokens, json_mode):
    headers = _headers()
    try:
        payload = post_json(f'{BASE_URL}/chat/completions', _body(model, messages, temperature, max_tokens, json_mode), headers, LABEL)
    except LLMError as e:
        low = str(e).lower()
        if e.kind == 'bad_request' and json_mode and ('response_format' in low or 'json' in low):
            payload = post_json(f'{BASE_URL}/chat/completions', _body(model, messages, temperature, max_tokens, False), headers, LABEL)
        elif e.kind == 'bad_request' and 'reasoning' in low:
            body = _body(model, messages, temperature, max_tokens, json_mode)
            body.pop('reasoning_effort', None)
            payload = post_json(f'{BASE_URL}/chat/completions', body, headers, LABEL)
        else:
            raise
    return _text(payload)


def _run(call, requested):
    return models.run(PID, LABEL, preferred_model(), list_models, call, requested)


def decide(inp, model=None, repair=None):
    """Returns (AgentDecision, model_used)."""
    msgs = [{'role': 'system', 'content': SYSTEM_DECIDE}, {'role': 'user', 'content': build_prompt(inp, repair)}]
    text, used = _run(lambda m: _complete(m, msgs, 0.4, 1200, True), model)
    return to_decision(text), used


def chat(system, messages, model=None, max_tokens=700):
    """Plain-text reply for the Negotiation Assistant. Returns (text, model_used)."""
    msgs = [{'role': 'system', 'content': system}] + list(messages)
    return _run(lambda m: _complete(m, msgs, 0.4, max_tokens + (800 if _is_reasoning(m) else 0), False), model)


def ping(model=None):
    """Smallest real request that proves key + model + parsing work. Returns (sample_text, model_used)."""
    msgs = [{'role': 'user', 'content': 'Reply with exactly the single word: ready'}]
    return _run(lambda m: _complete(m, msgs, 0, 400 if _is_reasoning(m) else 20, False), model)

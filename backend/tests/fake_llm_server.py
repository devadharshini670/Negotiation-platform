"""A local stand-in for the Groq and Gemini HTTP APIs, used to test the real HTTP code paths
(model discovery, headers, error handling, JSON parsing) without internet access or API keys.
It is NOT a substitute for a live test - see backend/tools/check_llm.py for that."""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _num(txt):
    m = re.search(r'-?\d[\d,]*\.?\d*', txt or '')
    return float(m.group(0).replace(',', '')) if m else None


def decide_from_prompt(prompt):
    """A tiny but rule-abiding negotiator that reads the real prompt the platform sends."""
    up = 'You want the value to go UP' in prompt
    reserve = _num(re.search(r'at least as good as ([^;]+);', prompt).group(1))
    worst = _num(re.search(r'never propose anything worse than ([^;]+);', prompt).group(1))
    step = _num(re.search(r'never concede more than ([^;]+);', prompt).group(1))
    own = re.search(r'Your previous offer: ([^.]*?)\. The opponent', prompt)
    opp = re.search(r"The opponent's latest offer: ([^\n]+?)\.(?:\n|$)", prompt)
    own_v = None if not own or own.group(1).strip() == 'none' else _num(own.group(1))
    opp_v = None if not opp or opp.group(1).strip() == 'none' else _num(opp.group(1))
    if opp_v is not None and ((opp_v >= reserve) if up else (opp_v <= reserve)):
        return {'action': 'accept', 'value': opp_v, 'rationale': 'The offer clears my minimum.', 'confidence': 0.8}
    if own_v is None:
        o = _num(re.search(r'opening value ([^,]+),', prompt).group(1))
        return {'action': 'open', 'value': o, 'rationale': 'Opening with my anchor.', 'confidence': 0.7}
    value = own_v - step if up else own_v + step
    value = max(value, worst) if up else min(value, worst)
    return {'action': 'counter', 'value': round(value, 2), 'rationale': 'Conceding a small step.', 'confidence': 0.7}


class Fake:
    """Shared, per-test configurable behaviour + a log of every request received."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.log = []                    # (provider, method, path, headers-dict, body)
        self.groq_models = ['llama-3.3-70b-versatile', 'openai/gpt-oss-120b', 'openai/gpt-oss-20b', 'whisper-large-v3']
        self.gemini_models = [
            ('gemini-2.0-flash', ['generateContent']), ('gemini-2.5-flash', ['generateContent']),
            ('gemini-3.5-flash', ['generateContent']), ('gemini-3.5-flash-image', ['generateContent']),
            ('gemini-embedding-001', ['embedContent']), ('gemini-3.1-pro-preview', ['generateContent'])]
        self.unavailable = set()         # model ids that answer "model not found"
        self.fail = None                 # (status, body) returned for every completion
        self.script = []                 # queue of raw text replies / (status, body) tuples consumed first
        self.text = None                 # fixed plain-text answer for assistant chats (default: echo)
        self.valid_keys = None           # None = accept anything


FAKE = Fake()


class _H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, status, obj):
        raw = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        return json.loads(self.rfile.read(n) or b'{}') if n else {}

    def _record(self, prov, body):
        FAKE.log.append((prov, self.command, self.path, {k.lower(): v for k, v in self.headers.items()}, body))

    def _key_ok(self, prov):
        if FAKE.valid_keys is None:
            return True
        h = {k.lower(): v for k, v in self.headers.items()}
        key = h.get('x-goog-api-key') or (h.get('authorization', '').replace('Bearer ', ''))
        return key in FAKE.valid_keys

    def _next(self):
        return FAKE.script.pop(0) if FAKE.script else None

    def do_GET(self):
        prov = 'groq' if self.path.startswith('/groq') else 'gemini'
        self._record(prov, None)
        if not self._key_ok(prov):
            return self._send(401 if prov == 'groq' else 400, {'error': {'message': 'Invalid API Key' if prov == 'groq' else 'API key not valid. Please pass a valid API key.', 'code': 'invalid_api_key' if prov == 'groq' else 400, 'status': 'INVALID_ARGUMENT'}})
        if prov == 'groq':
            return self._send(200, {'data': [{'id': m, 'active': True} for m in FAKE.groq_models]})
        return self._send(200, {'models': [{'name': f'models/{n}', 'supportedGenerationMethods': g} for n, g in FAKE.gemini_models]})

    def do_POST(self):
        body = self._body()
        if self.path.startswith('/groq'):
            self._record('groq', body)
            if not self._key_ok('groq'):
                return self._send(401, {'error': {'message': 'Invalid API Key', 'type': 'invalid_request_error', 'code': 'invalid_api_key'}})
            model = body.get('model')
            if model in FAKE.unavailable:
                return self._send(404, {'error': {'message': f'The model `{model}` does not exist or you do not have access to it.', 'type': 'invalid_request_error', 'code': 'model_not_found'}})
            scripted = self._next()
            if isinstance(scripted, tuple):
                return self._send(*scripted)
            if FAKE.fail:
                return self._send(*FAKE.fail)
            text = scripted if scripted is not None else self._answer(body['messages'][-1]['content'], body['messages'])
            return self._send(200, {'choices': [{'message': {'role': 'assistant', 'content': text}, 'finish_reason': 'stop'}]})
        m = re.match(r'/gemini/models/([^:]+):generateContent', self.path)
        self._record('gemini', body)
        if not self._key_ok('gemini'):
            return self._send(400, {'error': {'code': 400, 'message': 'API key not valid. Please pass a valid API key.', 'status': 'INVALID_ARGUMENT', 'details': [{'reason': 'API_KEY_INVALID'}]}})
        model = m.group(1) if m else ''
        if model in FAKE.unavailable:
            return self._send(404, {'error': {'code': 404, 'message': f'models/{model} is not found for API version v1beta, or is not supported for generateContent.', 'status': 'NOT_FOUND'}})
        scripted = self._next()
        if isinstance(scripted, tuple):
            return self._send(*scripted)
        if FAKE.fail:
            return self._send(*FAKE.fail)
        user = body['contents'][-1]['parts'][0]['text']
        text = scripted if scripted is not None else self._answer(user, [{'content': c['parts'][0]['text']} for c in body['contents']])
        return self._send(200, {'candidates': [{'content': {'role': 'model', 'parts': [{'text': 'thinking...', 'thought': True}, {'text': text}]}, 'finishReason': 'STOP'}]})

    def _answer(self, last, msgs):
        if 'Your previous offer:' in last and 'Return exactly this JSON shape' in last:
            return json.dumps(decide_from_prompt(last))
        if last.startswith('Reply with exactly the single word'):
            return 'ready'
        if FAKE.text is not None:
            return FAKE.text
        return f'ECHO[{len(msgs)} messages] ' + last[:80]


def start():
    srv = ThreadingHTTPServer(('127.0.0.1', 0), _H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f'http://127.0.0.1:{srv.server_address[1]}'

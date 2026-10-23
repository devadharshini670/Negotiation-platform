"""Groq + Gemini integration: model discovery, auth/quota/network errors, no silent provider switching,
real-LLM negotiations (Simulation and Practice), the free-text assistant and role icons.
Everything runs against the local fake server in fake_llm_server.py (no internet needed)."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from unittest import mock

import pytest

from app import app
from engine import negotiation_engine as eng
from llm import gemini_provider, groq_provider, models, provider
from llm._http import LLMError
from llm.prompt import to_decision
from models.scenarios import SCENARIOS, list_scenarios
from tests.fake_llm_server import FAKE
from tests.test_enhancements import new_user

GROQ = {'GROQ_API_KEY': 'gsk_TESTKEY_abcdefghijk', 'GROQ_MODEL': ''}
GEM = {'GEMINI_API_KEY': 'AIzaTESTKEY_abcdefghijk', 'GEMINI_MODEL': ''}
BOTH = {**GROQ, **GEM}


def fresh():
    FAKE.reset()
    provider.reset_for_tests()


def calls(prov, method=None):
    return [c for c in FAKE.log if c[0] == prov and (method is None or c[1] == method)]


# ───────────────────────────── Groq: the reported 404 ─────────────────────────────
def test_groq_unavailable_model_is_skipped_and_a_working_one_is_used_and_reported():
    fresh()
    FAKE.unavailable = {'llama-3.3-70b-versatile'}
    with mock.patch.dict(os.environ, {**GROQ, 'GROQ_MODEL': 'llama-3.3-70b-versatile'}):    # the old .env value must not break things
        r = provider.test_connection('groq')
    assert r['ok'] and r['model'] == 'openai/gpt-oss-120b', r
    assert 'gsk_' not in json.dumps(r)
    sent = [c[4]['model'] for c in calls('groq', 'POST')]
    assert sent[0] == 'llama-3.3-70b-versatile' and sent[-1] == 'openai/gpt-oss-120b'   # tried the preference, then moved on


def test_groq_models_that_are_not_chat_models_are_never_candidates():
    fresh()
    with mock.patch.dict(os.environ, GROQ):
        ids = groq_provider.list_models()
    assert 'whisper-large-v3' not in ids and ids[0] == 'openai/gpt-oss-120b'


def test_groq_request_shape_for_reasoning_models_has_room_for_the_answer():
    fresh()
    with mock.patch.dict(os.environ, GROQ):
        assert provider.test_connection('groq')['ok']
    body = calls('groq', 'POST')[-1][4]
    assert body['reasoning_effort'] == 'low' and body['max_tokens'] >= 400
    assert calls('groq', 'POST')[-1][3]['authorization'] == 'Bearer ' + GROQ['GROQ_API_KEY']


def test_a_model_typed_by_the_user_is_strict_and_its_failure_is_reported_not_replaced():
    fresh()
    FAKE.unavailable = {'my-own-model'}
    with mock.patch.dict(os.environ, GROQ):
        r = provider.test_connection('groq', 'my-own-model')
    assert not r['ok'] and r['error']['kind'] == 'model_not_found'
    assert [c[4]['model'] for c in calls('groq', 'POST')] == ['my-own-model']


# ───────────────────────────── Gemini: retired models, header key ─────────────────────────────
def test_gemini_discovery_skips_retired_and_non_text_models_and_picks_the_newest_flash():
    fresh()
    with mock.patch.dict(os.environ, GEM):
        ids = gemini_provider.list_models()
        r = provider.test_connection('gemini')
    assert 'gemini-embedding-001' not in ids and 'gemini-3.5-flash-image' not in ids
    assert ids[0] == 'gemini-3.5-flash', ids
    assert r['ok'] and r['model'] == 'gemini-3.5-flash'


def test_gemini_key_is_sent_in_a_header_never_in_the_url():
    fresh()
    with mock.patch.dict(os.environ, GEM):
        provider.test_connection('gemini')
    assert calls('gemini')
    for prov, method, path, headers, _ in calls('gemini'):
        assert 'AIza' not in path and 'key=' not in path
        assert headers['x-goog-api-key'] == GEM['GEMINI_API_KEY']


def test_gemini_retired_default_model_falls_through_to_a_live_one():
    fresh()
    FAKE.unavailable = {'gemini-2.0-flash'}
    with mock.patch.dict(os.environ, {**GEM, 'GEMINI_MODEL': 'gemini-2.0-flash'}):
        r = provider.test_connection('gemini')
    assert r['ok'] and r['model'] != 'gemini-2.0-flash'


def test_gemini_thinking_settings_use_the_right_field_per_generation_and_are_dropped_if_refused():
    fresh()
    with mock.patch.dict(os.environ, GEM):
        gemini_provider.chat('sys', [{'role': 'user', 'content': 'hi'}])
    cfg = calls('gemini', 'POST')[-1][4]['generationConfig']
    assert cfg['thinkingConfig'] == {'thinkingLevel': 'low'}
    fresh()
    FAKE.script = [(400, {'error': {'code': 400, 'message': 'Unknown name "thinkingConfig"', 'status': 'INVALID_ARGUMENT'}})]
    with mock.patch.dict(os.environ, GEM):
        text, _ = gemini_provider.chat('sys', [{'role': 'user', 'content': 'hi'}])
    assert text and 'thinkingConfig' not in calls('gemini', 'POST')[-1][4]['generationConfig']


def test_gemini_thought_parts_are_not_part_of_the_answer():
    fresh()
    FAKE.text = 'The real answer'
    with mock.patch.dict(os.environ, GEM):
        text, _ = gemini_provider.chat('sys', [{'role': 'user', 'content': 'hi'}])
    assert text == 'The real answer'


def test_gemini_truncated_empty_answer_is_a_clear_error():
    fresh()
    FAKE.script = [(200, {'candidates': [{'content': {'parts': []}, 'finishReason': 'MAX_TOKENS'}]})]
    with mock.patch.dict(os.environ, {**GEM, 'GEMINI_MODEL': 'gemini-3.5-flash'}):
        with pytest.raises(LLMError) as e:
            gemini_provider.chat('sys', [{'role': 'user', 'content': 'hi'}])
    assert e.value.kind == 'truncated'


# ───────────────────────────── error handling (both providers) ─────────────────────────────
@pytest.mark.parametrize('pid,env', [('groq', GROQ), ('gemini', GEM)])
def test_invalid_key_gives_a_clear_auth_error_without_the_key(pid, env):
    fresh()
    FAKE.valid_keys = {'a-different-key'}
    with mock.patch.dict(os.environ, env):
        r = provider.test_connection(pid)
    assert not r['ok'] and r['error']['kind'] == 'auth', r
    assert 'key' in r['error']['message'].lower()
    assert list(env.values())[0] not in json.dumps(r)


@pytest.mark.parametrize('pid,env', [('groq', GROQ), ('gemini', GEM)])
def test_quota_and_server_errors_are_classified(pid, env):
    fresh()
    FAKE.fail = (429, {'error': {'message': 'Rate limit reached', 'code': 'rate_limit_exceeded', 'status': 'RESOURCE_EXHAUSTED'}})
    with mock.patch.dict(os.environ, env):
        assert provider.test_connection(pid)['error']['kind'] == 'quota'
    fresh()
    FAKE.fail = (503, {'error': {'message': 'overloaded', 'status': 'UNAVAILABLE'}})
    with mock.patch.dict(os.environ, env):
        r = provider.test_connection(pid)
    assert r['error']['kind'] == 'server'


@pytest.mark.parametrize('mod,var,env', [(groq_provider, 'GROQ_BASE_URL', GROQ), (gemini_provider, 'GEMINI_BASE_URL', GEM)])
def test_unreachable_network_is_reported_as_a_network_error(mod, var, env):
    fresh()
    with mock.patch.dict(os.environ, env), mock.patch.object(mod, 'BASE_URL' if mod is groq_provider else 'API_BASE', 'http://127.0.0.1:9'):
        r = provider.test_connection(mod.PID)
    assert not r['ok'] and r['error']['kind'] == 'network'


def test_not_configured_provider_is_reported_not_faked():
    fresh()
    r = provider.test_connection('gemini')
    assert not r['ok'] and r['error']['kind'] == 'not_configured'


# ───────────────────────────── only Groq and Gemini, no silent switching ─────────────────────────────
def test_only_groq_and_gemini_exist_and_status_never_contains_keys():
    fresh()
    assert list(provider.REGISTRY) == ['groq', 'gemini']
    with mock.patch.dict(os.environ, BOTH):
        c, h = new_user()
        text = c.get('/api/llm/status').get_data(as_text=True) + json.dumps(c.post('/api/llm/test', json={'provider': 'groq'}, headers=h).get_json())
    assert 'gsk_' not in text and 'AIza' not in text
    assert 'anthropic' not in text.lower() and 'claude' not in text.lower()
    assert [p['id'] for p in c.get('/api/llm/status').get_json()['providers']] == ['groq', 'gemini']


def test_selected_provider_is_never_swapped_for_another():
    fresh()
    with mock.patch.dict(os.environ, GROQ):          # only Groq has a key
        with pytest.raises(ValueError, match='GEMINI_API_KEY'):
            provider.resolve('llm', 'gemini')
        with pytest.raises(ValueError):
            provider.resolve('llm', 'anthropic')
        assert provider.resolve('llm', 'groq')[1] == 'groq'
    with pytest.raises(ValueError):
        provider.resolve('llm', None)                 # no key at all: refuse instead of quietly using the rule engine


def test_llm_test_endpoint_needs_login_and_validates_input():
    fresh()
    assert app.test_client().post('/api/llm/test', json={'provider': 'groq'}).status_code in (401, 403)
    c, h = new_user()
    assert c.post('/api/llm/test', json={'provider': 'anthropic'}, headers=h).status_code == 400
    assert c.post('/api/llm/test', json={'provider': 'groq', 'model': 'bad model!'}, headers=h).status_code == 400


def test_creating_an_llm_negotiation_fails_loudly_when_the_provider_does_not_work():
    fresh()
    FAKE.valid_keys = {'other'}
    with mock.patch.dict(os.environ, GROQ):
        c, h = new_user()
        r = c.post('/api/negotiations', json={'scenario_id': 'vendor_pricing', 'personality_a': 'collaborative', 'personality_b': 'aggressive',
                                             'mode': 'llm', 'llm_provider': 'groq'}, headers=h)
        assert r.status_code == 502 and 'not working' in r.get_json()['error'] and r.get_json()['error_kind'] == 'auth'
        r = c.post('/api/negotiations', json={'scenario_id': 'vendor_pricing', 'personality_a': 'collaborative', 'personality_b': 'aggressive',
                                             'mode': 'llm', 'llm_provider': 'gemini'}, headers=h)
        assert r.status_code == 400 and 'GEMINI_API_KEY' in r.get_json()['error']
    assert not c.get('/api/negotiations').get_json()


# ───────────────────────────── real-LLM decisions ─────────────────────────────
def test_decision_parsing_accepts_common_variants_and_rejects_missing_fields():
    d = to_decision('{"action":"Counteroffer","value":"$1,200.50","rationale":"x"}')
    assert (d.action, d.value) == ('counter', 1200.5)
    assert to_decision('```json\n{"action":"accept","value":45}\n```').action == 'accept'
    with pytest.raises(ValueError):
        to_decision('{"value": 10}')
    with pytest.raises(ValueError):
        to_decision('I think we should counter')


def _llm_negotiation(c, h, pid, wf='simulation', sid='vendor_pricing', pause=False):
    r = c.post('/api/negotiations', json={'scenario_id': sid, 'personality_a': 'collaborative', 'personality_b': 'aggressive', 'mode': 'llm',
                                         'llm_provider': pid, 'workflow_mode': wf, 'max_rounds': 8, 'allow_fallback': not pause}, headers=h)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


@pytest.mark.parametrize('pid,env,other', [('groq', GROQ, 'gemini'), ('gemini', GEM, 'groq')])
def test_ai_vs_ai_simulation_uses_the_selected_provider_for_every_turn(pid, env, other):
    fresh()
    with mock.patch.dict(os.environ, BOTH):
        c, h = new_user()
        n = _llm_negotiation(c, h, pid)
        assert n['llm_provider'] == pid and n['llm_model'] and n['llm_model'] != 'auto'
        before = len(calls(other))
        s = c.post(f"/api/negotiations/{n['id']}/run", headers=h).get_json()
    assert s['status'] in ('agreed', 'max_rounds_reached', 'deadlock', 'rejected')
    ai = [o for o in s['history']]
    assert ai and all(o['source'] == 'llm' for o in ai), [o['source'] for o in ai]
    assert s['fallback_count'] == 0 and s['llm_calls'] >= len(ai) and s['last_error'] == ''
    assert len(calls(other)) == before                                      # the other provider was never contacted
    rounds = [o['round'] for o in s['history']]
    assert rounds == sorted(rounds) and max(rounds) <= s['max_rounds']      # turn order / round limit preserved
    agents = [o['agent_id'] for o in s['history']]
    assert agents[0] == s['agents'][0]['id'] and all(a != b for a, b in zip(agents, agents[1:]))   # strict A,B,A,B alternation


def test_personality_is_sent_to_the_model_and_differs_between_agents():
    fresh()
    with mock.patch.dict(os.environ, GROQ):
        c, h = new_user()
        n = _llm_negotiation(c, h, 'groq')
        c.post(f"/api/negotiations/{n['id']}/step", headers=h)
        c.post(f"/api/negotiations/{n['id']}/step", headers=h)
    prompts = [c_[4]['messages'][-1]['content'] for c_ in calls('groq', 'POST') if 'Round' in c_[4]['messages'][-1]['content']]
    assert 'COLLABORATIVELY' in prompts[-2] and 'AGGRESSIVELY' in prompts[-1]
    assert 'You are the Buyer' in prompts[-2] and 'You are the Vendor' in prompts[-1]
    assert 'Round 1 of 8' in prompts[-2] and "opponent's latest offer" in prompts[-1]


def test_practice_mode_runs_the_ai_side_with_the_selected_provider():
    fresh()
    with mock.patch.dict(os.environ, GEM):
        c, h = new_user()
        n = _llm_negotiation(c, h, 'gemini', wf='practice')
        s = c.post(f"/api/negotiations/{n['id']}/human-action", json={'action': 'open', 'value': 33, 'message': 'Hello, my opening offer is 33.'}, headers=h).get_json()
        assert s['history'][0]['source'] == 'human'
        s = c.post(f"/api/negotiations/{n['id']}/run", headers=h).get_json()
    ai = [o for o in s['history'] if o['agent_id'] == s['agents'][1]['id']]
    assert ai and all(o['source'] == 'llm' for o in ai) and s['fallback_count'] == 0 and s['human_turn']
    assert 'Practice Mode' in [c_[4] for c_ in calls('gemini', 'POST')][-1]['contents'][-1]['parts'][0]['text']


def test_an_unusable_reply_is_sent_back_once_and_the_corrected_answer_is_used_as_a_real_llm_decision():
    fresh()
    with mock.patch.dict(os.environ, GROQ):
        c, h = new_user()
        n = _llm_negotiation(c, h, 'groq')
        FAKE.script = ['Sure! I would counter at around thirty-five dollars.']       # not JSON
        s = c.post(f"/api/negotiations/{n['id']}/step", headers=h).get_json()
    assert s['history'][0]['source'] == 'llm' and s['fallback_count'] == 0
    assert 'could not be used' in calls('groq', 'POST')[-1][4]['messages'][-1]['content']


def test_an_illegal_move_from_the_model_is_corrected_by_the_orchestrator_never_applied():
    fresh()
    with mock.patch.dict(os.environ, GROQ):
        c, h = new_user()
        n = _llm_negotiation(c, h, 'groq')
        # The buyer (hard ceiling $48) is told by the "model" to open at $90: the evaluator must clamp it.
        FAKE.script = [json.dumps({'action': 'open', 'value': 90, 'rationale': 'Go big.', 'confidence': 0.9})]
        s = c.post(f"/api/negotiations/{n['id']}/step", headers=h).get_json()
    o = s['history'][0]
    assert o['value'] <= 48 and o['corrected'] and s['orchestrator_corrections'] == 1


def test_persistent_llm_failure_is_labelled_as_a_rule_based_fallback_never_as_the_llm():
    fresh()
    with mock.patch.dict(os.environ, GROQ):
        c, h = new_user()
        n = _llm_negotiation(c, h, 'groq')
        FAKE.fail = (500, {'error': {'message': 'boom'}})
        s = c.post(f"/api/negotiations/{n['id']}/step", headers=h).get_json()
    assert s['history'][0]['source'] == 'fallback' and s['fallback_count'] == 1 and s['llm_calls'] == 0
    assert s['history'][0]['rationale'].startswith('Rule-based fallback') and 'HTTP 500' in s['last_error']
    assert len(calls('groq', 'POST')) >= 3                                          # it retried before giving up


def test_pause_on_error_applies_nothing_and_reports_the_error():
    fresh()
    with mock.patch.dict(os.environ, GROQ):
        c, h = new_user()
        n = _llm_negotiation(c, h, 'groq', pause=True)
        FAKE.fail = (429, {'error': {'message': 'Rate limit reached', 'code': 'rate_limit_exceeded'}})
        r = c.post(f"/api/negotiations/{n['id']}/step", headers=h)
        s = c.get(f"/api/negotiations/{n['id']}").get_json()
    assert r.status_code == 409 and 'fallback is turned off' in r.get_json()['error']
    assert s['history'] == [] and s['fallback_count'] == 0 and s['current_round'] == 1


def test_rule_based_mode_is_still_available_and_labelled_as_such():
    fresh()
    c, h = new_user()
    r = c.post('/api/negotiations', json={'scenario_id': 'job_offer', 'personality_a': 'analytical', 'personality_b': 'strategic', 'mode': 'mock'}, headers=h)
    s = c.post(f"/api/negotiations/{r.get_json()['id']}/run", headers=h).get_json()
    assert s['mode'] == 'mock' and all(o['source'] == 'mock' for o in s['history']) and not calls('groq') and not calls('gemini')


# ───────────────────────────── the assistant ─────────────────────────────
def _ask(c, h, msg, **extra):
    return c.post('/api/assistant/chat', json={'message': msg, **extra}, headers=h)


def test_assistant_answers_a_free_text_question_with_the_selected_real_provider():
    fresh()
    FAKE.text = None
    with mock.patch.dict(os.environ, BOTH):
        c, h = new_user()
        r = _ask(c, h, 'How should I respond when a landlord refuses to move on the deposit?', provider='gemini')
    j = r.get_json()
    assert r.status_code == 200 and j['source'] == 'ai' and j['provider'] == 'gemini' and j['model']
    assert j['reply'].startswith('ECHO') and not calls('groq')
    system = calls('gemini', 'POST')[-1][4]['systemInstruction']['parts'][0]['text']
    assert 'negotiation coach' in system and 'general negotiation knowledge' in system.lower()


def test_assistant_keeps_conversation_context_for_follow_ups():
    fresh()
    with mock.patch.dict(os.environ, GROQ):
        c, h = new_user()
        _ask(c, h, 'What is a BATNA?', provider='groq')
        _ask(c, h, 'Give me an example of that', provider='groq')
    msgs = calls('groq', 'POST')[-1][4]['messages']
    contents = [m['content'] for m in msgs]
    assert 'What is a BATNA?' in contents and contents[-1] == 'Give me an example of that'
    assert any(m['role'] == 'assistant' and m['content'].startswith('ECHO') for m in msgs)


def test_assistant_predefined_questions_also_go_to_the_llm():
    fresh()
    with mock.patch.dict(os.environ, GROQ):
        c, h = new_user()
        r = _ask(c, h, 'What does this platform do?', provider='groq').get_json()
    assert r['source'] == 'ai' and calls('groq', 'POST')


def test_assistant_failure_is_an_error_not_a_fake_answer_and_is_not_stored():
    fresh()
    FAKE.fail = (500, {'error': {'message': 'down'}})
    with mock.patch.dict(os.environ, GROQ):
        c, h = new_user()
        r = _ask(c, h, 'What is anchoring?', provider='groq')
        hist = c.get('/api/assistant/history').get_json()['messages']
    assert r.status_code == 502 and 'unavailable' in r.get_json()['error'] and 'reply' not in r.get_json()
    assert hist == []


def test_assistant_invalid_key_and_quota_have_clear_messages():
    fresh()
    FAKE.valid_keys = {'x'}
    with mock.patch.dict(os.environ, GEM):
        c, h = new_user()
        r = _ask(c, h, 'hello', provider='gemini')
    assert r.status_code == 502 and r.get_json()['error_kind'] == 'auth' and 'AIza' not in r.get_data(as_text=True)
    fresh()
    FAKE.fail = (429, {'error': {'message': 'quota', 'status': 'RESOURCE_EXHAUSTED'}})
    with mock.patch.dict(os.environ, GEM):
        r = _ask(c, h, 'hello', provider='gemini')
    assert r.status_code == 429 and r.get_json()['error_kind'] == 'quota'


def test_assistant_rejects_empty_and_over_long_messages_and_unconfigured_providers():
    fresh()
    with mock.patch.dict(os.environ, GROQ):
        c, h = new_user()
        assert _ask(c, h, '   ', provider='groq').status_code == 400
        assert _ask(c, h, 'x' * 5000, provider='groq').status_code == 400
        assert _ask(c, h, 'hi', provider='anthropic').status_code == 503      # unknown provider is never honoured or swapped
    assert not calls('groq', 'POST')
    fresh()
    c, h = new_user()
    assert _ask(c, h, 'hi').status_code == 503


def test_assistant_refuses_actions_without_calling_the_model_and_cannot_change_a_negotiation():
    fresh()
    with mock.patch.dict(os.environ, GROQ):
        c, h = new_user()
        n = _llm_negotiation(c, h, 'groq')
        before = json.dumps(c.get(f"/api/negotiations/{n['id']}").get_json(), sort_keys=True)
        n_calls = len(calls('groq', 'POST'))
        r = _ask(c, h, 'Accept the vendor offer', negotiation_id=n['id'], provider='groq').get_json()
        assert r['source'] == 'builtin' and len(calls('groq', 'POST')) == n_calls
        _ask(c, h, 'Why would an aggressive vendor concede slowly?', negotiation_id=n['id'], provider='groq')
        after = json.dumps(c.get(f"/api/negotiations/{n['id']}").get_json(), sort_keys=True)
    assert before == after


def test_assistant_uses_the_provider_of_the_open_negotiation_even_if_the_page_sends_another():
    fresh()
    with mock.patch.dict(os.environ, BOTH):
        c, h = new_user()
        n = _llm_negotiation(c, h, 'gemini')
        g0 = len(calls('gemini', 'POST'))
        _ask(c, h, 'Summarize the situation', negotiation_id=n['id'], provider='groq')
    assert len(calls('gemini', 'POST')) == g0 + 1 and not calls('groq', 'POST')


# ───────────────────────────── role icons ─────────────────────────────
@pytest.mark.skipif(shutil.which('node') is None, reason='node is needed to evaluate the front-end mapping')
def test_every_scenario_gives_its_two_roles_different_specific_icons():
    js = (Path(__file__).resolve().parents[2] / 'frontend' / 'api.js').read_text(encoding='utf-8')
    block = js[js.index('const ROLE_RULES'):js.index('function roleIcon(')]
    code = block + '\nconst out = {}; for (const r of JSON.parse(process.argv[1])) out[r] = roleIconKey(r); console.log(JSON.stringify(out));'
    roles = sorted({a.role_label for s in SCENARIOS.values() for a in (s.side_a, s.side_b)})
    out = json.loads(subprocess.run(['node', '-e', code, json.dumps(roles)], capture_output=True, text=True, check=True).stdout)
    for s in list_scenarios():
        a, b = (out[x['role']] for x in s['agents'])
        assert a != b, (s['id'], a, b)
        assert 'person' not in (a, b), (s['id'], s['agents'])
    assert out['Buyer'] == 'buyer' and out['Vendor'] == 'seller' and out['Candidate'] == 'candidate' and out['Freelancer'] == 'freelancer'


def test_frontend_has_no_claude_or_anthropic_option_and_no_keys():
    root = Path(__file__).resolve().parents[2]
    for f in list((root / 'frontend').glob('*.html')) + list((root / 'frontend').glob('*.js')):
        text = f.read_text(encoding='utf-8').lower()
        assert 'anthropic' not in text and 'claude' not in text, f.name
        assert not re.search(r'gsk_[a-z0-9]{8}|aiza[a-z0-9_\-]{8}', text), f.name
    assert not (root / 'backend' / 'llm' / 'real_provider.py').exists()
    assert 'anthropic' not in (root / 'backend' / 'requirements.txt').read_text().lower()

"""Provider-layer unit tests that need no negotiation server: prompt content, reply parsing,
secret scrubbing and provider selection. (HTTP behaviour, model discovery and the full workflows
are in test_llm_integration.py.)"""
import io
import json
import os
import socket
import urllib.error
from unittest import mock

import pytest

from engine import negotiation_engine as eng, orchestrator
from llm import groq_provider, gemini_provider, provider
from llm._http import LLMError
from llm.prompt import to_decision, build_prompt
from models.state import NegotiationStatus
from tests.fake_llm_server import FAKE

KEY = {'GROQ_API_KEY': 'gsk_fakefakefake12345', 'GROQ_MODEL': ''}
GKEY = {'GEMINI_API_KEY': 'AIzaSyFakeFakeFakeFakeFakeFakeFakeFak', 'GEMINI_MODEL': ''}


def _inp():
    st = eng.create_negotiation('vendor_pricing', 'aggressive', 'collaborative', 'mock', 8, 'simulation')
    return st, orchestrator.build_input(st, st.agents[0])


def test_reply_parsing_handles_fences_string_values_and_clamps_confidence():
    d = to_decision('```json\n{"action":"Open","value":"$33.50","rationale":"Opening.","confidence":2}\n```')
    assert d.action == 'open' and d.value == 33.5 and d.source == 'llm' and d.confidence == 1.0


def test_non_json_llm_text_is_rejected():
    for bad in ('I think you should counter.', '[1,2,3]', ''):
        with pytest.raises(ValueError):
            to_decision(bad)


@pytest.mark.parametrize('exc', [
    urllib.error.HTTPError('u', 401, 'Unauthorized', {}, io.BytesIO(b'{"error":{"message":"bad key gsk_fakefakefake12345"}}')),
    socket.timeout('t'), urllib.error.URLError('dns fail')])
def test_transport_failures_become_llm_errors_without_leaking_the_key(exc):
    _st, inp = _inp()
    with mock.patch.dict(os.environ, KEY), mock.patch('urllib.request.urlopen', side_effect=exc):
        with pytest.raises(LLMError) as e:
            groq_provider.decide(inp, 'some-model')
    assert 'gsk_fakefakefake12345' not in str(e.value) and e.value.kind in ('auth', 'timeout', 'network')


def test_scrub_removes_configured_and_key_shaped_secrets():
    with mock.patch.dict(os.environ, {**KEY, **GKEY}):
        text = provider.scrub('failed with gsk_fakefakefake12345 and AIzaSyFakeFakeFakeFakeFakeFakeFakeFak and sk-ant-abcdefghijk12')
    assert 'gsk_' not in text and 'AIza' not in text and 'sk-ant' not in text


def test_full_negotiation_with_garbage_mid_run_marks_each_turn_by_what_really_produced_it():
    with mock.patch.dict(os.environ, KEY):
        st = eng.create_negotiation('vendor_pricing', 'aggressive', 'aggressive', 'llm', 8, 'simulation', llm_provider='groq')
        assert st.mode == 'llm' and st.llm_provider == 'groq' and st.llm_model
        FAKE.script = ['{"action":"open","value":32,"rationale":"Opening low."}'] \
            + ['total nonsense'] * 3 \
            + [(500, {'error': {'message': 'boom'}})] * 3 \
            + ['{"action":"counter","value":"abc","rationale":"x"}'] * 3
        for _ in range(4):
            orchestrator.step(st)
    srcs = [o.source for o in st.history]
    assert srcs[0] == 'llm' and srcs[1:] == ['fallback'] * 3
    assert st.fallback_count == 3 and st.status == NegotiationStatus.IN_PROGRESS
    assert st.history[0].value == 32 and 'gsk_fake' not in st.last_error


def test_provider_selection_and_status():
    with mock.patch.dict(os.environ, {'GROQ_API_KEY': '', 'GEMINI_API_KEY': ''}):
        assert provider.status()['configured'] is False
        assert provider.resolve('mock')[0] == 'mock'
        with pytest.raises(ValueError):
            provider.resolve('llm')
    with mock.patch.dict(os.environ, KEY):
        s = provider.status()
        assert s['configured'] and s['default_provider'] == 'groq' and 'gsk_' not in json.dumps(s)
        with pytest.raises(ValueError):
            provider.resolve('llm', 'anthropic')
        mode, pid, model, _ = provider.resolve('llm', 'groq', 'my-model_1.0')
        assert (mode, pid, model) == ('llm', 'groq', 'my-model_1.0')
        with pytest.raises(ValueError):
            provider.resolve('llm', 'groq', 'bad model; rm -rf')       # unsafe override is refused, not ignored


def test_prompt_includes_persona_state_and_personality_rules():
    st, inp = _inp()
    orchestrator.step(st)
    inp2 = orchestrator.build_input(st, st.agents[1])
    text = build_prompt(inp2)
    assert 'COLLABORATIVELY' in text and 'Round 1 of 8' in text and 'opponent\'s latest offer' in text.lower()
    assert '"agent_id": "buyer"' in text          # full public history is present
    # the opponent's private constraint/limit is never sent to this agent
    assert 'Hard ceiling' not in text and 'Hard floor: $40/unit' in text
    assert 'Buyer' in text            # but the opponent's public role is known


def test_prompt_demands_a_plain_number_and_can_carry_a_repair_note():
    _st, inp = _inp()
    text = build_prompt(inp, repair='Missing or non-numeric proposal.')
    assert 'plain number' in text and 'Missing or non-numeric proposal.' in text and 'could not be used' in text


def test_gemini_default_model_is_discovered_and_never_a_retired_one():
    with mock.patch.dict(os.environ, GKEY):
        ids = gemini_provider.list_models()
    assert ids and ids[0].startswith('gemini-3') and 'gemini-2.0-flash' not in ids[:1]

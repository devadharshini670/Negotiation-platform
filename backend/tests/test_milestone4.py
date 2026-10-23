"""End-to-end tests for orchestration, personalities, decision validation,
Practice Mode, deadlock handling, analytics, reports and the HTTP API."""
import itertools
import math
import os
from unittest import mock

from app import app
from engine import negotiation_engine as eng, orchestrator, offer_evaluator, analytics, deadlock
from engine.offer_evaluator import InvalidDecision
from llm import provider
from llm.schema import AgentDecision
from models.scenarios import get_scenario, SCENARIOS
from models.state import Personality, NegotiationStatus

PERSONALITIES = ['aggressive', 'collaborative', 'risk_averse']
SCENARIO_IDS = list(SCENARIOS)


def new(scenario='vendor_pricing', a='collaborative', b='aggressive', workflow='simulation', rounds=8, mode='mock'):
    return eng.create_negotiation(scenario, a, b, mode, rounds, workflow)


# ───────────── Simulation Mode: every scenario x personality combination ─────────────
def test_all_scenarios_and_personality_pairs_finish_consistently():
    for sid, (pa, pb) in itertools.product(SCENARIO_IDS, itertools.product(PERSONALITIES, PERSONALITIES)):
        st = eng.run_negotiation(new(sid, pa, pb).id)
        assert st.is_terminal(), (sid, pa, pb)
        assert st.current_round <= st.max_rounds
        a, b = st.agents
        if st.status == NegotiationStatus.AGREED:
            assert a.satisfies_limit(st.final_value) and b.satisfies_limit(st.final_value), 'agreement violates a hard limit'
        else:
            assert st.final_value is None
        # nothing happens after completion
        n = len(st.history)
        orchestrator.step(st)
        assert len(st.history) == n


def test_turn_order_and_rounds_are_consistent():
    st = eng.run_negotiation(new('job_offer', 'collaborative', 'collaborative').id)
    agents = [o.agent_id for o in st.history]
    assert agents[0] == st.agents[0].id
    for x, y in zip(agents, agents[1:]):
        assert x != y, 'duplicate turn'
    rounds = [o.round for o in st.history]
    assert rounds == sorted(rounds) and rounds[0] == 1


def test_aggressive_vs_aggressive_can_end_without_agreement_and_is_explained():
    st = eng.run_negotiation(new('vendor_pricing', 'aggressive', 'aggressive', rounds=6).id)
    assert st.status in (NegotiationStatus.MAX_ROUNDS, NegotiationStatus.DEADLOCK)
    assert st.deadlock_info and st.deadlock_info['explanation']


def test_longer_stalemate_is_detected_as_deadlock_and_mediated_or_declared():
    st = eng.run_negotiation(new('vendor_pricing', 'aggressive', 'aggressive', rounds=14).id)
    assert st.deadlock_info and st.deadlock_info['triggered']
    assert st.deadlock_info['trigger'] in ('no_progress', 'repeated_offers', 'max_rounds')


# ───────────── Personalities change behaviour, not just text ─────────────
def _avg_step(st, agent_id):
    recs = [c for c in st.concessions if c.agent_id == agent_id]
    return sum(c.pct_of_range for c in recs) / len(recs) if recs else 0


def test_personalities_produce_different_concession_behaviour():
    for sid in SCENARIO_IDS:
        aggr = eng.run_negotiation(new(sid, 'aggressive', 'collaborative').id)
        coll = eng.run_negotiation(new(sid, 'collaborative', 'collaborative').id)
        assert _avg_step(aggr, aggr.agents[0].id) < _avg_step(coll, coll.agents[0].id), sid


def test_aggressive_opens_further_from_target_than_collaborative():
    sc = get_scenario('vendor_pricing')
    agg = sc.build_agent('buyer', Personality.AGGRESSIVE)
    col = sc.build_agent('buyer', Personality.COLLABORATIVE)
    assert abs(agg.opening_offer() - agg.target) > abs(col.opening_offer() - col.target)


def test_risk_averse_keeps_a_safety_margin_before_the_hard_limit():
    sc = get_scenario('vendor_pricing')
    ra = sc.build_agent('buyer', Personality.RISK_AVERSE)
    assert ra.worst_offer() < ra.limit  # buyer minimises: proposes below its ceiling
    st = eng.run_negotiation(new('vendor_pricing', 'risk_averse', 'aggressive').id)
    buyer_offers = [o.value for o in st.history if o.agent_id == 'buyer' and o.value is not None]
    assert max(buyer_offers) <= ra.worst_offer() + 1e-6


def test_message_tone_changes_ai_concession_size():
    def reply(msg):
        st = eng.create_negotiation('vendor_pricing', 'collaborative', 'collaborative', 'mock', 8, 'practice')
        eng.human_action(st.id, 'open', 33, message=msg)
        return st.last_offer_by('vendor').value
    coop = reply('Happy to build a long-term partnership if we can be flexible.')
    pressure = reply('This is my final offer, take it or leave it.')
    assert coop < pressure  # vendor (maximizer) concedes more (lower price) to a cooperative tone


# ───────────── Decision validation (Accept / Counter / Reject) ─────────────
def _agents():
    sc = get_scenario('vendor_pricing')
    return sc.build_agent('buyer', Personality.COLLABORATIVE), sc.build_agent('vendor', Personality.AGGRESSIVE)


def test_accepting_an_offer_that_violates_the_hard_limit_is_blocked():
    buyer, _ = _agents()   # ceiling $48
    d, corrected, note = offer_evaluator.validate(buyer, AgentDecision('accept', 55, 'ok'), opponent_last=55, own_last=40)
    assert d.action == 'counter' and corrected and buyer.satisfies_limit(d.value)


def test_accept_value_is_aligned_to_the_real_opponent_offer():
    buyer, _ = _agents()
    d, corrected, _n = offer_evaluator.validate(buyer, AgentDecision('accept', 10, 'ok'), opponent_last=44, own_last=40)
    assert d.action == 'accept' and d.value == 44 and corrected


def test_missing_nan_and_unknown_decisions_are_invalid_not_rejections():
    buyer, _ = _agents()
    for bad in (AgentDecision('counter', None, 'x'), AgentDecision('counter', float('nan'), 'x'),
                AgentDecision('counter', 'abc', 'x'), AgentDecision('dance', 40, 'x'), AgentDecision('accept', 40, 'x')):
        try:
            offer_evaluator.validate(buyer, bad, opponent_last=None, own_last=None)
            raise AssertionError('should have been invalid')
        except InvalidDecision:
            pass


def test_backward_moves_and_huge_concessions_are_corrected():
    buyer, _ = _agents()   # minimizer; opening 32, limit 48
    d, corrected, _ = offer_evaluator.validate(buyer, AgentDecision('counter', 36, 'x'), opponent_last=55, own_last=40)
    assert d.value == 40 and corrected   # cannot go back down
    d, corrected, _ = offer_evaluator.validate(buyer, AgentDecision('counter', 48, 'x'), opponent_last=55, own_last=33)
    assert d.value < 48 and corrected    # collaborative cap 45% of 16 = 7.2


def test_counter_that_crosses_the_opponent_offer_becomes_an_acceptance():
    buyer, _ = _agents()
    d, corrected, _ = offer_evaluator.validate(buyer, AgentDecision('counter', 46, 'x'), opponent_last=44, own_last=40)
    assert d.action == 'accept' and d.value == 44


# ───────────── LLM modes, fallback and error handling ─────────────
def _clear_keys():
    return mock.patch.dict(os.environ, {'GROQ_API_KEY': '', 'GEMINI_API_KEY': ''})


def test_llm_requested_without_credentials_is_refused_not_silently_downgraded():
    with _clear_keys():
        try:
            new(mode='llm')
            raise AssertionError('expected a clear refusal')
        except ValueError as e:
            assert 'GROQ_API_KEY' in str(e) and 'rule-based' in str(e)
        st = new(mode='mock')                      # the rule engine stays available as an explicit choice
        st = eng.run_negotiation(st.id)
        assert st.llm_calls == 0 and all(o.source == 'mock' for o in st.history)
        assert analytics.analyze(st, get_scenario(st.scenario_id))['llm']['engine_label'].startswith('Mock')


def test_llm_failure_falls_back_and_is_counted_and_never_ends_the_negotiation_early():
    with mock.patch.dict(os.environ, {'GROQ_API_KEY': 'gsk_testkey123456789'}):
        st = new(mode='llm')
        assert st.mode == 'llm' and st.llm_provider == 'groq'
        with mock.patch.object(provider, 'reason', side_effect=RuntimeError('Groq API unreachable: gsk_testkey123456789')):
            st = eng.run_negotiation(st.id)
        assert st.fallback_count == len(st.history) > 0
        assert all(o.source == 'fallback' for o in st.history)
        assert 'gsk_testkey' not in st.last_error          # secret is scrubbed
        assert st.status != NegotiationStatus.REJECTED


def test_malformed_llm_output_uses_fallback_instead_of_rejecting():
    with mock.patch.dict(os.environ, {'GROQ_API_KEY': 'gsk_testkey123456789'}):
        for bad in (AgentDecision('counter', None, 'no number', .5, 'llm'), AgentDecision('counter', 'lots', 'text', .5, 'llm'),
                    AgentDecision('accept', 5, 'x', .5, 'llm')):
            st = new(mode='llm')
            with mock.patch.object(provider, 'reason', return_value=(bad, 'm')):
                orchestrator.step(st)
            assert st.status == NegotiationStatus.IN_PROGRESS and st.history[-1].action.value == 'open'
            assert st.history[-1].source == 'fallback' and st.fallback_count == 1
            assert st.llm_calls == orchestrator.MAX_ATTEMPTS        # the model was asked again with the reason before giving up


def test_timeout_is_handled_as_fallback():
    with mock.patch.dict(os.environ, {'GROQ_API_KEY': 'gsk_testkey123456789'}):
        st = new(mode='llm')
        with mock.patch.object(provider, 'reason', side_effect=TimeoutError('timed out')):
            orchestrator.step(st)
        assert st.fallback_count == 1 and st.history[-1].source == 'fallback'


def test_real_llm_path_labels_source_llm():
    with mock.patch.dict(os.environ, {'GROQ_API_KEY': 'gsk_testkey123456789'}):
        st = new(mode='llm')
        good = AgentDecision('open', 33, 'Opening firmly.', .9, 'llm')
        with mock.patch.object(provider, 'reason', return_value=(good, 'm')):
            orchestrator.step(st)
        assert st.history[-1].source == 'llm' and st.llm_calls == 1 and st.fallback_count == 0


def test_provider_prompt_contains_persona_history_and_private_numbers_only_for_owner():
    from llm.prompt import build_prompt
    st = new()
    orchestrator.step(st)
    text = build_prompt(orchestrator.build_input(st, st.agents[1]))
    for needle in ('Vendor', 'aggressive', 'Round 1 of 8', 'Full public conversation history', 'hard limit', "opponent's latest offer"):
        assert needle.lower() in text.lower(), needle


# ───────────── Practice Mode ─────────────
def test_practice_ai_responds_to_the_users_actual_offer_in_one_request():
    st = new(workflow='practice')
    eng.human_action(st.id, 'open', 33, message='Opening at $33.')
    assert [o.agent_id for o in st.history] == ['buyer', 'vendor']
    assert st.current_turn_agent_id == 'buyer' and st.current_round == 2
    assert eng.public_state(st)['human_turn'] is True


def test_ai_reaction_depends_on_the_offer_value():
    low = new(workflow='practice', b='collaborative'); eng.human_action(low.id, 'open', 33)
    high = new(workflow='practice', b='collaborative'); eng.human_action(high.id, 'open', 44)
    assert low.last_offer_by('vendor').value >= high.last_offer_by('vendor').value


def test_ai_accepts_a_good_offer_and_agreement_terms_are_the_users_offer():
    st = new(workflow='practice', b='collaborative')
    eng.human_action(st.id, 'open', 48)      # the user's own hard limit: very generous to the vendor
    assert st.status == NegotiationStatus.AGREED and st.final_value == 48 and st.final_agent_id == 'vendor'


def test_step_and_run_never_play_the_humans_turn():
    st = new(workflow='practice')
    try:
        orchestrator.step(st); raise AssertionError('expected error')
    except ValueError:
        pass
    eng.run_negotiation(st.id)
    assert len(st.history) == 0   # run stops immediately at the human's turn


def test_human_input_validation():
    st = new(workflow='practice')
    cases = [('open', None, ''), ('open', 'abc', ''), ('open', float('nan'), ''), ('open', -5, ''), ('open', 0, ''),
             ('open', 60, ''),            # violates buyer hard limit $48
             ('accept', None, ''),        # nothing to accept yet
             ('message', None, '   '), ('dance', 1, '')]
    for action, value, msg in cases:
        try:
            eng.human_action(st.id, action, value, message=msg); raise AssertionError((action, value))
        except ValueError:
            pass
    assert len(st.history) == 0 and st.current_round == 1  # invalid input never changes state


def test_human_cannot_accept_an_offer_that_violates_their_limit_or_go_backwards():
    st = new(workflow='practice'); eng.human_action(st.id, 'open', 36)
    ai_offer = st.last_offer_by('vendor').value
    assert ai_offer > 48
    try:
        eng.human_action(st.id, 'accept'); raise AssertionError('accept should be refused')
    except ValueError as e:
        assert 'hard limit' in str(e)
    try:
        eng.human_action(st.id, 'counter', 34); raise AssertionError('retreat should be refused')
    except ValueError as e:
        assert 'backwards' in str(e)


def test_human_can_accept_a_valid_offer_and_the_value_is_the_ais_offer():
    st = new(workflow='practice', b='collaborative')
    eng.human_action(st.id, 'open', 40)
    for v in (42, 44, 45, 46):
        if st.is_terminal(): break
        eng.human_action(st.id, 'counter', v)
    if not st.is_terminal():
        ai = st.last_offer_by('vendor').value
        if ai <= 48:
            eng.human_action(st.id, 'accept', 1)     # bogus typed value must be ignored
            assert st.final_value == ai
    assert st.is_terminal()


def test_human_reject_ends_negotiation_and_blocks_more_moves():
    st = new(workflow='practice'); eng.human_action(st.id, 'open', 33)
    eng.human_action(st.id, 'reject', message='Not workable.')
    assert st.status == NegotiationStatus.REJECTED and st.final_value is None
    try:
        eng.human_action(st.id, 'counter', 40); raise AssertionError('negotiation already ended')
    except ValueError:
        pass


def test_message_only_turn_lets_ai_open():
    st = new(workflow='practice'); eng.human_action(st.id, 'message', message='Hello, what is your best price?')
    assert [o.action.value for o in st.history] == ['message', 'open']
    assert st.current_round == 2 and st.history[0].source == 'human'


def test_extreme_lowball_gets_countered_first_then_rejected_by_a_firm_ai():
    st = new(workflow='practice', b='aggressive')
    eng.human_action(st.id, 'open', 1)
    assert not st.is_terminal() and st.history[-1].action.value == 'counter'    # round 1: still engages
    eng.human_action(st.id, 'counter', 1)
    assert st.status == NegotiationStatus.REJECTED


def test_repeated_offers_trigger_a_mediated_settlement_with_explanation():
    st = new(workflow='practice', b='aggressive', rounds=14)
    for _ in range(4):
        if st.is_terminal(): break
        eng.human_action(st.id, 'counter' if st.last_offer_by('buyer') else 'open', 34)
    assert st.is_terminal(), 'same offer three times must be caught well before max rounds'
    assert st.current_round <= 4
    dl = st.deadlock_info
    assert dl['triggered'] and dl['trigger'] == 'repeated_offers' and 'same offer' in dl['explanation']
    assert dl['resolution'] == 'mediated' and st.status == NegotiationStatus.AGREED and st.resolution_type == 'mediated'
    assert st.final_value == dl['mediated_value'] and st.agents[0].satisfies_limit(st.final_value) and st.agents[1].satisfies_limit(st.final_value)


def test_repeated_absurd_offers_end_in_a_declared_breakdown():
    st = new(workflow='practice', b='collaborative', rounds=14)
    for _ in range(5):
        if st.is_terminal(): break
        eng.human_action(st.id, 'counter' if st.last_offer_by('buyer') else 'open', 10)
    assert st.status == NegotiationStatus.DEADLOCK and st.final_value is None
    assert st.deadlock_info['resolution'] == 'breakdown' and 'no mutually feasible value' in st.outcome_reason
    an = eng.build_report(st.id)['analysis']
    assert an['status'] == 'deadlock' and any('Deadlock handling' in t for t in an['insights'])


def test_ai_calls_out_repeated_offers_and_concedes_less():
    fresh = new(workflow='practice', b='collaborative'); eng.human_action(fresh.id, 'open', 34)
    stubborn = new(workflow='practice', b='collaborative')
    eng.human_action(stubborn.id, 'open', 34); eng.human_action(stubborn.id, 'counter', 34)
    reply = stubborn.last_offer_by('vendor')
    assert 'same offer 2 times' in reply.rationale
    assert eng.public_state(stubborn)['repeat_streaks']['buyer'] == 1


def test_max_rounds_ends_practice_at_the_correct_round():
    st = new(workflow='practice', b='aggressive', rounds=2)
    eng.human_action(st.id, 'open', 33); eng.human_action(st.id, 'counter', 34)
    assert st.is_terminal() and st.current_round == 2 and st.status in (NegotiationStatus.MAX_ROUNDS, NegotiationStatus.DEADLOCK, NegotiationStatus.AGREED)


def test_all_scenarios_work_in_practice_mode():
    starts = {'vendor_pricing': 34, 'job_offer': 140000, 'project_budget': 130000}
    for sid, start in starts.items():
        st = eng.create_negotiation(sid, 'collaborative', 'collaborative', 'mock', 8, 'practice')
        eng.human_action(st.id, 'open', start)
        assert len(st.history) == 2 and st.history[1].agent_id == st.agents[1].id and st.history[1].source == 'mock'


def test_ai_private_limits_are_hidden_in_practice_until_the_end_but_visible_in_simulation():
    st = new(workflow='practice')
    ai = eng.public_state(st)['agents'][1]
    assert ai['limit'] is None and ai['target'] is None and 'Confidential' in ai['constraints']
    rep = eng.build_report(st.id)['agents'][1]
    assert 'hard_limit' not in rep
    eng.human_action(st.id, 'reject')
    assert eng.public_state(st)['agents'][1]['limit'] == 40
    assert eng.build_report(st.id)['agents'][1]['hard_limit'] == 40
    sim = new()
    assert eng.public_state(sim)['agents'][1]['limit'] == 40


def test_human_actions_are_refused_in_simulation_mode():
    st = new()
    try:
        eng.human_action(st.id, 'open', 33); raise AssertionError
    except ValueError:
        pass


# ───────────── Deadlock module ─────────────
def test_repeated_offer_trigger_is_reported():
    st = eng.run_negotiation(new('vendor_pricing', 'aggressive', 'aggressive', rounds=14).id)
    if st.deadlock_info['trigger'] != 'max_rounds':
        assert st.deadlock_info['resolution'] in ('mediated', 'breakdown')


def test_breakdown_when_no_midpoint_satisfies_both_limits():
    from models.state import NegotiationState, Offer, ActionType
    sc = get_scenario('vendor_pricing')
    a, b = sc.build_agent('buyer', Personality.AGGRESSIVE), sc.build_agent('vendor', Personality.AGGRESSIVE)
    st = NegotiationState('x', 'vendor_pricing', 8, [a, b], current_turn_agent_id=a.id)
    st.history = [Offer(3, 'buyer', ActionType.COUNTER, 30, 'r', 'mock'), Offer(3, 'vendor', ActionType.COUNTER, 45, 'r', 'mock')]
    st.stall_rounds = 2
    assert deadlock.resolve_if_deadlocked(st, a, b) and st.status == NegotiationStatus.DEADLOCK
    assert st.deadlock_info['resolution'] == 'breakdown' and st.deadlock_info['mediated_value'] is None


# ───────────── Analytics / Outcome / consistency ─────────────
def test_outcome_analysis_matches_the_raw_state():
    st = eng.run_negotiation(new('job_offer', 'collaborative', 'aggressive').id)
    r = eng.build_report(st.id)
    an = r['analysis']
    assert an['rounds_used'] == max(1, st.current_round) == r['rounds_used']
    assert an['events']['total_turns'] == len(st.history) == r['total_offers']
    for a in st.agents:
        recs = [c for c in st.concessions if c.agent_id == a.id]
        e = next(x for x in an['agents'] if x['id'] == a.id)
        assert e['concession_count'] + e['hold_count'] + e['retreat_count'] == len(recs)
        assert len(r['concessions'][a.id]) == len(recs)
    assert an['final_value'] == st.final_value and an['status'] == st.status.value
    if st.status == NegotiationStatus.AGREED:
        for e in an['agents']:
            a = next(x for x in st.agents if x.id == e['id'])
            assert e['satisfaction'] == a.satisfaction(st.final_value) and 0 <= e['satisfaction'] <= 100
        sh = an['surplus']['shares']
        assert math.isclose(sum(sh.values()), 100, abs_tol=.11)
    assert an['insights'] and all(isinstance(t, str) and t for t in an['insights'])


def test_no_agreement_means_zero_satisfaction_and_no_final_terms():
    st = new(workflow='practice'); eng.human_action(st.id, 'open', 33); eng.human_action(st.id, 'reject')
    an = eng.build_report(st.id)['analysis']
    assert an['status'] == 'rejected' and an['final_value'] is None and all(e['satisfaction'] == 0 for e in an['agents'])


def test_transcript_and_report_contain_required_sections():
    st = eng.run_negotiation(new('project_budget', 'risk_averse', 'collaborative').id)
    text, name = eng.transcript(st.id)
    for needle in ('NEGOTIATION TRANSCRIPT', 'PARTICIPANTS', 'Risk-Averse', 'Collaborative', 'Goal', 'Constraint', '── Round 1', 'FINAL OUTCOME',
                   'CONCESSION SUMMARY', st.id, 'Mock / rule-based engine', 'Reasoning'):
        assert needle in text, needle
    assert name.endswith('.txt')
    html, hname, mime = eng.report_document(st.id, 'html')
    for needle in ('Negotiation Report', 'Participants', 'Round-by-round timeline', 'Objective satisfaction', 'Deadlock information',
                   'Negotiation insights', 'Reasoning engine', 'Full transcript', '<svg', 'Project Budget Allocation'):
        assert needle.lower() in html.lower(), needle
    assert mime == 'text/html'
    import json
    j, _n, m = eng.report_document(st.id, 'json'); assert json.loads(j)['id'] == st.id and m == 'application/json'


def test_report_escapes_user_supplied_html():
    st = new(workflow='practice')
    eng.human_action(st.id, 'open', 33, message='<script>alert(1)</script>')
    html, _n, _m = eng.report_document(st.id, 'html')
    assert '<script>alert(1)</script>' not in html and '&lt;script&gt;' in html


def test_dashboard_stats_are_derived_from_sessions():
    eng.run_negotiation(new().id)
    d = eng.dashboard_stats()
    assert d['total_negotiations'] >= 1 and d['completed'] >= 1 and 0 <= d['agreement_rate_pct'] <= 100
    assert sum(d['status_breakdown'].values()) == d['completed']


# ───────────── HTTP API (all behind login) ─────────────
def _client():
    from tests.test_auth import logged_in_client
    return logged_in_client()


def test_api_requires_login_before_anything_else():
    c = app.test_client()
    assert c.post('/api/negotiations', json={}).status_code == 401
    assert c.get('/api/negotiations/missing').status_code == 401


def test_api_validation_errors():
    c, csrf, _ = _client()
    h = {'X-CSRF-Token': csrf}
    assert c.post('/api/negotiations', json={}, headers=h).status_code == 400
    assert c.post('/api/negotiations', json={'scenario_id': 'nope', 'personality_a': 'aggressive', 'personality_b': 'aggressive'}, headers=h).status_code == 400
    assert c.post('/api/negotiations', json={'scenario_id': 'vendor_pricing', 'personality_a': 'wild', 'personality_b': 'aggressive'}, headers=h).status_code == 400
    bad_rounds = c.post('/api/negotiations', json={'scenario_id': 'vendor_pricing', 'personality_a': 'aggressive', 'personality_b': 'aggressive', 'max_rounds': 'x'}, headers=h)
    assert bad_rounds.status_code == 400
    assert c.post('/api/negotiations', json={'scenario_id': 'vendor_pricing', 'personality_a': 'aggressive', 'personality_b': 'aggressive', 'max_rounds': 999}, headers=h).status_code == 400
    assert c.post('/api/negotiations', data='not json', content_type='application/json', headers=h).status_code == 400
    assert c.get('/api/negotiations/missing').status_code == 404
    assert c.post('/api/negotiations/missing/step', headers=h).status_code == 404
    assert c.get('/api/negotiations/missing/report').status_code == 404
    assert c.get('/api/negotiations/missing/transcript').status_code == 404


def test_api_practice_flow_and_downloads():
    c, csrf, _ = _client()
    h = {'X-CSRF-Token': csrf}
    r = c.post('/api/negotiations', json={'scenario_id': 'vendor_pricing', 'personality_a': 'collaborative', 'personality_b': 'risk_averse',
                                          'workflow_mode': 'practice', 'mode': 'mock', 'max_rounds': 6}, headers=h)
    assert r.status_code == 201
    i = r.get_json()['id']
    assert c.post(f'/api/negotiations/{i}/step', headers=h).status_code == 409                    # AI may not play the human's turn
    assert c.post(f'/api/negotiations/{i}/human-action', json={'action': 'open', 'value': 'abc'}, headers=h).status_code == 400
    ok = c.post(f'/api/negotiations/{i}/human-action', json={'action': 'open', 'value': 34, 'message': 'Opening offer.'}, headers=h)
    assert ok.status_code == 200 and len(ok.get_json()['history']) == 2 and ok.get_json()['human_turn'] is True
    assert ok.get_json()['agents'][1]['limit'] is None
    c.post(f'/api/negotiations/{i}/human-action', json={'action': 'reject'}, headers=h)
    t = c.get(f'/api/negotiations/{i}/transcript')
    assert t.status_code == 200 and 'attachment' in t.headers['Content-Disposition'] and b'FINAL OUTCOME' in t.data
    rep = c.get(f'/api/negotiations/{i}/report/download')
    assert rep.status_code == 200 and rep.mimetype == 'text/html' and b'Negotiation Report' in rep.data
    assert c.get(f'/api/negotiations/{i}/report/download?format=pdf').status_code == 400
    assert c.get(f'/api/negotiations/{i}/report/download?format=json').mimetype == 'application/json'


def test_api_simulation_run_and_status_never_expose_keys():
    with mock.patch.dict(os.environ, {'GROQ_API_KEY': 'gsk_supersecretvalue123'}):
        c = app.test_client()
        s = c.get('/api/llm/status'); assert b'supersecret' not in s.data and s.get_json()['configured'] is True
        assert b'supersecret' not in c.get('/api/health').data
    with _clear_keys():
        c, csrf, _ = _client()
        h = {'X-CSRF-Token': csrf}
        i = c.post('/api/negotiations', json={'scenario_id': 'job_offer', 'personality_a': 'aggressive', 'personality_b': 'collaborative'}, headers=h).get_json()['id']
        done = c.post(f'/api/negotiations/{i}/run', headers=h).get_json()
        assert done['status'] in ('agreed', 'max_rounds_reached', 'deadlock', 'rejected')
        assert c.post(f'/api/negotiations/{i}/step', headers=h).get_json()['history'] == done['history']


def test_frontend_is_served_and_has_no_secrets():
    c = app.test_client()
    assert c.get('/').status_code == 200 and c.get('/outcome.html').status_code == 200
    assert c.get('/../backend/app.py').status_code == 404 and c.get('/.env').status_code == 404


def test_concurrent_step_requests_never_duplicate_or_skip_turns():
    import threading
    st = new('job_offer', 'collaborative', 'collaborative')
    threads = [threading.Thread(target=eng.step_negotiation, args=(st.id,)) for _ in range(8)]
    [t.start() for t in threads]; [t.join() for t in threads]
    who = [o.agent_id for o in st.history]
    assert len(who) == len(set(range(len(who)))) and all(a != b for a, b in zip(who, who[1:]))
    assert who[0] == st.agents[0].id and len(who) == 8 or st.is_terminal()


def test_product_naming_is_consistent():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    checked = 0
    for folder, _d, files in os.walk(root):
        if any(x in folder for x in ('.venv', '__pycache__', '.pytest_cache', 'tests')):
            continue
        for f in files:
            if f.endswith(('.html', '.js', '.css', '.md', '.py')):
                text = open(os.path.join(folder, f), encoding='utf-8').read().lower()
                assert 'arena' not in text, f'legacy wording in {f}'
                assert 'the table' not in text.replace('off the table', '').replace('on the table', ''), f'old brand in {f}'
                checked += 1
    assert checked >= 15
    html = open(os.path.join(root, 'frontend', 'negotiation.html'), encoding='utf-8').read()
    assert 'Negotiation Area' in html and 'AI Multi-Agent Negotiation Platform' in html


# ───────────── Negotiation Certificate ─────────────
def test_certificate_requires_a_terminal_negotiation():
    c, csrf, _ = _client()
    h = {'X-CSRF-Token': csrf}
    r = c.post('/api/negotiations', json={'scenario_id': 'vendor_pricing', 'personality_a': 'aggressive', 'personality_b': 'collaborative'}, headers=h)
    i = r.get_json()['id']
    assert c.get(f'/api/negotiations/{i}/certificate').status_code == 409
    c.post(f'/api/negotiations/{i}/run', headers=h)
    ok = c.get(f'/api/negotiations/{i}/certificate')
    assert ok.status_code == 200 and 'attachment' in ok.headers['Content-Disposition']
    assert b'Certificate of Negotiation' in ok.data and b'Orchestrator-Verified' in ok.data


def test_certificate_reflects_actual_outcome_and_escapes_input():
    st = new(workflow='practice')
    eng.human_action(st.id, 'open', 33, message='<b>hi</b>')
    eng.human_action(st.id, 'reject')
    html, name = eng.certificate(st.id)
    assert 'No Agreement' in html and name.endswith('.html')
    assert '<b>hi</b>' not in html
    agreed = eng.run_negotiation(new('job_offer', 'collaborative', 'collaborative').id)
    html2, _ = eng.certificate(agreed.id)
    assert 'Agreement Certified' in html2 and f'{agreed.final_value:,.2f}' in html2

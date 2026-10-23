"""Facade used by the Flask API: session store, locking, public (redacted)
serialisation, human actions, dashboard statistics and report assembly."""
import threading
import uuid
from models.state import NegotiationState, Personality, NegotiationStatus, now
from models.scenarios import get_scenario
from llm import provider
from llm.schema import AgentDecision
from engine import orchestrator, analytics, offer_evaluator, reporting, deadlock, gamification, assistant_context

_STORE = {}
_LOCKS = {}
_GUARD = threading.Lock()
MAX_ROUNDS_LIMIT = 20
MIN_ROUNDS = 2


def _lock(i):
    with _GUARD:
        return _LOCKS.setdefault(i, threading.RLock())


def create_negotiation(scenario_id, personality_a, personality_b, mode='mock', max_rounds=None, workflow_mode='simulation',
                       llm_provider=None, llm_model=None, owner_id=None, owner_username=None, allow_fallback=True):
    s = get_scenario(scenario_id)
    try:
        pa, pb = Personality(personality_a), Personality(personality_b)
    except ValueError:
        raise ValueError('personality must be one of: ' + ', '.join(p.value for p in Personality))
    if max_rounds is not None and not (MIN_ROUNDS <= int(max_rounds) <= MAX_ROUNDS_LIMIT):
        raise ValueError(f'max_rounds must be between {MIN_ROUNDS} and {MAX_ROUNDS_LIMIT}')
    if workflow_mode not in ('simulation', 'practice'):
        raise ValueError('workflow_mode must be "simulation" or "practice"')
    if mode not in ('mock', 'llm'):
        raise ValueError('mode must be "mock" or "llm"')
    effective, pid, model, notice = provider.resolve(mode, llm_provider, llm_model)
    if effective == 'llm':
        model = provider.preflight(pid, model)     # one real request: fail now, clearly, instead of silently degrading later
    a, b = s.build_agent(s.side_a.id, pa), s.build_agent(s.side_b.id, pb)
    st = NegotiationState(uuid.uuid4().hex[:10], scenario_id, int(max_rounds or s.default_max_rounds), [a, b],
                          current_turn_agent_id=a.id, mode=effective, workflow_mode=workflow_mode)
    st.mode_requested, st.mode_notice, st.llm_provider, st.llm_model = mode, notice, pid, model
    st.owner_id, st.owner_username = owner_id, owner_username
    st.llm_allow_fallback = bool(allow_fallback)
    _STORE[st.id] = st
    return st


def get_negotiation(i):
    return _STORE.get(i)


def _need(i):
    st = get_negotiation(i)
    if not st:
        raise KeyError('negotiation not found')
    return st


def public_state(st):
    """State as sent to the browser. In Practice Mode the AI counterpart's private
    numbers stay hidden until the negotiation is over."""
    d = st.to_dict()
    d['human_turn'] = orchestrator.is_human_turn(st)
    d['repeat_streaks'] = {a.id: deadlock.repeat_streak(st, a.id) for a in st.agents}
    if not analytics.reveal_private(st):
        for a in d['agents'][1:]:
            a['opening'] = a['target'] = a['limit'] = None
            a['constraints'] = 'Confidential until the negotiation ends.'
    return d


def list_negotiations(owner_id):
    """Only the given owner's own sessions — never platform-wide. (Aggregate,
    anonymous platform stats are available separately via dashboard_stats().)"""
    out = []
    for st in sorted(_STORE.values(), key=lambda x: x.created_at, reverse=True):
        if st.owner_id != owner_id:
            continue
        s = get_scenario(st.scenario_id)
        out.append({'id': st.id, 'scenario_id': st.scenario_id, 'scenario_name': s.name, 'status': st.status.value,
                    'mode': st.mode, 'workflow_mode': st.workflow_mode, 'rounds_used': max(1, st.current_round),
                    'max_rounds': st.max_rounds, 'final_value': st.final_value, 'unit': s.unit,
                    'agents': [{'id': a.id, 'role_label': a.role_label, 'personality': a.personality.value} for a in st.agents],
                    'created_at': st.created_at})
    return out


def rename_owner(owner_id, username):
    """Keep leaderboard/profile names in step with an account's new username."""
    with _GUARD:
        for st in _STORE.values():
            if st.owner_id == owner_id:
                st.owner_username = username


def delete_owner_data(owner_id):
    """Account deletion: remove every negotiation the account owns. Returns how many."""
    with _GUARD:
        ids = [i for i, st in _STORE.items() if st.owner_id == owner_id]
        for i in ids:
            _STORE.pop(i, None)
            _LOCKS.pop(i, None)
    return len(ids)


def export_owner_data(owner_id):
    return [public_state(_STORE[x['id']]) for x in list_negotiations(owner_id)]


def read_only_context(i):
    """A detached, read-only description of a negotiation for the Assistant (None if unknown).
    Takes the negotiation's lock only so the snapshot is consistent; changes nothing."""
    st = get_negotiation(i)
    if not st:
        return None
    with _lock(i):
        return assistant_context.negotiation_context(st)


def owns(negotiation_id, owner_id):
    st = get_negotiation(negotiation_id)
    return bool(st and owner_id and st.owner_id == owner_id)


def dashboard_stats():
    xs = list(_STORE.values())
    terminal = [x for x in xs if x.is_terminal()]
    agreed = [x for x in terminal if x.status == NegotiationStatus.AGREED]
    sats = []
    for x in agreed:
        sats += [a['satisfaction'] for a in analytics.analyze(x, get_scenario(x.scenario_id))['agents'] if a['satisfaction'] is not None]
    breakdown = {}
    for x in terminal:
        breakdown[x.status.value] = breakdown.get(x.status.value, 0) + 1
    return {'total_negotiations': len(xs), 'completed': len(terminal), 'agreements': len(agreed),
            'agreement_rate_pct': round(len(agreed) / len(terminal) * 100, 1) if terminal else 0,
            'avg_rounds': round(sum(max(1, x.current_round) for x in terminal) / len(terminal), 1) if terminal else 0,
            'llm_runs': sum(x.llm_calls > 0 for x in xs), 'fallbacks': sum(x.fallback_count for x in xs),
            'active': sum(not x.is_terminal() for x in xs), 'simulations': sum(x.workflow_mode == 'simulation' for x in xs),
            'practice_sessions': sum(x.workflow_mode == 'practice' for x in xs),
            'avg_satisfaction': round(sum(sats) / len(sats), 1) if sats else None, 'status_breakdown': breakdown}


def _practice_analyses_for(owner_id):
    """(score, analysis, human_id) for every completed Practice Mode negotiation
    owned by this user — the only sessions that reflect the user's own play."""
    out = []
    for st in _STORE.values():
        if st.owner_id != owner_id or st.workflow_mode != 'practice' or not st.is_terminal():
            continue
        an = analytics.analyze(st, get_scenario(st.scenario_id))
        human_id = st.agents[0].id
        score = gamification.negotiation_skill_score(an, human_id)
        out.append((score, an))
    return out


def _simulation_analyses_for(owner_id):
    return [analytics.analyze(st, get_scenario(st.scenario_id)) for st in _STORE.values()
            if st.owner_id == owner_id and st.workflow_mode == 'simulation' and st.is_terminal()]


def user_gamification(owner_id):
    profile = gamification.user_profile(_practice_analyses_for(owner_id))
    profile['simulation'] = gamification.simulation_summary(_simulation_analyses_for(owner_id))
    return profile


def leaderboard(limit=10):
    """Username + aggregate score only — never negotiation IDs or content, so one
    user's ranking can never be used to browse another user's sessions."""
    by_owner = {}
    for st in _STORE.values():
        if st.owner_id and st.workflow_mode == 'practice':
            by_owner.setdefault(st.owner_id, st.owner_username)
    rows = []
    for owner_id, username in by_owner.items():
        profile = user_gamification(owner_id)
        if profile['completed']:
            rows.append({'username': username, 'average_score': profile['average_score'],
                        'best_score': profile['best_score'], 'completed': profile['completed'],
                        'badge_count': len(profile['badges'])})
    rows.sort(key=lambda r: (-r['average_score'], -r['badge_count']))
    return rows[:limit]


def step_negotiation(i):
    st = _need(i)
    with _lock(i):
        return orchestrator.step(st)


def run_negotiation(i):
    st = _need(i)
    with _lock(i):
        return orchestrator.run(st)


def human_action(i, action, value=None, rationale=None, message='', respond=True):
    """A Practice Mode move by the human (Agent A). The AI's reply is produced in
    the same request so the state can never be left half-way through a round."""
    st = _need(i)
    with _lock(i):
        if st.workflow_mode != 'practice':
            raise ValueError('Human actions are only available in Practice Mode.')
        if st.is_terminal():
            raise ValueError('This negotiation has already ended.')
        if not orchestrator.is_human_turn(st):
            raise ValueError('Practice Mode is waiting for the AI participant.')
        action = str(action or '').strip().lower()
        if action not in ('open', 'counter', 'accept', 'reject', 'message'):
            raise ValueError('Unknown action. Use open, counter, accept, reject or message.')
        a, opp = st.agents[0], st.agents[1]
        msg = (message or '').strip()[:1000]
        if st.status == NegotiationStatus.NOT_STARTED:
            st.status, st.started_at = NegotiationStatus.IN_PROGRESS, now()
        own, oo = st.last_offer_by(a.id), st.last_offer_by(opp.id)
        if action == 'message':
            if not msg:
                raise ValueError('Write a message before sending.')
            d, corrected, note = AgentDecision('message', None, msg, .99, 'human'), False, None
        else:
            if action in ('open', 'counter'):
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    raise ValueError('Enter a valid numeric amount for your proposal.')
            elif action == 'accept' and oo is None:
                raise ValueError('There is no offer from the AI to accept yet. Make an offer or send a message first.')
            fallback_text = {'accept': 'Human participant accepted the proposal.', 'reject': 'Human participant rejected the proposal.'}.get(action, 'Human participant submitted a proposal.')
            raw = AgentDecision(action, value, msg or fallback_text, .99, 'human')
            d, corrected, note = offer_evaluator.validate(a, raw, oo.value if oo else None, own.value if own else None, strict=True)
        if corrected:
            st.orchestrator_corrections += 1
        orchestrator.apply_turn(st, a, d, corrected, note, message=msg or None, source='human')
        if respond and not st.is_terminal() and not orchestrator.is_human_turn(st):
            orchestrator.step(st)
        return st


def build_report(i):
    st = _need(i)
    s = get_scenario(st.scenario_id)
    an = analytics.analyze(st, s)
    pub = public_state(st)
    human_id = st.agents[0].id if st.workflow_mode == 'practice' else None
    skill_score = gamification.negotiation_skill_score(an, human_id) if human_id else None
    outcome = gamification.evaluate_outcome(an, human_id)       # same evaluator for Practice and Simulation
    return {
        'id': st.id, 'scenario': s.name, 'scenario_id': s.id, 'scenario_description': s.description, 'issue_label': s.issue_label,
        'context': s.total_context, 'unit': s.unit, 'status': st.status.value, 'final_value': st.final_value,
        'rounds_used': max(1, st.current_round), 'max_rounds': st.max_rounds, 'total_offers': len(st.history),
        'outcome_reason': st.outcome_reason, 'mode': st.mode, 'workflow_mode': st.workflow_mode, 'llm_calls': st.llm_calls,
        'fallback_count': st.fallback_count, 'orchestrator_corrections': st.orchestrator_corrections,
        'created_at': st.created_at, 'started_at': st.started_at, 'completed_at': st.completed_at,
        'agents': an['agents'], 'analysis': an, 'skill_score': skill_score, 'outcome': outcome,
        'concessions': {a.id: [c.to_dict() for c in st.concessions if c.agent_id == a.id] for a in st.agents},
        'history': pub['history'],
    }


def transcript(i):
    st = _need(i)
    s = get_scenario(st.scenario_id)
    return reporting.transcript_text(st, s, analytics.analyze(st, s)), f'negotiation-transcript-{st.scenario_id}-{st.id}.txt'


def certificate(i):
    st = _need(i)
    s = get_scenario(st.scenario_id)
    an = analytics.analyze(st, s)
    return reporting.certificate_html(st, s, an), f'negotiation-certificate-{st.scenario_id}-{st.id}.html'


def report_document(i, fmt='html'):
    st = _need(i)
    s = get_scenario(st.scenario_id)
    an = analytics.analyze(st, s)
    if fmt == 'json':
        import json
        return json.dumps(build_report(i), indent=2), f'negotiation-report-{st.scenario_id}-{st.id}.json', 'application/json'
    return reporting.report_html(st, s, an), f'negotiation-report-{st.scenario_id}-{st.id}.html', 'text/html'

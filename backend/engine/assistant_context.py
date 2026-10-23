"""Read-only views of the platform for the Negotiation Assistant.

These functions only READ a negotiation and return brand-new plain dictionaries
(no references to engine objects), so whatever receives them can explain the
negotiation but has no handle with which to change it. Confidential numbers follow
exactly the same redaction rules as the rest of the application: in Practice Mode the
AI participant's target / limit / opening stay hidden until the negotiation ends."""
from engine import analytics, gamification
from models.agents import PERSONALITY_PARAMS
from models.scenarios import SCENARIOS, get_scenario

MAX_HISTORY = 40
MAX_TEXT = 300


def _clip(text):
    text = (text or '').strip()
    return text if len(text) <= MAX_TEXT else text[:MAX_TEXT - 1] + '…'


def platform_facts():
    """Static knowledge about the platform (not tied to any negotiation)."""
    return {
        'personalities': [{'id': k.value, 'label': v['label'], 'style': v['style']} for k, v in PERSONALITY_PARAMS.items()],
        'scenarios': [{'id': s.id, 'name': s.name, 'description': s.description, 'issue': s.issue_label,
                       'roles': [s.side_a.role_label, s.side_b.role_label], 'default_max_rounds': s.default_max_rounds}
                      for s in SCENARIOS.values()],
        'badges': [{'id': k, 'label': v['label'], 'description': v['desc']} for k, v in gamification.BADGES.items()],
        'outcomes': dict(gamification.OUTCOMES),
    }


def negotiation_context(st):
    """Everything about ONE negotiation that the assistant may see."""
    scenario = get_scenario(st.scenario_id)
    an = analytics.analyze(st, scenario)                       # applies the Practice Mode redaction
    role = {a.id: a.role_label for a in st.agents}
    practice = st.workflow_mode == 'practice'
    agents = []
    for e in an['agents']:
        item = {'role': e['role'], 'controlled_by': e['controlled_by'], 'personality': e['personality_label'],
                'personality_id': None if e['controlled_by'] == 'human' else e['personality'],
                'goal': e.get('goals'), 'objective': e.get('objective'),
                'offers_made': e['offers_made'], 'concessions': e['concession_count'], 'holds': e['hold_count'],
                'retreats': e['retreat_count'], 'average_step_pct_of_range': e['avg_step_pct'], 'last_position': e['last_position']}
        for key, name in (('constraints', 'constraint'), ('target', 'target'), ('hard_limit', 'hard_limit'), ('opening_value', 'opening_value')):
            if key in e:                                       # absent while hidden from the user
                item[name] = e[key]
        agents.append(item)
    latest = {}
    for o in st.history:
        if o.value is not None and o.action.value in ('open', 'counter'):
            latest[role[o.agent_id]] = o.value
    values = list(latest.values())
    history = [{'round': o.round, 'who': role[o.agent_id], 'action': o.action.value, 'value': o.value,
                'message': _clip(o.message), 'reasoning': _clip(o.rationale), 'source': o.source,
                'orchestrator_correction': _clip(o.correction_note)} for o in st.history[-MAX_HISTORY:]]
    moves = [{'round': c.round, 'who': role[c.agent_id], 'kind': c.kind, 'moved_by': c.delta, 'pct_of_range': c.pct_of_range}
             for c in st.concessions[-MAX_HISTORY:]]
    ctx = {
        'available': True,
        'mode': 'Practice Mode (human vs AI)' if practice else 'Simulation Mode (AI vs AI)',
        'engine': an['llm']['engine_label'],
        'scenario': {'name': scenario.name, 'description': scenario.description, 'issue': scenario.issue_label,
                     'unit': scenario.unit, 'context': scenario.total_context},
        'agents': agents,
        'status': an['status_label'], 'finished': an['terminal'], 'round': max(1, st.current_round), 'max_rounds': st.max_rounds,
        'whose_turn': None if an['terminal'] else role.get(st.current_turn_agent_id),
        'latest_offers': latest, 'gap_between_latest_offers': round(abs(values[0] - values[1]), 2) if len(values) == 2 else None,
        'transcript': history, 'transcript_truncated': len(st.history) > MAX_HISTORY,
        'concession_log': moves,
        'deadlock': {k: an['deadlock'].get(k) for k in ('trigger', 'resolution', 'explanation', 'mediated_value')} if an['deadlock'] else None,
        'stalled_rounds': an['stall_rounds'],
        'private_numbers_hidden': practice and not an['terminal'],
    }
    if an['terminal']:
        human_id = st.agents[0].id if practice else None
        ev = gamification.evaluate_outcome(an, human_id)
        ctx['result'] = {'final_value': an['final_display'], 'how_it_closed': an['resolution_label'], 'reason': _clip(an['outcome_reason']),
                         'outcome': ev['label'], 'score': ev['score'], 'score_basis': ev['score_basis'],
                         'badges': [b['label'] for b in ev['badges']],
                         'satisfaction': {e['role']: e['satisfaction'] for e in an['agents']},
                         'analytics': [_clip(t) for t in an['insights'][:8]]}
    return ctx


def setup_context(setup):
    """The scenario / personalities the user has selected but not yet started. Only validated, public
    information is returned (never limits, targets or constraints), and nothing is created or stored."""
    if not isinstance(setup, dict) or setup.get('scenario_id') not in SCENARIOS:
        return None
    scenario = SCENARIOS[setup['scenario_id']]
    practice = setup.get('workflow_mode') == 'practice'
    labels = {k.value: v for k, v in PERSONALITY_PARAMS.items()}
    sides = []
    for idx, side in enumerate((scenario.side_a, scenario.side_b)):
        pid = setup.get('personality_a' if idx == 0 else 'personality_b')
        human = practice and idx == 0
        entry = {'role': side.role_label, 'controlled_by': 'you' if human else 'AI agent', 'goal': side.goals, 'objective': side.objective}
        if not human and pid in labels:
            entry.update(personality=labels[pid]['label'], personality_style=labels[pid]['style'])
        sides.append(entry)
    return {'phase': 'setup (negotiation not started yet)',
            'mode': 'Practice Mode (you play the first side against an AI agent)' if practice else 'Simulation Mode (two AI agents negotiate)',
            'scenario': {'name': scenario.name, 'description': scenario.description, 'issue': scenario.issue_label,
                         'unit': scenario.unit, 'context': scenario.total_context, 'default_max_rounds': scenario.default_max_rounds},
            'sides': sides}

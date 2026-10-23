"""Negotiation Analytics: every number and sentence here is derived from the
recorded negotiation state (history, concessions, agents, deadlock info)."""
from models.state import ActionType, Direction
from models.agents import PERSONALITY_LABELS, PERSONALITY_PARAMS
from models.units import format_amount

STATUS_LABELS = {
    'not_started': 'Not Started', 'in_progress': 'In Progress', 'agreed': 'Agreement Reached',
    'rejected': 'Rejected', 'deadlock': 'Deadlock', 'completed': 'Completed', 'max_rounds_reached': 'Maximum Rounds Reached',
}
RESOLUTION_LABELS = {'negotiated': 'Accepted by a party', 'convergence': 'Positions converged', 'mediated': 'Orchestrator-mediated settlement'}


def money(v, unit='$'):
    return format_amount(v, unit)


def is_human(state, agent):
    return state.workflow_mode == 'practice' and agent.id == state.agents[0].id


def reveal_private(state):
    """Private targets/limits stay hidden from a Practice Mode player until the negotiation ends."""
    return state.workflow_mode != 'practice' or state.is_terminal()


def _behavior(avg_pct):
    return 'small, guarded steps' if avg_pct < 5 else 'moderate steps' if avg_pct < 12 else 'large steps'


def analyze(state, scenario):
    unit = scenario.unit
    terminal = state.is_terminal()
    agreed = state.status.value == 'agreed'
    reveal = reveal_private(state)
    by_id = {a.id: a for a in state.agents}
    role = lambda aid: by_id[aid].role_label if aid in by_id else '—'

    # ---- per-agent statistics ------------------------------------------------
    agents = []
    for a in state.agents:
        recs = [c for c in state.concessions if c.agent_id == a.id]
        moves = [o for o in state.history if o.agent_id == a.id and o.action in (ActionType.OPEN, ActionType.COUNTER)]
        conceded_total = sum(max(c.conceded, 0) for c in recs)
        total_pct = round(conceded_total / a.range_span() * 100, 1)
        avg_pct = round(total_pct / len(recs), 1) if recs else 0.0
        largest = max([c.pct_of_range for c in recs if c.kind == 'concession'] or [0.0])
        sat = a.satisfaction(state.final_value) if agreed else (0.0 if terminal else None)
        target_met = None
        if agreed:
            target_met = (state.final_value >= a.target) if a.direction == Direction.MAXIMIZE else (state.final_value <= a.target)
        entry = {
            'id': a.id, 'role': a.role_label, 'personality': a.personality.value,
            'personality_label': 'Human-directed' if is_human(state, a) else PERSONALITY_LABELS[a.personality.value],
            'controlled_by': 'human' if is_human(state, a) else 'ai', 'direction': a.direction.value,
            'offers_made': len(moves), 'opening_position': moves[0].value if moves else None,
            'last_position': moves[-1].value if moves else None,
            'concession_count': sum(1 for c in recs if c.kind == 'concession'),
            'hold_count': sum(1 for c in recs if c.kind == 'hold'),
            'retreat_count': sum(1 for c in recs if c.kind == 'retreat'),
            'total_conceded': round(conceded_total, 2), 'total_conceded_pct': total_pct,
            'avg_step_pct': avg_pct, 'largest_step_pct': round(largest, 1),
            'observed_behavior': _behavior(avg_pct) if recs else 'no movement recorded',
            'satisfaction': sat, 'target_met': target_met,
            'final_position': state.final_value if agreed else (moves[-1].value if moves else None),
        }
        entry.update(target=a.target, hard_limit=a.limit, opening_value=a.opening, goals=a.goals, constraints=a.constraints, objective=a.objective)
        agents.append(entry)
    if not reveal:   # Practice Mode in progress: never expose the AI's private numbers
        for e in agents:
            if e['controlled_by'] == 'ai':
                for k in ('target', 'hard_limit', 'opening_value', 'constraints'):
                    e.pop(k, None)

    # ---- timeline (round by round) -------------------------------------------
    rec_by = {(c.agent_id, c.round): c for c in state.concessions}
    rounds = {}
    for o in state.history:
        c = rec_by.get((o.agent_id, o.round)) if o.action in (ActionType.OPEN, ActionType.COUNTER) else None
        rounds.setdefault(o.round, []).append({
            'agent_id': o.agent_id, 'role': role(o.agent_id), 'action': o.action.value, 'value': o.value,
            'message': o.message, 'rationale': o.rationale, 'source': o.source, 'stance': o.stance,
            'moved_by': c.delta if c else None, 'move_pct': c.pct_of_range if c else None, 'move_kind': c.kind if c else None,
            'corrected': o.corrected, 'correction_note': o.correction_note, 'timestamp': o.timestamp})
    timeline = [{'round': r, 'entries': rounds[r]} for r in sorted(rounds)]
    series = {a.id: [{'round': o.round, 'value': o.value, 'index': i}
                     for i, o in enumerate(state.history) if o.agent_id == a.id and o.action in (ActionType.OPEN, ActionType.COUNTER)]
              for a in state.agents}

    # ---- counts ---------------------------------------------------------------
    count = lambda act: sum(1 for o in state.history if o.action.value == act)
    events = {'openings': count('open'), 'counteroffers': count('counter'), 'accepts': count('accept'), 'rejects': count('reject'),
              'messages': count('message'), 'corrections': state.orchestrator_corrections, 'total_turns': len(state.history)}

    # ---- bargaining surplus ---------------------------------------------------
    surplus = None
    if reveal:
        mx = next((a for a in state.agents if a.direction == Direction.MAXIMIZE), None)
        mn = next((a for a in state.agents if a.direction == Direction.MINIMIZE), None)
        if mx and mn and mx.limit <= mn.limit:
            lo, hi = mx.limit, mn.limit
            surplus = {'zone_low': lo, 'zone_high': hi, 'width': hi - lo, 'shares': None}
            if agreed:
                share_mx = 50.0 if hi == lo else round((state.final_value - lo) / (hi - lo) * 100, 1)
                surplus['shares'] = {mx.id: share_mx, mn.id: round(100 - share_mx, 1)}

    joint = None
    if agreed and len(agents) == 2 and all(a['satisfaction'] is not None for a in agents):
        s0, s1 = agents[0]['satisfaction'], agents[1]['satisfaction']
        joint = {'average_satisfaction': round((s0 + s1) / 2, 1), 'balance': round(100 - abs(s0 - s1), 1)}

    # ---- LLM / engine ---------------------------------------------------------
    ai_turns = [o for o in state.history if o.source in ('llm', 'mock', 'fallback')]
    if state.mode == 'llm' and state.llm_calls > 0 and state.fallback_count == 0:
        label = 'Real LLM'
    elif state.mode == 'llm' and state.fallback_count:
        label = f'Real LLM with {state.fallback_count} rule-based fallback turn{"s" if state.fallback_count != 1 else ""}'
    else:
        label = 'Mock / Rule-Based engine (no LLM used)'
    llm = {'mode': state.mode, 'requested_mode': state.mode_requested, 'provider': state.llm_provider, 'model': state.llm_model,
           'llm_calls': state.llm_calls, 'fallback_turns': state.fallback_count, 'ai_turns': len(ai_turns),
           'engine_label': label, 'notice': state.mode_notice, 'last_error': state.last_error}

    result = {
        'status': state.status.value, 'status_label': STATUS_LABELS[state.status.value], 'terminal': terminal,
        'final_value': state.final_value, 'final_display': money(state.final_value, unit) if state.final_value is not None else None,
        'resolution_type': state.resolution_type, 'resolution_label': RESOLUTION_LABELS.get(state.resolution_type or '', None),
        'final_agent_id': state.final_agent_id, 'final_agent_role': role(state.final_agent_id) if state.final_agent_id else None,
        'outcome_reason': state.outcome_reason, 'rounds_used': max(1, state.current_round), 'max_rounds': state.max_rounds,
        'agents': agents, 'timeline': timeline, 'series': series, 'events': events, 'surplus': surplus, 'joint': joint,
        'deadlock': state.deadlock_info, 'stall_rounds': state.stall_rounds, 'llm': llm,
    }
    result['insights'] = _insights(state, scenario, result)
    return result


def _insights(state, scenario, r):
    """Plain-language findings, each computed from the recorded data above."""
    out, unit = [], scenario.unit
    a0, a1 = r['agents'][0], r['agents'][1]
    ev = r['events']
    who = lambda a: 'You' if a['controlled_by'] == 'human' else a['role']

    if not r['terminal']:
        out.append('The negotiation is still in progress; insights are provisional until it ends.')
    elif r['status'] == 'agreed':
        how = {'negotiated': f'{r["final_agent_role"]} accepted the other side\'s proposal' if r['final_agent_role'] else 'a party accepted the proposal',
               'convergence': 'the two proposals converged inside both parties\' limits',
               'mediated': 'the Orchestrator mediated the deadlock at the midpoint of the stalled offers'}.get(r['resolution_type'], 'the parties agreed')
        out.append(f'An agreement was reached at {r["final_display"]} in round {r["rounds_used"]} of {r["max_rounds"]}: {how}.')
    else:
        out.append(f'No agreement was reached after {r["rounds_used"]} of {r["max_rounds"]} rounds ({r["status_label"].lower()}).')

    if r['terminal']:
        if a0['concession_count'] + a1['concession_count'] > 0:
            more, less = (a0, a1) if a0['total_conceded_pct'] >= a1['total_conceded_pct'] else (a1, a0)
            if abs(a0['total_conceded_pct'] - a1['total_conceded_pct']) < 2:
                out.append(f'Both sides conceded a similar share of their range ({a0["total_conceded_pct"]}% vs {a1["total_conceded_pct"]}%).')
            else:
                out.append(f'{who(more)} conceded {more["total_conceded_pct"]}% of {"your" if more["controlled_by"]=="human" else "its"} bargaining range over {more["concession_count"]} move(s), '
                           f'compared with {less["total_conceded_pct"]}% by {who(less)} - {who(less)} held firmer.')
        else:
            out.append('Neither side changed its position after the first offers, so no concessions were recorded.')

        ais = [a for a in (a0, a1) if a['controlled_by'] != 'human' and a['concession_count'] + a['hold_count'] + a['retreat_count'] > 0]
        if len(ais) == 2:
            x, y = ais
            if x['personality'] == y['personality']:
                out.append(f'Both agents were {x["personality_label"]}: {x["role"]} averaged {x["avg_step_pct"]}% of its range per move and {y["role"]} {y["avg_step_pct"]}%.')
            else:
                rank = {k.value: v['rate'] for k, v in PERSONALITY_PARAMS.items()}   # expected: smaller steps -> larger steps
                exp_first = x if rank[x['personality']] < rank[y['personality']] else y
                obs_first = x if x['avg_step_pct'] < y['avg_step_pct'] else y
                a_, b_ = exp_first, (y if exp_first is x else x)
                if abs(x['avg_step_pct'] - y['avg_step_pct']) < .5:
                    out.append(f'{x["role"]} ({x["personality_label"]}) and {y["role"]} ({y["personality_label"]}) moved in similar-sized steps ({x["avg_step_pct"]}% vs {y["avg_step_pct"]}%), so their personalities were not clearly distinguishable in this run.')
                elif obs_first is exp_first:
                    out.append(f'Behaviour matched personality: {a_["role"]} ({a_["personality_label"]}) took smaller steps ({a_["avg_step_pct"]}% of its range per move) than {b_["role"]} ({b_["personality_label"]}, {b_["avg_step_pct"]}%).')
                else:
                    out.append(f'Behaviour differed from what the personalities suggest: {a_["role"]} ({a_["personality_label"]}) averaged {a_["avg_step_pct"]}% per move vs {b_["avg_step_pct"]}% for {b_["role"]} ({b_["personality_label"]}) - the exchange was shaped by round pressure and each side\'s limits.')

    surplus = r['surplus']
    if surplus and surplus['shares']:
        s = surplus['shares']
        w = max(s, key=s.get)
        wa = next(a for a in r['agents'] if a['id'] == w)
        out.append(f'Of the bargaining zone between the two hard limits ({money(surplus["zone_low"], unit)}–{money(surplus["zone_high"], unit)}), '
                   f'{who(wa)} captured {s[w]}% and the other side {round(100 - s[w], 1)}%.')
    if r['joint']:
        out.append(f'Average objective satisfaction was {r["joint"]["average_satisfaction"]}/100 with a balance score of {r["joint"]["balance"]}/100 (100 = perfectly even).')
    for a in (a0, a1):
        if r['status'] == 'agreed' and a['target_met'] is not None:
            out.append(f'{who(a)} {"met" if a["target_met"] else "did not meet"} {"your" if a["controlled_by"]=="human" else "its"} target position (satisfaction {a["satisfaction"]}/100).')

    dl = r['deadlock']
    if dl and dl.get('triggered'):
        out.append('Deadlock handling: ' + dl['explanation'])
    if ev['corrections']:
        out.append(f'The Orchestrator corrected {ev["corrections"]} decision(s) that would have broken a hard constraint or negotiation rule.')
    if r['llm']['fallback_turns']:
        out.append(f'{r["llm"]["fallback_turns"]} AI turn(s) used the rule-based fallback because the LLM was unavailable or returned an unusable answer.')

    # Practice Mode coaching, derived from the human's own moves
    human = next((a for a in r['agents'] if a['controlled_by'] == 'human'), None)
    if human and r['terminal']:
        if human['hold_count']:
            out.append(f'You repeated your position {human["hold_count"]} time(s) without moving; repeated offers signal inflexibility and can trigger deadlock.')
        if human['concession_count'] == 0 and human['offers_made'] > 1:
            out.append('You never conceded, which leaves the AI no reason to move; small, reciprocal concessions usually unlock agreements.')
        if r['status'] != 'agreed':
            out.append('Tip: try tying each concession to one from the AI, and share reasoning in your messages - the AI responds to tone and to the size of your moves.')
    return out

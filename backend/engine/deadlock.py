"""Deadlock Detection and Resolution Module.

Detects stalled negotiations independently of the hard max-round cutoff:

* ``repeated_offers``  - both sides kept restating identical positions
* ``no_progress``      - both sides moved less than STALL_THRESHOLD_PCT of their
                         own bargaining range for STALL_ROUNDS_TO_TRIGGER rounds
* ``max_rounds``       - the round limit was reached without an agreement

On detection the Orchestrator first tries a mediated midpoint settlement (only
if it satisfies BOTH hard limits) and otherwise declares a breakdown. Every
outcome is recorded in ``state.deadlock_info`` so the outcome screen, transcript
and report can explain exactly what happened."""
from models.state import NegotiationStatus, now

# A round counts as "stalled" when neither agent moved more than this
# percentage of its own bargaining range compared to its previous offer.
STALL_THRESHOLD_PCT = 3.0
# Consecutive stalled rounds tolerated before the Orchestrator intervenes.
STALL_ROUNDS_TO_TRIGGER = 2
# An agent that restates the exact same offer this many extra times in a row
# (i.e. the same offer stated REPEAT_LIMIT + 1 times) is stonewalling.
REPEAT_LIMIT = 2


def repeat_streak(state, agent_id):
    """How many times in a row the agent has restated its previous offer unchanged."""
    n = 0
    for c in reversed([c for c in state.concessions if c.agent_id == agent_id]):
        if abs(c.delta) < 1e-9:
            n += 1
        else:
            break
    return n


def update_stall_counter(state, round_no):
    """Inspect both agents' concession records for the round that was just
    completed and update the running count of consecutive stalled rounds."""
    records = [c for c in state.concessions if c.round == round_no]
    by_agent = {c.agent_id: c for c in records}
    if len(by_agent) < 2:
        state.stall_rounds = 0
        return
    if all(abs(c.pct_of_range) <= STALL_THRESHOLD_PCT for c in by_agent.values()):
        state.stall_rounds += 1
    else:
        state.stall_rounds = 0


def _trigger_kind(state):
    """'repeated_offers' when an agent stonewalled or the stalled rounds contained no movement at all."""
    if any(repeat_streak(state, a.id) >= REPEAT_LIMIT for a in state.agents):
        return 'repeated_offers'
    if state.stall_rounds <= 0:
        return 'no_progress'
    last_rounds = sorted({c.round for c in state.concessions})[-state.stall_rounds:]
    recent = [c for c in state.concessions if c.round in last_rounds]
    return 'repeated_offers' if recent and all(abs(c.delta) < 1e-9 for c in recent) else 'no_progress'


def resolve_if_deadlocked(state, agent_a, agent_b):
    """Intervene when the negotiation is stalled: try a mediated midpoint, otherwise
    declare a breakdown. Stalled means either STALL_ROUNDS_TO_TRIGGER consecutive rounds of
    negligible movement by both sides, or an agent restating the same offer REPEAT_LIMIT+1 times.
    Returns True if the negotiation was terminated."""
    repeaters = [a for a in (agent_a, agent_b) if repeat_streak(state, a.id) >= REPEAT_LIMIT]
    if state.stall_rounds < STALL_ROUNDS_TO_TRIGGER and not repeaters:
        return False
    x = state.last_offer_by(agent_a.id)
    y = state.last_offer_by(agent_b.id)
    if not x or not y or x.value is None or y.value is None:
        return False
    trigger = _trigger_kind(state)
    if repeaters:
        r = repeaters[0]
        what = f'{r.role_label} restated the same offer ({state.last_offer_by(r.id).value:,.2f}) {repeat_streak(state, r.id) + 1} times in a row'
    elif trigger == 'repeated_offers':
        what = 'both sides kept restating the same positions'
    else:
        what = f'both sides moved less than {STALL_THRESHOLD_PCT:g}% of their bargaining range'
    span = f'for {state.stall_rounds} consecutive rounds' if state.stall_rounds >= STALL_ROUNDS_TO_TRIGGER and not repeaters else 'without meaningful progress'
    midpoint = round((x.value + y.value) / 2, 2)
    info = {'triggered': True, 'trigger': trigger, 'round': state.current_round, 'stalled_rounds': state.stall_rounds,
            'positions': {agent_a.id: x.value, agent_b.id: y.value}, 'mediated_value': None}
    if agent_a.satisfies_limit(midpoint) and agent_b.satisfies_limit(midpoint):
        state.status = NegotiationStatus.AGREED
        state.final_value = midpoint
        state.final_agent_id = None
        state.resolution_type = 'mediated'
        info.update(resolution='mediated', mediated_value=midpoint,
                    explanation=f'Deadlock detected: {what} {span}, so the Orchestrator '
                                f'mediated a settlement at the midpoint ({midpoint:,.2f}) of the latest offers, which satisfies both hard limits.')
    else:
        state.status = NegotiationStatus.DEADLOCK
        info.update(resolution='breakdown',
                    explanation=f'Deadlock detected: {what} {span} and no mutually '
                                'feasible value exists between the current positions, so the negotiation was declared a breakdown.')
    state.outcome_reason = info['explanation']
    state.deadlock_info = info
    state.completed_at = now()
    return True


def declare_max_rounds(state):
    x = state.last_offer_by(state.agents[0].id)
    y = state.last_offer_by(state.agents[1].id)
    state.status = NegotiationStatus.MAX_ROUNDS
    state.outcome_reason = f'Maximum of {state.max_rounds} rounds reached without agreement.'
    state.deadlock_info = {'triggered': True, 'trigger': 'max_rounds', 'round': state.current_round, 'stalled_rounds': state.stall_rounds,
                           'positions': {state.agents[0].id: x.value if x else None, state.agents[1].id: y.value if y else None},
                           'mediated_value': None, 'resolution': 'breakdown',
                           'explanation': state.outcome_reason + ' No mutually acceptable position was reached before the limit.'}
    state.completed_at = now()

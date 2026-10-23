"""Orchestrator Agent: the single authority for turns, rounds, state transitions
and hard constraints. Agent output (LLM or rule engine) is advisory - every
decision is validated here before it can change negotiation state."""
from models.state import NegotiationStatus, ActionType, Offer, ConcessionRecord, now
from models.agents import personality_params
from models.scenarios import get_scenario
from llm.schema import AgentInput
import os
import time
from llm import provider
from llm._http import LLMError
from llm.mock_provider import decide as rule_decide
from engine import offer_evaluator, concession, deadlock

CONVERGENCE_BAND = .04   # proposals this close (share of range), both within limits, are merged


def agent(state, agent_id):
    return next(a for a in state.agents if a.id == agent_id)


def opponent(state, a):
    return next(x for x in state.agents if x.id != a.id)


def is_human_turn(state):
    return (state.workflow_mode == 'practice' and not state.is_terminal()
            and state.current_turn_agent_id == state.agents[0].id)


def history(state):
    return [{'round': o.round, 'agent_id': o.agent_id, 'action': o.action.value, 'value': o.value,
             'rationale': o.rationale, 'message': getattr(o, 'message', None), 'source': o.source} for o in state.history]


def _latest_opponent_message(state, a):
    for o in reversed(state.history):
        if o.agent_id == a.id:
            return None
        if o.message:
            return o.message
    return None


def build_input(state, a):
    opp = opponent(state, a)
    own = state.last_offer_by(a.id)
    oo = state.last_offer_by(opp.id)
    p = personality_params(a.personality)
    s = get_scenario(state.scenario_id)
    inp = AgentInput(state.id, s.name, a.issue_label, s.unit, s.total_context, state.current_round, state.max_rounds,
                     a.id, a.role_label, a.personality.value, p['style'], a.direction.value, a.goals, a.constraints, a.objective,
                     a.opening, a.target, a.limit, own.value if own else None, opp.role_label, oo.value if oo else None,
                     history(state), [c.to_dict() for c in state.concessions if c.agent_id == a.id])
    inp.opponent_message = _latest_opponent_message(state, a)
    inp.opening_offer = round(a.opening_offer(), 2)
    inp.reserve_now = round(a.acceptance_value(state.current_round, state.max_rounds), 2)
    inp.worst_offer = round(a.worst_offer(), 2)
    inp.max_step = round(p['max_step'] * a.range_span(), 2)
    inp.opponent_concessions = [{'round': c.round, 'moved_by': c.delta, 'kind': c.kind} for c in state.concessions if c.agent_id == opp.id]
    inp.workflow_mode = state.workflow_mode
    inp.opponent_repeats = deadlock.repeat_streak(state, opp.id)
    return inp


# --------------------------------------------------------------------------
def apply_turn(state, a, d, corrected=False, note=None, message=None, source=None):
    """Apply one validated decision. Shared by AI turns and human turns so that
    turn order, rounds, concessions and terminal conditions can never diverge."""
    opp_agent = opponent(state, a)
    prev = state.last_offer_by(a.id)
    is_offer = d.action in ('open', 'counter') and d.value is not None
    stance = offer_evaluator.stance_label(a, d.value) if is_offer else None
    state.history.append(Offer(state.current_round, a.id, ActionType(d.action), d.value, d.rationale, source or d.source,
                               message=message, corrected=corrected, correction_note=note, stance=stance))
    if prev and is_offer:
        r = concession.record(a, prev.value, d.value, state.current_round, state.concessions)
        state.concessions.append(ConcessionRecord(**r))
    state.updated_at = now()
    is_second = a.id == state.agents[1].id

    if d.action == 'message':
        state.current_turn_agent_id = opp_agent.id
        return state
    if d.action == 'accept':
        state.status, state.final_value, state.final_agent_id = NegotiationStatus.AGREED, d.value, a.id
        state.resolution_type = 'negotiated'
        state.outcome_reason = f'{a.role_label} accepted the latest proposal.'
        state.completed_at = now()
        return state
    if d.action == 'reject':
        state.status, state.final_agent_id = NegotiationStatus.REJECTED, a.id
        state.outcome_reason = f'{a.role_label} rejected the proposal as unacceptable and ended the negotiation.'
        state.completed_at = now()
        return state

    # Convergence: the two latest proposals overlap inside both hard limits and are nearly identical.
    public = [o for o in state.history if o.action in (ActionType.OPEN, ActionType.COUNTER)]
    if len(public) >= 2:
        x, y = public[-2], public[-1]
        if x.agent_id != y.agent_id and x.value is not None and y.value is not None:
            ax, ay = agent(state, x.agent_id), agent(state, y.agent_id)
            if ax.satisfies_limit(y.value) and ay.satisfies_limit(x.value) and abs(x.value - y.value) <= max(ax.range_span(), ay.range_span()) * CONVERGENCE_BAND:
                state.status, state.final_value, state.final_agent_id = NegotiationStatus.AGREED, round((x.value + y.value) / 2, 2), None
                state.resolution_type = 'convergence'
                state.outcome_reason = 'The latest proposals entered a narrow, mutually acceptable zone and were settled at their midpoint.'
                state.completed_at = now()
                return state

    if is_second:   # end of a round
        deadlock.update_stall_counter(state, state.current_round)
        if deadlock.resolve_if_deadlocked(state, state.agents[0], state.agents[1]):
            return state
        if state.current_round >= state.max_rounds:
            deadlock.declare_max_rounds(state)
            return state
    state.current_turn_agent_id = opp_agent.id
    if is_second:
        state.current_round += 1
    return state


MAX_ATTEMPTS = 3   # first call + up to two retries (transient errors, or a reply that cannot be used)


def _llm_turn(state, a, inp, opp_v, own_v):
    """Ask the selected provider for this agent's decision and validate it. Transient failures are retried;
    an unusable reply (bad JSON, missing amount, illegal move) is sent back once with the reason so the
    model can correct it. Raises the last error if every attempt fails."""
    repair, last = None, None
    for attempt in range(MAX_ATTEMPTS):
        try:
            d, _used = provider.reason(inp, 'llm', state.llm_provider, state.llm_model, repair)
        except LLMError as e:
            last = e
            if (e.retryable or e.kind in ('bad_response', 'truncated')) and attempt < MAX_ATTEMPTS - 1:
                time.sleep(float(os.getenv('LLM_RETRY_DELAY', '0.8')) * (attempt + 1))
                continue
            raise
        except ValueError as e:                      # the reply was not parseable JSON / lacked "action"
            last, repair = e, f'It was not usable: {e}.'
            continue
        state.llm_calls += 1
        try:
            return offer_evaluator.validate(a, d, opp_v, own_v)
        except offer_evaluator.InvalidDecision as e:
            last, repair = e, f'{e}'
    raise last


def step(state):
    """Execute the next AI turn. Refuses to act on a human participant's behalf."""
    if state.is_terminal():
        return state
    if is_human_turn(state):
        raise ValueError('Practice Mode is waiting for your move.')
    if state.status == NegotiationStatus.NOT_STARTED:
        state.status = NegotiationStatus.IN_PROGRESS
        state.started_at = now()
    a = agent(state, state.current_turn_agent_id)
    opp = opponent(state, a)
    inp = build_input(state, a)
    own_v = state.last_offer_by(a.id).value if state.last_offer_by(a.id) else None
    opp_v = state.last_offer_by(opp.id).value if state.last_offer_by(opp.id) else None

    d = corrected = note = None
    if state.mode == 'llm':
        try:
            d, corrected, note = _llm_turn(state, a, inp, opp_v, own_v)
            state.last_error = ''
        except Exception as exc:  # network failure, timeout, HTTP error, malformed/invalid decision (after retries)
            state.last_error = provider.scrub(f'{type(exc).__name__}: {exc}')
            if not state.llm_allow_fallback:
                # The user chose "pause on error": nothing is applied, the state stays exactly as it was.
                raise ValueError(f'The {provider.REGISTRY[state.llm_provider]["label"]} turn failed and the rule-based fallback is turned off: '
                                 f'{provider.scrub(exc)} Fix the problem and press the button again.')
            d = None
    if d is None:
        d = rule_decide(inp)
        if state.mode == 'llm':
            state.fallback_count += 1
            d.source = 'fallback'
            d.rationale = f'Rule-based fallback (the {state.llm_provider} LLM turn failed: {state.last_error[:120]}): {d.rationale}'
        d, corrected, note = offer_evaluator.validate(a, d, opp_v, own_v)
    if corrected:
        state.orchestrator_corrections += 1
    return apply_turn(state, a, d, corrected, note, message=None)


def run(state, cap=None):
    """Run AI turns until the negotiation ends (or, in Practice Mode, until it is the human's turn)."""
    cap = cap or state.max_rounds * 2 + 4
    for _ in range(cap):
        if state.is_terminal() or is_human_turn(state):
            break
        step(state)
    return state

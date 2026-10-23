"""Deterministic, personality-driven rule engine.

This is the Mock / Rule-Based mode: it is used when no API key is configured,
when the user picks it explicitly, and as the per-turn fallback if a real LLM
call fails. It never claims to be an LLM - decisions carry ``source='mock'``."""
from llm.schema import AgentDecision
from models.agents import PERSONALITY_PARAMS
from models.state import Personality
from models.units import format_amount

COOPERATIVE_WORDS = ('win-win', 'win win', 'partnership', 'long-term', 'long term', 'flexible', 'mutual', 'together',
                     'fair', 'collaborat', 'compromise', 'meet you', 'happy to', 'work with you', 'both sides')
PRESSURE_WORDS = ('take it or leave it', 'final offer', 'ultimatum', 'or else', 'walk away', 'last chance',
                  'non-negotiable', 'nonnegotiable', 'no more', 'my last')


def tone_of(message):
    """Very small, transparent tone reader used only by the rule-based engine."""
    m = (message or '').lower()
    if not m:
        return None
    if any(w in m for w in PRESSURE_WORDS):
        return 'pressure'
    if any(w in m for w in COOPERATIVE_WORDS):
        return 'cooperative'
    return None


def fmt(v, unit='$'):
    return format_amount(v, unit)


# What each personality says. The numbers are always computed by decide() below;
# these tables only give each agent its own voice.
OPEN_LINE = {
    'aggressive': 'I am opening from a strong position',
    'collaborative': 'I am opening with a reasonable position that leaves room for us both',
    'risk_averse': 'I am opening with a measured, defensible position',
    'competitive': 'I am opening at the top of what this deal is worth',
    'empathetic': 'I want to start somewhere that respects both our needs',
    'strategic': 'I am opening with a deliberately calculated position',
    'opportunistic': 'I am opening high to see how much room there is',
    'compromising': 'I am opening close to the middle so we can meet quickly',
    'analytical': 'Based on the numbers, I am opening at a well-supported position',
}
ACCEPT_LINE = {
    'aggressive': '{opp} meets my requirements - I accept.',
    'collaborative': '{opp} works for both of us. Happy to close on that.',
    'risk_averse': '{opp} is a defensible, low-risk outcome within my constraints. I accept.',
    'competitive': '{opp} clears my bar. I accept - this is a win.',
    'empathetic': '{opp} feels fair to both of us, and I appreciate you getting here. I accept.',
    'strategic': '{opp} is within the range I planned for - I accept and close it out.',
    'opportunistic': '{opp} clears my minimum, so I will take it.',
    'compromising': '{opp} is a fair middle ground. I accept.',
    'analytical': '{opp} falls inside my calculated acceptance range. I accept.',
}
PRESSURE_LINE = {
    'aggressive': 'Ultimatums will not move me. ',
    'collaborative': 'I would rather find common ground than trade ultimatums. ',
    'risk_averse': 'That kind of pressure makes me more cautious. ',
    'competitive': 'Pressure only makes me dig in. ',
    'empathetic': 'I can hear this matters a lot to you, so let us stay calm and keep working at it. ',
    'strategic': 'Noted - but a deadline does not change what the deal is worth. ',
    'opportunistic': 'I will wait and see whether that is really your last word. ',
    'compromising': 'There is no need for ultimatums - let us just meet in the middle. ',
    'analytical': 'Tone aside, the numbers are what matter. ',
}
COUNTER_LINE = {
    'aggressive': '{opp} is still well short of what this deal is worth. I will move to {planned}, but only a small step - the next move has to come from your side.',
    'collaborative': 'There is room for a deal that works for both of us. I am moving to {planned} to close part of the {gap} gap - can you meet me closer to the middle?',
    'risk_averse': 'I need an agreement I can defend. {opp} does not yet fit within my constraints, so I am adjusting cautiously to {planned}.',
    'competitive': '{opp} does not come close. I will move to {planned} - and that is a concession you will have to earn the next one of.',
    'empathetic': 'I understand where you are coming from, and I want us both to walk away comfortable. I am moving to {planned} - can we find the rest together?',
    'strategic': 'I am moving to {planned}, which is a deliberate step, and I would like to see you match it. The gap is {gap}.',
    'opportunistic': 'I can shift to {planned} for now, but {opp} leaves a lot on the table.',
    'compromising': 'Let us split this fairly: I am moving to {planned} so the remaining {gap} gap is shared between us.',
    'analytical': 'With a gap of {gap} between {opp} and my position, I am adjusting to {planned}, in proportion to the distance left.',
}
MIDPOINT_LINE = 'We are close enough that I would rather simply meet in the middle: {planned}.'
WALK_LINE = '{opp} is far outside any workable range for the {issue}. I am ending the negotiation.'
STONEWALL_LINE = 'You have restated the same offer {n} times with no movement. I will not keep negotiating against a wall - I am ending the negotiation.'


def decide(inp):
    sign = 1 if inp.direction == 'maximize' else -1
    p = PERSONALITY_PARAMS[Personality(inp.personality)]
    span = max(abs(inp.opening - inp.limit), 1e-9)
    unit = inp.unit
    better = lambda a, b: (a - b) * sign >= -1e-9          # a is at least as good as b for this agent
    opp, own = inp.opponent_last, inp.own_last
    tone = tone_of(inp.opponent_message)
    reserve = inp.reserve_now if inp.reserve_now is not None else inp.limit
    worst = inp.worst_offer if inp.worst_offer is not None else inp.limit
    open_at = inp.opening_offer if inp.opening_offer is not None else inp.opening
    me = inp.personality

    # 1. Nothing on the table yet -> open from a personality-shaped anchor.
    if opp is None:
        return AgentDecision('open', round(open_at, 2), f'{OPEN_LINE[me]}: {fmt(open_at, unit)} for the {inp.issue_label.lower()}.', .82, 'mock')

    within_limit = better(opp, inp.limit)

    # 2. Accept: the offer meets the hard limit AND this round's acceptance level.
    if within_limit and better(opp, reserve):
        return AgentDecision('accept', opp, ACCEPT_LINE[me].format(opp=fmt(opp, unit)), .90, 'mock')
    if own is not None and better(opp, own):
        # The opponent already offers more than this agent asked for.
        return AgentDecision('accept', opp, f'{fmt(opp, unit)} is at least what I asked for. Accepting.', .92, 'mock')

    # 3. Walk away: a wildly non-serious offer (never on the opening exchange) or, for the
    #    personalities that have no patience for it, a counterpart that keeps restating one offer.
    beyond = max(0.0, (inp.limit - opp) * sign) / span
    walk = p['pressure_walk']
    if walk is not None and inp.round >= 2 and beyond >= walk:
        return AgentDecision('reject', None, WALK_LINE.format(opp=fmt(opp, unit), issue=inp.issue_label.lower()), .88, 'mock')
    if p['repeat_walk'] is not None and inp.round >= 2 and inp.opponent_repeats >= p['repeat_walk']:
        return AgentDecision('reject', None, STONEWALL_LINE.format(n=inp.opponent_repeats + 1), .85, 'mock')

    # 4. Counter: personality controls the size of the step.
    base = own if own is not None else open_at
    pressure = min(max((inp.round - 1) * .04, 0), .20) * p['round_pressure']
    if p['late_boost'] and inp.max_rounds > 1:                 # deadline-driven personalities speed up late
        pressure += p['late_boost'] * min(max((inp.round - 1) / (inp.max_rounds - 1), 0.0), 1.0)
    rate = (p['rate'] + pressure) * p['tone'].get(tone, 1.0)
    last_move = (inp.opponent_concessions or [None])[-1]
    if last_move and last_move.get('kind') == 'concession':    # the opponent just moved toward me
        rate *= p['reciprocity_bonus']
        if p['exploit']:
            rate *= 1 - p['exploit']                           # ...and an exploiter pockets it instead of matching
    # Reward serious offers: the closer the opponent's offer is to what this agent could accept,
    # the larger the concession. A lowball earns only a token move.
    shortfall = max(0.0, (reserve - opp) * sign) / span
    weight = max(.15, 1 - shortfall)
    if inp.opponent_repeats:                                    # reciprocity: no movement from them, less from me
        rate *= p['repeat_decay'] ** min(inp.opponent_repeats, 2)
    planned = base + (opp - base) * min(rate * weight, .75)
    midpoint = False
    if p['midpoint_gap'] and abs(opp - base) <= p['midpoint_gap'] * span:   # close enough: split the difference
        planned, midpoint = (base + opp) / 2, True
    cap = p['max_step'] * span
    if abs(planned - base) > cap:
        planned = base + cap * (1 if opp > base else -1)
    planned = max(planned, worst) if sign == 1 else min(planned, worst)      # safety margin
    planned = max(planned, inp.limit) if sign == 1 else min(planned, inp.limit)  # hard limit
    if own is not None and (planned - own) * sign > 0:                         # never retreat
        planned = own
    planned = round(planned, 2)
    gap = abs(opp - planned)
    lead = {'cooperative': 'Thanks for the constructive tone. ', 'pressure': PRESSURE_LINE[me]}.get(tone, '')
    body = MIDPOINT_LINE.format(planned=fmt(planned, unit)) if midpoint else \
        COUNTER_LINE[me].format(opp=fmt(opp, unit), planned=fmt(planned, unit), gap=fmt(gap, unit))
    if inp.opponent_repeats:
        lead += f'You have now made the same offer {inp.opponent_repeats + 1} times - I need to see movement from you. '
    return AgentDecision('counter', planned, lead + body, .78, 'mock')

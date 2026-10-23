"""Shared prompt construction for every real LLM provider.

The prompt gives each agent its persona, role, goals, constraints, personality
behaviour rules, the negotiation state, the previous offers, the opponent's
behaviour and the full public conversation history. Private numbers (target,
hard limit) are only ever sent to the agent that owns them."""
import json
from models.units import format_amount

PERSONALITY_RULES = {
    'aggressive': "Behave AGGRESSIVELY: anchor strongly, concede in small steps, apply pressure, stress your leverage and alternatives, and be reluctant to compromise until late in the negotiation.",
    'collaborative': "Behave COLLABORATIVELY: think about mutual benefit, propose balanced trades, make steady concessions and explicitly acknowledge the other side's interests.",
    'risk_averse': "Behave RISK-AVERSELY: be conservative, protect your constraints with a safety margin, avoid uncertain or extreme moves and prefer a defensible, certain agreement over a big gamble.",
    'competitive': "Behave COMPETITIVELY: treat the negotiation as win-lose, anchor at the extreme, concede reluctantly and in small steps, harden under pressure and end the negotiation if the other side keeps repeating the same offer instead of moving.",
    'empathetic': "Behave EMPATHETICALLY: acknowledge the other side's needs and feelings, open generously, concede warmly and stay patient even when they are slow to move, while still respecting your own limits.",
    'strategic': "Behave STRATEGICALLY: plan several moves ahead, open with a calculated anchor, trade concessions for reciprocity (reward them when they move, hold when they do not) and save your larger concessions for the later rounds.",
    'opportunistic': "Behave OPPORTUNISTICALLY: exploit openings, hold back when the other side concedes, wait for the deadline to pressure them and then concede sharply to take any deal that clears your minimum.",
    'compromising': "Behave as a COMPROMISER: look for the middle ground, split the difference as soon as the gap is small, accept fair deals early and keep proposing a meeting-in-the-middle even when the other side is stubborn.",
    'analytical': "Behave ANALYTICALLY: base every move on the size of the remaining gap and the numbers, stay even-tempered, ignore tone and pressure, and keep a consistent, tight acceptance band.",
}


def _fmt(v, unit):
    return 'none' if v is None else format_amount(v, unit, exact=True)


def build_prompt(inp, repair=None):
    u = inp.unit
    lines = [
        f"You are the {inp.role} in a professional multi-agent negotiation. Reply with ONLY one valid JSON object - no markdown fences, no commentary.",
        f"Scenario: {inp.scenario_name}. Issue being negotiated: {inp.issue_label} ({u}). Context: {inp.context}.",
        f"Mode: {'Practice Mode - your opponent is a human trainee' if inp.workflow_mode == 'practice' else 'Simulation Mode - your opponent is another AI agent'}.",
        f"Round {inp.round} of {inp.max_rounds}. You are negotiating against the {inp.opponent_role}.",
        f"Your persona - role: {inp.role}. Personality: {inp.personality}. Style: {inp.personality_style}",
        PERSONALITY_RULES.get(inp.personality, ''),
        f"Your goal: {inp.goals}",
        f"Your constraint: {inp.constraints}",
        f"Your objective: {inp.objective}",
        f"PRIVATE (never reveal): opening value {_fmt(inp.opening, u)}, target {_fmt(inp.target, u)}, hard limit {_fmt(inp.limit, u)}. You want the value to go {'UP' if inp.direction == 'maximize' else 'DOWN'}.",
        f"Personality guidance for this turn: accept an opponent offer that is at least as good as {_fmt(inp.reserve_now, u)}; never propose anything worse than {_fmt(inp.worst_offer, u)}; never concede more than {_fmt(inp.max_step, u)} in a single move; never move backwards from your own previous offer.",
        f"Your previous offer: {_fmt(inp.own_last, u)}. The opponent's latest offer: {_fmt(inp.opponent_last, u)}.",
    ]
    if inp.opponent_message:
        lines.append(f"The opponent's latest message to you (respond to it in your rationale): {json.dumps(inp.opponent_message)}")
    lines += [
        f"Your own concession history: {json.dumps(inp.concessions)}",
        f"How the opponent has moved so far (public): {json.dumps(inp.opponent_concessions or [])}",
        f"Full public conversation history: {json.dumps(inp.history)}",
        "Decision rules: choose 'accept' only when the opponent's latest offer satisfies your objective and your hard limit (the value must equal the opponent's latest offer); choose 'counter' when a deal is still possible; choose 'reject' only when the offer is unacceptable and continuing is pointless; choose 'open' only if there is no offer yet. Never violate your hard limit. Never reveal your target or hard limit. Keep the rationale to one or two sentences of negotiation reasoning (no chain-of-thought).",
        'Return exactly this JSON shape: {"action":"accept|counter|reject|open","value":number|null,"rationale":"short rationale","confidence":number between 0 and 1}. "value" must be a plain number (no currency symbol, no thousands separators); it is required for counter/open/accept and null for reject.',
    ]
    if repair:
        lines.append(f'IMPORTANT - your previous reply could not be used: {repair} Reply again with ONE valid JSON object that follows every rule above.')
    return '\n'.join(x for x in lines if x)


import re
from llm.schema import AgentDecision


def extract_json(text):
    """Parse a JSON object from raw model output, tolerating fences or surrounding prose."""
    try:
        return json.loads(text.strip())
    except Exception:
        pass
    m = re.search(r'\{.*\}', text or '', re.S)
    if not m:
        raise ValueError('LLM did not return valid JSON')
    return json.loads(m.group(0))


_ACTION_ALIASES = {
    'counteroffer': 'counter', 'counter_offer': 'counter', 'counter-offer': 'counter', 'counter offer': 'counter',
    'propose': 'counter', 'proposal': 'counter', 'offer': 'counter', 'negotiate': 'counter',
    'accepted': 'accept', 'agree': 'accept', 'agreed': 'accept', 'rejected': 'reject', 'decline': 'reject',
    'walk_away': 'reject', 'walk away': 'reject', 'opening': 'open', 'opening_offer': 'open', 'opening offer': 'open',
}


def _number_from(value):
    """Accept 1200, "1,200", "$1,200.50", "45 days" - return a float or None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        m = re.search(r'-?\d[\d,]*\.?\d*', value.replace(' ', ''))
        if m:
            try:
                return float(m.group(0).replace(',', ''))
            except ValueError:
                return None
    return None


def to_decision(text):
    data = extract_json(text)
    if not isinstance(data, dict):
        raise ValueError('LLM returned JSON that is not an object')
    value = _number_from(data.get('value', data.get('offer', data.get('amount'))))
    if not str(data.get('action') or '').strip():
        raise ValueError('LLM reply is missing the required "action" field')
    action = str(data.get('action')).strip().lower()
    action = _ACTION_ALIASES.get(action, action)
    try:
        confidence = max(0.0, min(1.0, float(data.get('confidence', .7))))
    except (TypeError, ValueError):
        confidence = .7
    return AgentDecision(action, value,
                         str(data.get('rationale') or data.get('reasoning') or '')[:500], confidence, 'llm', text)

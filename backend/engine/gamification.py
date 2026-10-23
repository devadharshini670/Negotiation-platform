"""The one authoritative outcome / score / badge evaluator.

Everything is computed from the recorded analysis of a finished negotiation —
never randomized and never assumed. Practice Mode and Simulation Mode run
through exactly the same functions; the only difference is whose satisfaction
the score looks at: the human participant's own (Practice Mode), or the joint
average of both agents (Simulation Mode, where nobody on the user's side negotiated).

The user's personal skill profile and the leaderboard still count Practice Mode
only (the user didn't negotiate the AI-vs-AI runs); Simulation Mode sessions get
the same evaluation as a *session result* and a separate simulation summary."""

BADGES = {
    'first_agreement': {'label': 'First Agreement', 'desc': 'Closed your first deal in Practice Mode.'},
    'efficient_closer': {'label': 'Efficient Closer', 'desc': 'Reached agreement in half the allowed rounds or fewer.'},
    'peacemaker': {'label': 'Peacemaker', 'desc': 'An Orchestrator-mediated settlement rescued a stalled negotiation.'},
    'balanced_dealmaker': {'label': 'Balanced Dealmaker', 'desc': 'Reached an agreement with a near-even satisfaction balance (90+/100).'},
    'veteran': {'label': 'Veteran Negotiator', 'desc': 'Completed 5 or more Practice Mode negotiations.'},
    'high_scorer': {'label': 'Top Performer', 'desc': 'Scored 90 or above in a single negotiation.'},
}


def negotiation_skill_score(an, human_id=None):
    """0-100. Weighted: 50% reaching agreement at all, 35% objective satisfaction,
    15% how few rounds it took (only rewarded on agreement — taking many rounds
    and still failing earns no efficiency credit). Satisfaction is the human
    participant's own when there is one (Practice Mode); otherwise the average of
    both agents' (Simulation Mode)."""
    if not an['terminal']:
        return None
    agreed = an['status'] == 'agreed'
    human = next((a for a in an['agents'] if a['id'] == human_id), None) if human_id else None
    if human is not None:
        satisfaction = human.get('satisfaction') or 0
    else:
        values = [a.get('satisfaction') or 0 for a in an['agents']]
        satisfaction = sum(values) / len(values) if values else 0
    efficiency = 0.0
    if agreed and an['max_rounds'] > 1:
        efficiency = max(0.0, 1 - (an['rounds_used'] - 1) / (an['max_rounds'] - 1))
    score = (100 if agreed else 0) * .5 + satisfaction * .35 + (efficiency * 100) * .15
    return round(max(0.0, min(100.0, score)), 1)


def session_badges(an, score):
    """Ids of the badges this single negotiation earns. This is the only place the
    badge rules live; the profile below simply applies it to each of the user's sessions."""
    if not an['terminal']:
        return []
    agreed = an['status'] == 'agreed'
    earned = []
    if agreed:
        earned.append('first_agreement')
        if an['rounds_used'] <= max(1, an['max_rounds'] // 2):
            earned.append('efficient_closer')
    if (an['deadlock'] or {}).get('resolution') == 'mediated':
        earned.append('peacemaker')
    if agreed and an.get('joint') and an['joint']['balance'] >= 90:
        earned.append('balanced_dealmaker')
    if score is not None and score >= 90:
        earned.append('high_scorer')
    return earned


OUTCOMES = {
    'balanced_deal': 'Balanced deal',
    'efficient_agreement': 'Efficient agreement',
    'mediated_agreement': 'Mediated settlement',
    'agreement': 'Agreement reached',
    'deadlock': 'Deadlock — no agreement',
    'rejected': 'Rejected — no agreement',
    'max_rounds': 'Maximum rounds reached — no agreement',
    'completed': 'Negotiation completed',
}


def outcome_key(an):
    """Classify a finished negotiation from its recorded facts (status, how it closed,
    rounds used and how evenly the satisfaction was shared)."""
    status = an['status']
    if status == 'agreed':
        if (an['deadlock'] or {}).get('resolution') == 'mediated':
            return 'mediated_agreement'
        if an.get('joint') and an['joint']['balance'] >= 90:
            return 'balanced_deal'
        if an['rounds_used'] <= max(1, an['max_rounds'] // 2):
            return 'efficient_agreement'
        return 'agreement'
    return {'deadlock': 'deadlock', 'rejected': 'rejected', 'max_rounds_reached': 'max_rounds'}.get(status, 'completed')


def evaluate_outcome(an, human_id=None):
    """Outcome label, score and badges for ONE finished negotiation, in either mode.
    ``human_id`` is the Practice Mode participant (None for Simulation Mode)."""
    if not an['terminal']:
        return None
    score = negotiation_skill_score(an, human_id)
    key = outcome_key(an)
    return {'key': key, 'label': OUTCOMES[key], 'status': an['status'], 'score': score,
            'score_basis': 'your own result' if human_id else 'both agents combined',
            'badges': [{'id': b, **BADGES[b]} for b in session_badges(an, score)]}


def user_profile(scored_analyses):
    """``scored_analyses`` is a list of (score, analysis_dict) for the user's own
    completed Practice Mode negotiations. Returns aggregate stats and which
    badges the recorded data actually earns."""
    earned = set()
    for score, an in scored_analyses:
        earned.update(session_badges(an, score))
    if len(scored_analyses) >= 5:
        earned.add('veteran')
    badges = [b for b in BADGES if b in earned]
    scores = [s for s, _ in scored_analyses]
    return {
        'completed': len(scored_analyses),
        'agreements': sum(1 for _, an in scored_analyses if an['status'] == 'agreed'),
        'average_score': round(sum(scores) / len(scores), 1) if scores else None,
        'best_score': max(scores) if scores else None,
        'badges': [{'id': b, **BADGES[b]} for b in badges],
        'locked_badges': [{'id': b, **BADGES[b]} for b in BADGES if b not in badges],
    }


def simulation_summary(simulation_analyses):
    """Same evaluator applied to the user's finished Simulation Mode runs: how they
    ended and which badges those results earned. Kept apart from the practice profile."""
    outcomes, earned, scores = {}, set(), []
    for an in simulation_analyses:
        ev = evaluate_outcome(an)
        outcomes[ev['key']] = outcomes.get(ev['key'], 0) + 1
        earned.update(b['id'] for b in ev['badges'])
        scores.append(ev['score'])
    return {'completed': len(scores), 'outcomes': [{'key': k, 'label': OUTCOMES[k], 'count': n} for k, n in outcomes.items()],
            'average_score': round(sum(scores) / len(scores), 1) if scores else None,
            'badges': [{'id': b, **BADGES[b]} for b in BADGES if b in earned]}

def record(agent, previous, new, round_no, existing):
    """Describe one movement of an agent's position (see ConcessionRecord)."""
    delta = new - previous
    span = agent.range_span()
    conceded = agent.conceded_amount(previous, new)
    kind = 'concession' if conceded > 1e-9 else 'retreat' if conceded < -1e-9 else 'hold'
    cumulative = sum(max(x.conceded, 0) for x in existing if x.agent_id == agent.id) + max(conceded, 0)
    return {
        'agent_id': agent.id, 'round': round_no, 'previous_value': previous, 'new_value': new,
        'delta': round(delta, 2), 'pct_of_range': round(abs(delta) / span * 100, 2),
        'cumulative_pct': round(cumulative / span * 100, 2),
        'kind': kind, 'conceded': round(conceded, 2),
    }

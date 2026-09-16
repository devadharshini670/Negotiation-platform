from llm.schema import AgentDecision

def decide(inp):
    sign=1 if inp.direction=='maximize' else -1
    opp=inp.opponent_last
    base=inp.own_last if inp.own_last is not None else inp.opening
    if opp is None:
        return AgentDecision('open',round(inp.opening,2),f'Opening from a deliberate anchor toward the {inp.role} target.',.82,'mock')
    if (opp-inp.target)*sign>=0 and (opp-inp.limit)*sign>=0:
        return AgentDecision('accept',opp,'The latest proposal satisfies the agent objective and remains within its constraint.',.92,'mock')
    # Personality controls concession speed; pressure increases as rounds progress.
    base_rate={'aggressive':.12,'collaborative':.30,'risk_averse':.20}.get(inp.personality,.20)
    pressure=min(max((inp.round-1)*.055,0),.25)
    rate=min(base_rate+pressure,.58)
    planned=base+(opp-base)*rate
    planned=max(planned,inp.limit) if inp.direction=='maximize' else min(planned,inp.limit)
    # The overlap of hard constraints is the feasible bargaining zone. As the
    # discussion progresses, the fallback engine is willing to close a deal
    # near the midpoint rather than oscillate forever.
    if (opp-inp.limit)*sign>=0:
        target_gap=abs(opp-inp.target)/(abs(inp.target-inp.limit) or 1)
        close_threshold={'aggressive':.16,'collaborative':.28,'risk_averse':.34}.get(inp.personality,.25)
        if target_gap<=close_threshold or inp.round>=5:
            return AgentDecision('accept',opp,'The proposal is within a defensible range; closing now is preferable to unnecessary additional risk.',.86,'mock')
    return AgentDecision('counter',round(planned,2),f'{inp.personality.replace("_","-").title()} strategy makes a measured concession toward the opponent while protecting the hard limit.',.78,'mock')

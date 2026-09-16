from models.state import NegotiationStatus,ActionType,Offer,ConcessionRecord,now
from models.agents import personality_params
from llm.schema import AgentInput
from llm import provider
from engine import offer_evaluator,concession

def agent(state,agent_id): return next(a for a in state.agents if a.id==agent_id)
def opponent(state,a): return next(x for x in state.agents if x.id!=a.id)
def history(state): return [{'round':o.round,'agent_id':o.agent_id,'action':o.action.value,'value':o.value,'rationale':o.rationale,'message':getattr(o,'message',None),'source':o.source} for o in state.history]
def build_input(state,a):
    opp=opponent(state,a); own=state.last_offer_by(a.id); oo=state.last_offer_by(opp.id); p=personality_params(a.personality)
    from models.scenarios import get_scenario
    s=get_scenario(state.scenario_id)
    return AgentInput(state.id,s.name,a.issue_label,s.unit,s.total_context,state.current_round,state.max_rounds,a.id,a.role_label,a.personality.value,p['style'],a.direction.value,a.goals,a.constraints,a.objective,a.opening,a.target,a.limit,own.value if own else None,opp.role_label,oo.value if oo else None,history(state),[c.to_dict() if hasattr(c,'to_dict') else c for c in state.concessions if c.agent_id==a.id])
def step(state):
    if state.is_terminal(): return state
    if state.status==NegotiationStatus.NOT_STARTED: state.status=NegotiationStatus.IN_PROGRESS; state.started_at=now()
    a=agent(state,state.current_turn_agent_id); inp=build_input(state,a)
    try: d=provider.reason(inp,state.mode)
    except Exception as exc:
        from llm.mock_provider import decide
        d=decide(inp); state.fallback_count+=1; d.rationale=f'Fallback engine: {d.rationale}'
    if d.source=='llm': state.llm_calls+=1
    d,corrected,note=offer_evaluator.validate(a,d)
    if corrected: state.orchestrator_corrections+=1
    prev=state.last_offer_by(a.id)
    state.history.append(Offer(state.current_round,a.id,ActionType(d.action),d.value,d.rationale,d.source,message=(d.rationale if d.action=='message' else None),corrected=corrected,correction_note=note))
    if prev and d.action in ('open','counter') and d.value is not None:
        r=concession.record(a,prev.value,d.value,state.current_round,state.concessions); state.concessions.append(ConcessionRecord(r['agent_id'],r['round'],r['previous_value'],r['new_value'],r['delta'],r['pct_of_range'],r['cumulative_pct']))
    if d.action=='message':
        state.current_turn_agent_id=opponent(state,a).id
        state.updated_at=now()
        return state
    if d.action=='accept':
        state.status=NegotiationStatus.AGREED; state.final_value=d.value; state.final_agent_id=a.id; state.outcome_reason=f'{a.role_label} accepted the latest proposal.'; state.completed_at=now(); return state
    if d.action=='reject':
        state.status=NegotiationStatus.REJECTED; state.outcome_reason=f'{a.role_label} rejected the proposal as unacceptable.'; state.completed_at=now(); return state
    public=[o for o in state.history if o.action in (ActionType.OPEN,ActionType.COUNTER)]
    if len(public)>=2:
        x,y=public[-2],public[-1]
        if x.agent_id!=y.agent_id and x.value is not None and y.value is not None:
            ax=agent(state,x.agent_id); ay=agent(state,y.agent_id)
            if ax.satisfies_limit(y.value) and ay.satisfies_limit(x.value) and abs(x.value-y.value)<=max(ax.range_span(),ay.range_span())*.04:
                state.status=NegotiationStatus.AGREED; state.final_value=round((x.value+y.value)/2,2); state.final_agent_id=a.id; state.outcome_reason='The latest proposals entered a narrow mutually acceptable zone.'; state.completed_at=now(); return state
    if state.current_round>=state.max_rounds and a.id==state.agents[1].id:
        state.status=NegotiationStatus.MAX_ROUNDS; state.outcome_reason=f'Maximum of {state.max_rounds} rounds reached without agreement.'; state.completed_at=now(); return state
    state.current_turn_agent_id=opponent(state,a).id
    if a.id==state.agents[1].id: state.current_round+=1
    state.updated_at=now(); return state
def run(state,cap=100):
    for _ in range(cap):
        if state.is_terminal():break
        step(state)
    return state

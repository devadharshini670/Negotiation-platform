import uuid
from models.state import NegotiationState,Personality,NegotiationStatus,ActionType,Offer,now
from models.scenarios import get_scenario
from engine import orchestrator,concession
_STORE={}
def create_negotiation(scenario_id,personality_a,personality_b,mode='mock',max_rounds=None,workflow_mode='simulation'):
    s=get_scenario(scenario_id); a=s.build_agent(s.side_a.id,Personality(personality_a)); b=s.build_agent(s.side_b.id,Personality(personality_b))
    st=NegotiationState(uuid.uuid4().hex[:10],scenario_id,max_rounds or s.default_max_rounds,[a,b],current_turn_agent_id=a.id,mode=mode if mode in {'mock','llm'} else 'mock',workflow_mode=workflow_mode if workflow_mode in {'simulation','practice'} else 'simulation')
    _STORE[st.id]=st; return st
def get_negotiation(i): return _STORE.get(i)
def list_negotiations():
    out=[]
    for st in sorted(_STORE.values(),key=lambda x:x.created_at,reverse=True):
        s=get_scenario(st.scenario_id); out.append({'id':st.id,'scenario_id':st.scenario_id,'scenario_name':s.name,'status':st.status.value,'mode':st.mode,'workflow_mode':st.workflow_mode,'rounds_used':max(1,st.current_round),'max_rounds':st.max_rounds,'final_value':st.final_value,'unit':s.unit,'agents':[{'id':a.id,'role_label':a.role_label,'personality':a.personality.value} for a in st.agents],'created_at':st.created_at})
    return out
def dashboard_stats():
    xs=list(_STORE.values()); terminal=[x for x in xs if x.is_terminal()]; agreed=[x for x in terminal if x.status==NegotiationStatus.AGREED]
    return {'total_negotiations':len(xs),'completed':len(terminal),'agreements':len(agreed),'agreement_rate_pct':round(len(agreed)/len(terminal)*100,1) if terminal else 0,'avg_rounds':round(sum(max(1,x.current_round) for x in terminal)/len(terminal),1) if terminal else 0,'llm_runs':sum(x.llm_calls>0 for x in xs),'fallbacks':sum(x.fallback_count for x in xs),'active':sum(not x.is_terminal() for x in xs)}
def step_negotiation(i):
 st=get_negotiation(i)
 if not st: raise KeyError('negotiation not found')
 return orchestrator.step(st)
def run_negotiation(i):
 st=get_negotiation(i)
 if not st: raise KeyError('negotiation not found')
 return orchestrator.run(st)
def build_report(i):
 st=get_negotiation(i)
 if not st: raise KeyError('negotiation not found')
 s=get_scenario(st.scenario_id)
 return {'id':st.id,'scenario':s.name,'status':st.status.value,'final_value':st.final_value,'unit':s.unit,'rounds_used':max(1,st.current_round),'max_rounds':st.max_rounds,'total_offers':len(st.history),'outcome_reason':st.outcome_reason,'mode':st.mode,'workflow_mode':st.workflow_mode,'llm_calls':st.llm_calls,'fallback_count':st.fallback_count,'orchestrator_corrections':st.orchestrator_corrections,'agents':[a.to_dict() for a in st.agents],'concessions':{a.id:[c.to_dict() if hasattr(c,'to_dict') else c.__dict__ for c in st.concessions if c.agent_id==a.id] for a in st.agents},'history':[o.to_dict() for o in st.history]}
def human_action(i,action,value,rationale='Human participant submitted this proposal.',message=''):
 st=get_negotiation(i)
 if not st:raise KeyError('negotiation not found')
 if st.is_terminal():raise ValueError('negotiation already ended')
 a=orchestrator.agent(st,st.current_turn_agent_id)
 if a.id!=st.agents[0].id: raise ValueError('Practice Mode is waiting for the AI participant.')
 from llm.schema import AgentDecision
 clean_message=(message or '').strip()[:1000]
 if action=='message':
  if not clean_message: raise ValueError('Write a message before sending.')
  st.history.append(Offer(st.current_round,a.id,ActionType.MESSAGE,None,clean_message,'human',message=clean_message))
  st.current_turn_agent_id=orchestrator.opponent(st,a).id
  st.updated_at=now()
  return st
 from engine import offer_evaluator
 d,corrected,note=offer_evaluator.validate(a,AgentDecision(action,value,rationale,.99,'human'))
 if corrected: st.orchestrator_corrections+=1
 st.history.append(Offer(st.current_round,a.id,ActionType(d.action),d.value,d.rationale,'human',message=clean_message or None,corrected=corrected,correction_note=note))
 prev=st.last_offer_by(a.id)
 if prev and d.action in ('open','counter') and d.value is not None:
  r=concession.record(a,prev.value,d.value,st.current_round,st.concessions)
  from models.state import ConcessionRecord
  st.concessions.append(ConcessionRecord(r['agent_id'],r['round'],r['previous_value'],r['new_value'],r['delta'],r['pct_of_range'],r['cumulative_pct']))
 if d.action=='accept':
  st.status=NegotiationStatus.AGREED;st.final_value=d.value;st.final_agent_id=a.id;st.outcome_reason=f'{a.role_label} accepted the proposal.';st.completed_at=now();return st
 if d.action=='reject':
  st.status=NegotiationStatus.REJECTED;st.outcome_reason=f'{a.role_label} rejected the proposal.';st.completed_at=now();return st
 st.current_turn_agent_id=orchestrator.opponent(st,a).id
 st.updated_at=now();return st

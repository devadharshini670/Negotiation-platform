from engine.negotiation_engine import create_negotiation,run_negotiation
from engine import deadlock, offer_evaluator
from models.state import NegotiationStatus,NegotiationState,ConcessionRecord,Offer,ActionType,Personality
from models.scenarios import get_scenario

def test_three_scenarios():
    for scenario in ('vendor_pricing','job_offer','project_budget'):
        s=create_negotiation(scenario,'collaborative','aggressive','mock',5)
        assert len(s.agents)==2
        assert s.current_round==1

def test_multiround_vendor_negotiation():
    s=create_negotiation('vendor_pricing','risk_averse','aggressive','mock',5)
    s=run_negotiation(s.id)
    assert len(s.history)>=6
    assert s.status in {NegotiationStatus.AGREED,NegotiationStatus.REJECTED,NegotiationStatus.DEADLOCK,NegotiationStatus.MAX_ROUNDS}

def test_personalities_are_independent():
    s=create_negotiation('vendor_pricing','aggressive','risk_averse','mock',5)
    assert s.agents[0].personality.value=='aggressive'
    assert s.agents[1].personality.value=='risk_averse'

def _stub_state():
    sc=get_scenario('vendor_pricing')
    a=sc.build_agent(sc.side_a.id,Personality.AGGRESSIVE)
    b=sc.build_agent(sc.side_b.id,Personality.AGGRESSIVE)
    st=NegotiationState('stub','vendor_pricing',8,[a,b],current_turn_agent_id=a.id)
    return st,a,b

def test_stall_counter_increments_on_negligible_movement():
    st,a,b=_stub_state()
    st.concessions=[ConcessionRecord(a.id,3,40,40.5,0.5,1.0,1.0),ConcessionRecord(b.id,3,45,44.6,-0.4,1.0,1.0)]
    deadlock.update_stall_counter(st,3)
    assert st.stall_rounds==1
    st.concessions+= [ConcessionRecord(a.id,4,40.5,44,3.5,10.0,11.0),ConcessionRecord(b.id,4,44.6,42,-2.6,10.0,11.0)]
    deadlock.update_stall_counter(st,4)
    assert st.stall_rounds==0  # real movement resets the counter

def test_deadlock_mediates_when_a_feasible_midpoint_exists():
    st,a,b=_stub_state()
    st.history=[Offer(3,a.id,ActionType.COUNTER,41,'r','mock'),Offer(3,b.id,ActionType.COUNTER,44,'r','mock')]
    st.stall_rounds=2
    resolved=deadlock.resolve_if_deadlocked(st,a,b)
    assert resolved is True
    assert st.status==NegotiationStatus.AGREED
    assert st.final_value==42.5

def test_deadlock_declares_breakdown_when_no_feasible_midpoint():
    st,a,b=_stub_state()
    # 60 fails buyer's ceiling(48)/vendor floor is fine, but 90 fails buyer ceiling badly -> use values outside both ranges
    st.history=[Offer(3,a.id,ActionType.COUNTER,60,'r','mock'),Offer(3,b.id,ActionType.COUNTER,60,'r','mock')]
    st.stall_rounds=2
    resolved=deadlock.resolve_if_deadlocked(st,a,b)
    assert resolved is True
    assert st.status==NegotiationStatus.DEADLOCK

def test_stance_label_reflects_agent_firmness():
    sc=get_scenario('vendor_pricing')
    buyer=sc.build_agent(sc.side_a.id,Personality.COLLABORATIVE)  # minimize, opening 32, target 38, limit 48
    assert offer_evaluator.stance_label(buyer,buyer.target)=='Firmly anchored'
    assert offer_evaluator.stance_label(buyer,60)=='Off the table'  # above the 48 ceiling -> unacceptable

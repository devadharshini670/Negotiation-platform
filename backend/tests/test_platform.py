from engine.negotiation_engine import create_negotiation,run_negotiation
from models.state import NegotiationStatus

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

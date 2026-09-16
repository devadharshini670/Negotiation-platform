from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import uuid

class Personality(str, Enum):
    AGGRESSIVE="aggressive"; COLLABORATIVE="collaborative"; RISK_AVERSE="risk_averse"
class Direction(str, Enum):
    MAXIMIZE="maximize"; MINIMIZE="minimize"
class ActionType(str, Enum):
    OPEN="open"; ACCEPT="accept"; COUNTER="counter"; REJECT="reject"; MESSAGE="message"
class NegotiationStatus(str, Enum):
    NOT_STARTED="not_started"; IN_PROGRESS="in_progress"; AGREED="agreed"; REJECTED="rejected"; DEADLOCK="deadlock"; COMPLETED="completed"; MAX_ROUNDS="max_rounds_reached"

def now(): return datetime.now(timezone.utc).isoformat()

@dataclass
class Offer:
    round:int; agent_id:str; action:ActionType; value:Optional[float]; rationale:str; source:str
    message:Optional[str]=None
    timestamp:str=field(default_factory=now); id:str=field(default_factory=lambda:uuid.uuid4().hex[:10])
    corrected:bool=False; correction_note:Optional[str]=None
    def to_dict(self):
        d=asdict(self); d["action"]=self.action.value; return d

@dataclass
class ConcessionRecord:
    agent_id:str; round:int; previous_value:float; new_value:float; delta:float; pct_of_range:float; cumulative_pct:float
    def to_dict(self): return asdict(self)

@dataclass
class NegotiationState:
    id:str; scenario_id:str; max_rounds:int; agents:list
    current_round:int=1; current_turn_agent_id:str=""; status:NegotiationStatus=NegotiationStatus.NOT_STARTED
    history:list=field(default_factory=list); concessions:list=field(default_factory=list)
    final_value:Optional[float]=None; final_agent_id:Optional[str]=None; outcome_reason:str=""
    created_at:str=field(default_factory=now); updated_at:str=field(default_factory=now); mode:str="mock"
    workflow_mode:str="simulation"
    llm_calls:int=0; fallback_count:int=0; orchestrator_corrections:int=0; started_at:Optional[str]=None; completed_at:Optional[str]=None
    def last_offer_by(self, agent_id):
        for o in reversed(self.history):
            if o.agent_id==agent_id and o.action in (ActionType.OPEN,ActionType.COUNTER): return o
        return None
    def last_public_offer(self):
        for o in reversed(self.history):
            if o.action in (ActionType.OPEN,ActionType.COUNTER): return o
        return None
    def is_terminal(self): return self.status in {NegotiationStatus.AGREED,NegotiationStatus.REJECTED,NegotiationStatus.DEADLOCK,NegotiationStatus.COMPLETED,NegotiationStatus.MAX_ROUNDS}
    def to_dict(self):
        return {"id":self.id,"scenario_id":self.scenario_id,"max_rounds":self.max_rounds,"agents":[a.to_dict() for a in self.agents],"current_round":self.current_round,"current_turn_agent_id":self.current_turn_agent_id,"status":self.status.value,"history":[x.to_dict() for x in self.history],"concessions":[x.to_dict() for x in self.concessions],"final_value":self.final_value,"final_agent_id":self.final_agent_id,"outcome_reason":self.outcome_reason,"created_at":self.created_at,"updated_at":self.updated_at,"mode":self.mode,"workflow_mode":self.workflow_mode,"llm_calls":self.llm_calls,"fallback_count":self.fallback_count,"orchestrator_corrections":self.orchestrator_corrections,"started_at":self.started_at,"completed_at":self.completed_at}

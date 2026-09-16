from dataclasses import dataclass,asdict
from typing import Optional
@dataclass
class AgentInput:
 negotiation_id:str; scenario_name:str; issue_label:str; unit:str; context:str; round:int; max_rounds:int; agent_id:str; role:str; personality:str; personality_style:str; direction:str; goals:str; constraints:str; objective:str; opening:float; target:float; limit:float; own_last:Optional[float]; opponent_role:str; opponent_last:Optional[float]; history:list; concessions:list
 def to_dict(self): return asdict(self)
@dataclass
class AgentDecision:
 action:str; value:Optional[float]; rationale:str; confidence:float=0.5; source:str="mock"; raw:Optional[str]=None
 def to_dict(self): return asdict(self)

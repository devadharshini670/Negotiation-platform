from dataclasses import dataclass, asdict
from models.state import Personality,Direction

PERSONALITY_PARAMS={
 Personality.AGGRESSIVE:{"concession_rate":.10,"accept_threshold":.06,"style":"Firm and target-driven. Uses strong anchors, small concessions and protects leverage."},
 Personality.COLLABORATIVE:{"concession_rate":.30,"accept_threshold":.15,"style":"Win-win oriented. Seeks fair middle ground and makes steady, measured concessions."},
 Personality.RISK_AVERSE:{"concession_rate":.20,"accept_threshold":.20,"style":"Cautious and stability-focused. Avoids risky moves and prefers a defensible agreement."}
}
@dataclass
class AgentConfig:
 id:str; role_label:str; personality:Personality; direction:Direction; opening:float; target:float; limit:float; issue_label:str; goals:str; constraints:str; objective:str
 def to_dict(self):
  d=asdict(self); d["personality"]=self.personality.value; d["direction"]=self.direction.value; return d
 def range_span(self): return max(abs(self.opening-self.limit),1e-9)
 def satisfies_limit(self,v): return v>=self.limit if self.direction==Direction.MAXIMIZE else v<=self.limit
 def clamp(self,v): return max(v,self.limit) if self.direction==Direction.MAXIMIZE else min(v,self.limit)
 def distance(self,a,b): return abs(a-b)

def personality_params(p): return PERSONALITY_PARAMS[p]

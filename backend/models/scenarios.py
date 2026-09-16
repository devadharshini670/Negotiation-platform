from dataclasses import dataclass
from models.state import Personality,Direction
from models.agents import AgentConfig
@dataclass
class Side:
 id:str; role_label:str; direction:Direction; opening:float; target:float; limit:float; goals:str; constraints:str; objective:str
@dataclass
class Scenario:
 id:str; name:str; description:str; issue_label:str; unit:str; total_context:str; side_a:Side; side_b:Side; default_max_rounds:int=8
 def build_agent(self,side_id,p):
  s=self.side_a if side_id==self.side_a.id else self.side_b
  return AgentConfig(s.id,s.role_label,p,s.direction,s.opening,s.target,s.limit,self.issue_label,s.goals,s.constraints,s.objective)
SCENARIOS={
"vendor_pricing":Scenario("vendor_pricing","Vendor Pricing Negotiation","A procurement buyer and supplier negotiate a unit price for a 1,000-unit contract.","Unit Price","$","1,000-unit bulk supply contract",
 Side("buyer","Buyer",Direction.MINIMIZE,32,38,48,"Secure the lowest defensible unit price while preserving supplier quality and continuity.","Hard ceiling: $48/unit.","Minimize unit price without crossing the approved budget."),
 Side("vendor","Vendor",Direction.MAXIMIZE,58,50,40,"Maximize profitable revenue while winning a repeatable supply relationship.","Hard floor: $40/unit.","Maximize unit price while protecting margin.")),
"job_offer":Scenario("job_offer","Job Offer Negotiation","A candidate and employer negotiate annual base salary for a senior engineering role.","Annual Salary","$","Senior engineering compensation package",
 Side("candidate","Candidate",Direction.MAXIMIZE,145000,132000,115000,"Secure compensation that reflects experience, market value and role scope.","Hard floor: $115,000 base salary.","Maximize base salary while keeping the opportunity viable."),
 Side("employer","Employer",Direction.MINIMIZE,105000,118000,135000,"Hire a strong candidate within the approved compensation budget.","Hard ceiling: $135,000 base salary.","Minimize salary cost without losing the candidate.")),
"project_budget":Scenario("project_budget","Project Budget Allocation","Two department leads negotiate Department A's share of a fixed $200,000 project pool.","Department A Share","$","Fixed shared project pool of $200,000",
 Side("dept_a","Department A Lead",Direction.MAXIMIZE,140000,120000,90000,"Secure enough funding to deliver Department A's committed roadmap.","Hard floor: $90,000.","Maximize Department A funding while keeping the proposal defensible."),
 Side("dept_b","Department B Lead",Direction.MINIMIZE,60000,80000,110000,"Protect enough of the shared pool for Department B deliverables.","Department A share cannot exceed $110,000.","Minimize Department A's share while keeping the project workable."))}
def get_scenario(i):
 if i not in SCENARIOS: raise KeyError(f"Unknown scenario: {i}")
 return SCENARIOS[i]
def list_scenarios():
 return [{"id":s.id,"name":s.name,"description":s.description,"issue_label":s.issue_label,"unit":s.unit,"total_context":s.total_context,"default_max_rounds":s.default_max_rounds,"agents":[{"id":x.id,"role":x.role_label,"goal":x.goals,"constraint":x.constraints,"objective":x.objective,"direction":x.direction.value} for x in (s.side_a,s.side_b)]} for s in SCENARIOS.values()]

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
SCENARIOS.update({
"freelance_contract":Scenario("freelance_contract","Freelance Contract Negotiation","A freelance designer and a startup client negotiate the fixed fee for a six-week brand identity and website project.","Project Fee","$","Fixed-fee, six-week brand identity and marketing-website project",
 Side("freelancer","Freelancer",Direction.MAXIMIZE,7500,6000,4200,"Earn a fee that reflects the scope of work and my day rate while keeping a long-term client.","Hard floor: $4,200 for the project.","Maximize the project fee without losing the engagement."),
 Side("client","Client",Direction.MINIMIZE,3200,4800,6200,"Get a polished brand and website delivered inside the approved marketing budget.","Hard ceiling: $6,200 for the project.","Minimize the fee while keeping quality and delivery dates intact.")),
"real_estate":Scenario("real_estate","Real Estate Price Negotiation","A homeowner and a buyer negotiate the sale price of a three-bedroom townhouse after the inspection.","Sale Price","$","Three-bedroom townhouse listed at $525,000 with a 30-day closing",
 Side("seller","Seller",Direction.MAXIMIZE,560000,525000,492000,"Sell at or near the listing price before the relocation date.","Hard floor: $492,000 (covers the remaining mortgage and moving costs).","Maximize the sale price without letting the sale slip past the relocation date."),
 Side("buyer","Buyer",Direction.MINIMIZE,455000,490000,515000,"Buy the home at a fair price that reflects the inspection findings and my approved financing.","Hard ceiling: $515,000 (maximum mortgage pre-approval).","Minimize the purchase price while securing the home.")),
"software_dev_contract":Scenario("software_dev_contract","Software Development Contract","A software agency and a client company negotiate the fixed price of a custom web-application build.","Fixed Contract Price","$","Custom web application: four-month build, fixed scope, two rounds of revisions",
 Side("agency","Software Agency",Direction.MAXIMIZE,190000,156000,128000,"Win a profitable fixed-price build that covers engineering capacity and delivery risk.","Hard floor: $128,000 (team cost plus minimum margin).","Maximize contract value while keeping delivery risk covered."),
 Side("client_co","Client Company",Direction.MINIMIZE,92000,120000,148000,"Get the product built to specification within the approved project budget.","Hard ceiling: $148,000 (approved budget).","Minimize the price while keeping the agreed scope intact.")),
"salary_benefits":Scenario("salary_benefits","Salary & Benefits Negotiation","A product-manager candidate and a hiring manager negotiate the total annual package: salary, bonus, equity and benefits.","Total Annual Compensation","$","Salary, target bonus, equity and benefits for a product-manager role, valued as annual cost",
 Side("applicant","Candidate",Direction.MAXIMIZE,165000,142000,124000,"Secure a total package that reflects my experience, the market and the scope of the role.","Hard floor: $124,000 total annual compensation.","Maximize total compensation while keeping the offer worth accepting."),
 Side("hiring_manager","Hiring Manager",Direction.MINIMIZE,118000,132000,150000,"Hire the strongest candidate within the approved headcount budget.","Hard ceiling: $150,000 total annual compensation.","Minimize the cost of the package without losing the candidate.")),
"supplier_renewal":Scenario("supplier_renewal","Supplier Contract Renewal","A components supplier and a manufacturer negotiate the annual value of a 12-month renewal after a rise in material costs.","Annual Contract Value","$","12-month renewal of an existing components supply agreement",
 Side("supplier","Supplier",Direction.MAXIMIZE,980000,880000,790000,"Renew the account at a price that reflects higher material costs and secures volume.","Hard floor: $790,000 per year (margin after raw-material increases).","Maximize annual contract value while keeping a long-term customer."),
 Side("manufacturer","Manufacturer",Direction.MINIMIZE,700000,770000,840000,"Keep supply continuity at a price consistent with the approved procurement budget.","Hard ceiling: $840,000 per year (approved procurement budget).","Minimize annual cost without risking supply continuity.")),
"project_deadline":Scenario("project_deadline","Project Deadline Negotiation","A project sponsor and a delivery lead negotiate how many days the team has to deliver a platform release.","Delivery Deadline","days","Platform release with fixed scope and two engineering squads",
 Side("sponsor","Project Sponsor",Direction.MINIMIZE,30,45,60,"Hit the market window with a credible delivery date.","Hard ceiling: 60 days (launch commitment already made to customers).","Minimize the delivery time without setting the team up to fail."),
 Side("delivery_lead","Delivery Lead",Direction.MAXIMIZE,90,70,52,"Commit to a date the team can meet with proper testing and review.","Hard floor: 52 days (minimum to deliver safely at current capacity).","Maximize the timeline while keeping the commitment realistic.")),
})
def get_scenario(i):
 if i not in SCENARIOS: raise KeyError(f"Unknown scenario: {i}")
 return SCENARIOS[i]
def list_scenarios():
 return [{"id":s.id,"name":s.name,"description":s.description,"issue_label":s.issue_label,"unit":s.unit,"total_context":s.total_context,"default_max_rounds":s.default_max_rounds,"agents":[{"id":x.id,"role":x.role_label,"goal":x.goals,"constraint":x.constraints,"objective":x.objective,"direction":x.direction.value} for x in (s.side_a,s.side_b)]} for s in SCENARIOS.values()]

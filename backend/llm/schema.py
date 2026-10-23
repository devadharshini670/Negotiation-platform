from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class AgentInput:
    negotiation_id: str
    scenario_name: str
    issue_label: str
    unit: str
    context: str
    round: int
    max_rounds: int
    agent_id: str
    role: str
    personality: str
    personality_style: str
    direction: str
    goals: str
    constraints: str
    objective: str
    opening: float
    target: float
    limit: float
    own_last: Optional[float]
    opponent_role: str
    opponent_last: Optional[float]
    history: list
    concessions: list
    # --- added in Milestone 4 -------------------------------------------
    opponent_message: Optional[str] = None   # newest free-text message from the opponent
    opening_offer: Optional[float] = None    # personality-adjusted opening anchor
    reserve_now: Optional[float] = None      # least favourable value acceptable this round
    worst_offer: Optional[float] = None      # least favourable value the agent will propose
    max_step: Optional[float] = None         # largest single concession (absolute amount)
    opponent_concessions: Optional[list] = None  # opponent movement history (public information)
    workflow_mode: str = "simulation"
    opponent_repeats: int = 0                # times the opponent restated the same offer in a row

    def to_dict(self):
        return asdict(self)


@dataclass
class AgentDecision:
    action: str
    value: Optional[float]
    rationale: str
    confidence: float = 0.5
    source: str = "mock"
    raw: Optional[str] = None

    def to_dict(self):
        return asdict(self)

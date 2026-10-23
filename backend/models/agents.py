from dataclasses import dataclass, asdict
from models.state import Personality, Direction

# Negotiation behaviour per personality. Every value below is consumed by the
# decision engine (llm/mock_provider.py) *and* by the Orchestrator's validation
# (engine/offer_evaluator.py), so a personality changes real decisions - not
# just the description text.
#
#  rate            share of the remaining gap an agent closes per counteroffer
#  opening_shift   how far the opening anchor is pulled from the extreme
#                  opening toward the agent's target (0 = maximum anchor)
#  reserve_start   how far along target->limit the agent is willing to accept
#                  in round 1 (0 = only its target, 1 = its hard limit)
#  reserve_end     the same fraction at the final round. The agent will never
#                  go beyond it, which acts as a safety margin before the limit
#  max_step        largest single concession, as a share of the bargaining range
#  pressure_walk   how far beyond its hard limit an offer must be (as a share of
#                  the range) before the agent treats it as non-serious and
#                  walks away instead of countering (None = never walks away)
#
# Behaviour knobs added with the six newer personalities (every personality
# defines them; the three original ones keep their original values via _DEFAULTS):
#  round_pressure    how strongly the passing rounds raise the concession rate
#  late_boost        extra concession rate that builds toward the final round
#  tone              rate multipliers when the opponent's message reads as
#                    cooperative / pressuring (the rule engine's tone reader)
#  repeat_decay      how much of the rate survives each time the opponent
#                    restates its offer unchanged (lower = loses patience faster)
#  reciprocity_bonus rate multiplier when the opponent's last move was a concession
#  exploit           share of the rate withheld when the opponent just conceded
#  midpoint_gap      once the gap is within this share of the range, propose the midpoint
#  repeat_walk       walk away once the opponent has restated its offer this many
#                    times in a row (None = keep negotiating; deadlock handling decides)
_DEFAULTS = {"round_pressure": 1.0, "late_boost": 0.0, "repeat_decay": .5, "reciprocity_bonus": 1.0,
             "exploit": 0.0, "midpoint_gap": 0.0, "repeat_walk": None}

_BASE_PARAMS = {
    Personality.AGGRESSIVE: {
        "label": "Aggressive", "round_pressure": .5, "tone": {"cooperative": 1.10, "pressure": .60},
        "concession_rate": .12, "rate": .12, "opening_shift": 0.0,
        "reserve_start": .05, "reserve_end": .50, "max_step": .18, "pressure_walk": 1.5,
        "accept_threshold": .06,
        "style": "Firm and target-driven. Uses strong anchors, small concessions, applies pressure and protects leverage. Rarely compromises early.",
    },
    Personality.COLLABORATIVE: {
        "label": "Collaborative", "tone": {"cooperative": 1.25, "pressure": .80},
        "concession_rate": .30, "rate": .30, "opening_shift": .35,
        "reserve_start": .30, "reserve_end": .85, "max_step": .45, "pressure_walk": None,
        "accept_threshold": .15,
        "style": "Win-win oriented. Seeks a fair middle ground, opens with a reasonable anchor, makes steady, balanced concessions and looks for mutual benefit.",
    },
    Personality.RISK_AVERSE: {
        "label": "Risk-Averse", "tone": {"cooperative": 1.15, "pressure": .70},
        "concession_rate": .20, "rate": .20, "opening_shift": .20,
        "reserve_start": .25, "reserve_end": .75, "max_step": .30, "pressure_walk": 1.5,
        "accept_threshold": .20,
        "style": "Cautious and constraint-focused. Keeps a safety margin from its hard limit, avoids uncertain outcomes and prefers a defensible, certain agreement.",
    },
    Personality.COMPETITIVE: {
        "label": "Competitive", "round_pressure": .4, "tone": {"cooperative": 1.0, "pressure": .45},
        "concession_rate": .10, "rate": .10, "opening_shift": 0.0,
        "reserve_start": 0.0, "reserve_end": .35, "max_step": .14, "pressure_walk": 1.0,
        "accept_threshold": .05, "repeat_decay": .35, "repeat_walk": 2,
        "style": "Win-lose and results-driven. Anchors at the extreme, treats every concession as a loss, hardens under pressure and walks away from a counterpart who stonewalls instead of meeting halfway.",
    },
    Personality.EMPATHETIC: {
        "label": "Empathetic", "tone": {"cooperative": 1.30, "pressure": 1.05},
        "concession_rate": .34, "rate": .34, "opening_shift": .40,
        "reserve_start": .30, "reserve_end": .90, "max_step": .48, "pressure_walk": None,
        "accept_threshold": .18, "repeat_decay": .80, "reciprocity_bonus": 1.2,
        "style": "Relationship-focused. Acknowledges the other side's needs, opens generously, concedes warmly and stays patient even when the other side is slow to move.",
    },
    Personality.STRATEGIC: {
        "label": "Strategic", "round_pressure": .8, "late_boost": .16, "tone": {"cooperative": 1.15, "pressure": .75},
        "concession_rate": .16, "rate": .16, "opening_shift": .10,
        "reserve_start": .10, "reserve_end": .70, "max_step": .24, "pressure_walk": 1.8,
        "accept_threshold": .08, "repeat_decay": .5, "reciprocity_bonus": 1.35,
        "style": "Plans several moves ahead. Opens with a calculated anchor, trades concessions for reciprocity and saves its larger moves for later rounds when they buy a deal.",
    },
    Personality.OPPORTUNISTIC: {
        "label": "Opportunistic", "round_pressure": .6, "late_boost": .26, "tone": {"cooperative": 1.0, "pressure": .85},
        "concession_rate": .14, "rate": .14, "opening_shift": .05,
        "reserve_start": .08, "reserve_end": .80, "max_step": .32, "pressure_walk": 1.3,
        "accept_threshold": .10, "repeat_decay": .4, "exploit": .45,
        "style": "Exploits openings. Holds back when the other side is generous, concedes sharply near the deadline and takes any deal that clears its minimum late in the game.",
    },
    Personality.COMPROMISING: {
        "label": "Compromising", "tone": {"cooperative": 1.15, "pressure": .90},
        "concession_rate": .32, "rate": .32, "opening_shift": .30,
        "reserve_start": .35, "reserve_end": .85, "max_step": .42, "pressure_walk": None,
        "accept_threshold": .16, "repeat_decay": .85, "reciprocity_bonus": 1.1, "midpoint_gap": .22,
        "style": "Seeks the middle. Splits the difference as soon as the gap narrows, accepts fair deals early and keeps proposing meetings-in-the-middle even against a stubborn counterpart.",
    },
    Personality.ANALYTICAL: {
        "label": "Analytical", "late_boost": .06, "tone": {"cooperative": 1.0, "pressure": 1.0},
        "concession_rate": .22, "rate": .22, "opening_shift": .25,
        "reserve_start": .30, "reserve_end": .62, "max_step": .26, "pressure_walk": 2.0,
        "accept_threshold": .12, "repeat_decay": .6,
        "style": "Data-driven and even-tempered. Calibrates every move to the size of the remaining gap, ignores tone and pressure, and holds a tight, consistent acceptance band.",
    },
}
PERSONALITY_PARAMS = {k: {**_DEFAULTS, **v} for k, v in _BASE_PARAMS.items()}
PERSONALITY_LABELS = {k.value: v["label"] for k, v in PERSONALITY_PARAMS.items()}


@dataclass
class AgentConfig:
    id: str
    role_label: str
    personality: Personality
    direction: Direction
    opening: float
    target: float
    limit: float
    issue_label: str
    goals: str
    constraints: str
    objective: str

    def to_dict(self):
        d = asdict(self)
        d["personality"] = self.personality.value
        d["direction"] = self.direction.value
        return d

    def range_span(self):
        return max(abs(self.opening - self.limit), 1e-9)

    def satisfies_limit(self, v):
        return v >= self.limit if self.direction == Direction.MAXIMIZE else v <= self.limit

    def clamp(self, v):
        return max(v, self.limit) if self.direction == Direction.MAXIMIZE else min(v, self.limit)

    def distance(self, a, b):
        return abs(a - b)

    # ---- personality-driven helpers ----------------------------------
    def params(self):
        return PERSONALITY_PARAMS[self.personality]

    def value_at(self, frac):
        """Value located ``frac`` of the way from the agent's target to its hard limit."""
        return self.target + frac * (self.limit - self.target)

    def reserve_fraction(self, round_no, max_rounds):
        p = self.params()
        progress = 0.0 if max_rounds <= 1 else min(max(round_no - 1, 0) / (max_rounds - 1), 1.0)
        return p["reserve_start"] + (p["reserve_end"] - p["reserve_start"]) * progress

    def acceptance_value(self, round_no, max_rounds):
        """Least favourable value this agent will accept in the given round."""
        return self.value_at(self.reserve_fraction(round_no, max_rounds))

    def worst_offer(self):
        """Least favourable value the agent will ever *propose* (its safety margin)."""
        return self.value_at(self.params()["reserve_end"])

    def opening_offer(self):
        return self.opening + self.params()["opening_shift"] * (self.target - self.opening)

    def satisfaction(self, value):
        """Objective satisfaction 0-100: 0 at the hard limit, 100 at the ideal opening value."""
        if value is None:
            return None
        span = self.range_span()
        gained = (value - self.limit) if self.direction == Direction.MAXIMIZE else (self.limit - value)
        return round(max(0.0, min(100.0, gained / span * 100)), 1)

    def conceded_amount(self, previous, new):
        """Positive when the move from ``previous`` to ``new`` favours the opponent."""
        return (previous - new) if self.direction == Direction.MAXIMIZE else (new - previous)


def personality_params(p):
    return PERSONALITY_PARAMS[p]

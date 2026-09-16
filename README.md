# The Table — AI Negotiation Suite

A professional multi-agent negotiation platform implementing the supplied Milestone 1 and Milestone 2 requirements.

## Architecture
User → Scenario → Agent Strategy → Readiness → Orchestrator → Agent reasoning → Validation → State update → Outcome

The Orchestrator is authoritative for turns, rounds, state transitions and hard constraints. LLM output is advisory and schema-validated.

## Features
- Vendor Pricing, Job Offer and Project Budget scenarios
- Independent Agent A/B personalities: Aggressive, Collaborative, Risk-Averse
- Simulation-ready AI-vs-AI workflow
- Deterministic rule-based fallback
- Real Anthropic LLM integration through backend
- Structured agent input and structured response validation
- Offer evaluation, counteroffers and concession tracking
- Multi-round negotiation with agreement/rejection/deadlock/max-round termination
- Professional nude/neutral light theme
- Live Orchestrator visualization
- Outcome analytics and session history

## Real LLM
Copy `backend/.env.example` to `backend/.env` and set:

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your_key
LLM_MODEL=claude-3-5-haiku-latest
```

Never commit `.env`.

## Run

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open `frontend/index.html` in a browser. If your browser blocks local fetches, serve the frontend with a simple static server such as `python -m http.server 5500` from the frontend directory.

## Milestones
Milestone 1: scenarios, agent persona model, configuration workflow, architecture and negotiation-state foundation.

Milestone 2: state model, orchestrator, agent input, LLM provider, structured decisions, offer evaluation, counteroffers, concession tracking and multi-round flow.


### UI Polish Update
Professional light nude/taupe theme with medium-sized typography, stronger hierarchy, improved spacing, and refined responsive presentation.

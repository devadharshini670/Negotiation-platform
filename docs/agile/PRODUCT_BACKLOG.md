# Agile Product Backlog & Epic Breakdown

## Project Title
**The Table — AI Negotiation Suite**

---

## 1. Product Vision & Target Personas

### Product Vision
To provide a structured AI negotiation environment where users can configure realistic negotiation scenarios and agent personalities, execute controlled multi-round bargaining, enforce constraints safely, and inspect negotiation state and outcomes.

### Target Personas
1. **Scenario User / Learner**: Selects a negotiation scenario and configures the participants to explore negotiation behaviour.
2. **Negotiation Participant**: Participates in Practice Mode as Agent A while the other participant is controlled by the platform.
3. **Platform Developer / Evaluator**: Requires deterministic state transitions, validation, LLM fallback behaviour, testability and transparent outcome reporting.

---

## 2. Definition of Done (DoD)

A user story or feature is considered **Done** only when all applicable criteria are met:

- [x] **Code Complete:** Required functionality is implemented in the relevant backend/frontend module.
- [x] **Integration Complete:** The feature is connected to the negotiation state flow or UI/API where applicable.
- [x] **Validation & Safety:** Invalid actions and hard-constraint violations are handled safely.
- [x] **Testing:** Existing automated tests continue to pass and relevant behaviour is verified.
- [x] **Documentation:** README/milestone traceability is updated for milestone capabilities.
- [x] **Review Ready:** The feature is suitable for sprint demonstration and technical review.

---

## 3. Product Epics & Story Cards

### Epic 1: Scenario & Agent Foundation

| Story ID | Story Title | User Story Description | Priority | Story Points | Status |
|:---|:---|:---|:---:|:---:|:---:|
| **US-SCN-01** | Predefined Negotiation Scenarios | *As a user, I want Vendor Pricing, Job Offer and Project Budget scenarios so that I can start negotiation from a defined context.* | MUST | 5 SP | DONE |
| **US-SCN-02** | Two-Agent Representation | *As a user, I want two negotiating agents with roles, direction, opening, target, limit, goals, constraints and objectives so that each negotiation has explicit participants.* | MUST | 5 SP | DONE |
| **US-SCN-03** | Independent Personality Selection | *As a user, I want Agent A and Agent B to select personalities independently so that different negotiation behaviours can be combined.* | MUST | 3 SP | DONE |
| **US-SCN-04** | Scenario-to-State Workflow | *As a user, I want scenario selection and agent configuration to create a valid negotiation state so that the negotiation can begin consistently.* | MUST | 5 SP | DONE |

### Epic 2: Negotiation State & Orchestration

| Story ID | Story Title | User Story Description | Priority | Story Points | Status |
|:---|:---|:---|:---:|:---:|:---:|
| **US-ORC-01** | Turn and Round Tracking | *As the negotiation engine, I want to track the current round and active agent so that turns progress deterministically.* | MUST | 3 SP | DONE |
| **US-ORC-02** | Negotiation History | *As a user, I want offers, counteroffers, actions and conversation history recorded so that the negotiation can be reviewed.* | MUST | 5 SP | DONE |
| **US-ORC-03** | Deterministic Orchestration | *As the platform, I want deterministic turn and round management so that negotiation state transitions are predictable.* | MUST | 8 SP | DONE |
| **US-ORC-04** | Terminal Conditions | *As the platform, I want agreement, rejection and maximum-round termination rules so that every negotiation reaches a defined outcome.* | MUST | 5 SP | DONE |
| **US-ORC-05** | Orchestrator Visualization | *As a user, I want to see orchestrator stages in the negotiation UI so that the multi-agent workflow is understandable.* | SHOULD | 3 SP | DONE |

### Epic 3: Agent Reasoning & LLM Integration

| Story ID | Story Title | User Story Description | Priority | Story Points | Status |
|:---|:---|:---|:---:|:---:|:---:|
| **US-LLM-01** | Standard AgentInput Contract | *As the negotiation engine, I want a standard AgentInput structure so that every reasoning provider receives consistent state.* | MUST | 3 SP | DONE |
| **US-LLM-02** | Deterministic Agent Reasoning | *As the platform, I want mock/deterministic reasoning so that negotiations remain executable without an external LLM.* | MUST | 5 SP | DONE |
| **US-LLM-03** | Anthropic Provider | *As the platform, I want an Anthropic LLM provider so that agents can use real model-based reasoning when configured.* | MUST | 5 SP | DONE |
| **US-LLM-04** | Structured Decision Validation | *As the platform, I want agent decisions validated before state update so that malformed or unsafe model output cannot directly mutate state.* | MUST | 5 SP | DONE |
| **US-LLM-05** | Safe LLM Fallback | *As the platform, I want deterministic fallback when LLM execution is unavailable so that negotiation can continue safely.* | SHOULD | 3 SP | DONE |

### Epic 4: Offer Evaluation & Negotiation Intelligence

| Story ID | Story Title | User Story Description | Priority | Story Points | Status |
|:---|:---|:---|:---:|:---:|:---:|
| **US-OFR-01** | Hard-Limit Validation | *As the platform, I want opening and counteroffer values checked against hard limits so that protected constraints are not violated.* | MUST | 5 SP | DONE |
| **US-OFR-02** | Safe Proposal Correction | *As the platform, I want invalid proposals corrected safely so that malformed values do not break the negotiation.* | MUST | 3 SP | DONE |
| **US-OFR-03** | Concession Tracking | *As a user, I want concession delta and cumulative concession percentage tracked so that negotiation movement can be understood.* | MUST | 5 SP | DONE |
| **US-OFR-04** | Offer Favourability | *As a user, I want offers classified against agent targets so that the quality of each proposal can be interpreted.* | SHOULD | 3 SP | DONE |
| **US-OFR-05** | Outcome Reporting | *As a user, I want a structured outcome report so that the final negotiation result can be reviewed.* | SHOULD | 5 SP | DONE |

### Epic 5: Practice Mode, UI & Analytics

| Story ID | Story Title | User Story Description | Priority | Story Points | Status |
|:---|:---|:---|:---:|:---:|:---:|
| **US-UI-01** | Human Practice Mode | *As a participant, I want to act as Agent A so that I can practice negotiation against the other agent.* | MUST | 5 SP | DONE |
| **US-UI-02** | Live Negotiation Interface | *As a user, I want a live transcript and progress display so that I can follow the negotiation as it happens.* | MUST | 5 SP | DONE |
| **US-UI-03** | Negotiation Intelligence Panels | *As a user, I want concession and negotiation-intelligence panels so that negotiation movement is visible.* | SHOULD | 3 SP | DONE |
| **US-UI-04** | Session History & Dashboard | *As a user, I want session history and dashboard metrics so that previous negotiation outcomes can be inspected.* | SHOULD | 5 SP | DONE |
| **US-UI-05** | UI/UX Polish | *As a user, I want a consistent professional interface so that the platform is easier to use and demonstrate.* | SHOULD | 2 SP | DONE |

### Epic 6: Quality Assurance & Release Hardening

| Story ID | Story Title | User Story Description | Priority | Story Points | Status |
|:---|:---|:---|:---:|:---:|:---:|
| **US-QA-01** | Scenario Verification | *As a developer, I want all three scenarios tested so that the scenario foundation is regression-checked.* | MUST | 3 SP | DONE |
| **US-QA-02** | Multi-Round Verification | *As a developer, I want the multi-round negotiation lifecycle tested so that turn/round behaviour is verified.* | MUST | 5 SP | DONE |
| **US-QA-03** | Personality Verification | *As a developer, I want independent personality assignment tested so that Agent A and Agent B configuration remains independent.* | MUST | 5 SP | DONE |
| **US-QA-04** | Runnable Project Setup | *As a developer, I want runnable setup and environment instructions so that the project can be executed consistently.* | MUST | 5 SP | DONE |

---

## 4. Milestone Traceability

### Milestone 1 — Scenario & Agent Foundation

| Capability | Status |
|:---|:---:|
| Multi-agent negotiation representation | DONE |
| Simulation / AI-vs-AI workflow | DONE |
| Three predefined scenarios | DONE |
| Two agents per scenario | DONE |
| Role, goal, constraint and objective | DONE |
| Aggressive / Collaborative / Risk-Averse personalities | DONE |
| Independent personality selection | DONE |
| Scenario → Agent Configuration | DONE |
| Agent Configuration → Negotiation State | DONE |
| Architecture/workflow representation | DONE |

### Milestone 2 — Orchestration, Reasoning & Intelligence

| Capability | Status |
|:---|:---:|
| Current round and current agent/turn | DONE |
| Offers and counteroffers | DONE |
| Accept/reject decisions | DONE |
| Negotiation status | DONE |
| Conversation history | DONE |
| Deterministic Orchestrator | DONE |
| Turn and round management | DONE |
| Standard AgentInput | DONE |
| Anthropic LLM interface | DONE |
| Mock/deterministic fallback | DONE |
| Structured LLM response | DONE |
| Server-side validation | DONE |
| Offer evaluation | DONE |
| Counteroffer generation | DONE |
| Concession tracking | DONE |
| Constraint protection | DONE |
| Agreement/rejection/max-round termination | DONE |
| Multi-round flow | DONE |
| Live Orchestrator visualization | DONE |
| Outcome report | DONE |
| Dashboard metrics from backend state | DONE |

---

**Backlog total:** **123 SP** (reconstructed planning estimate).

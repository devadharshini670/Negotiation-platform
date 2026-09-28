# Agile Sprint Plans (Week 01 to Week 06)

## Project Title
**The Table — AI Negotiation Suite**

---

## Sprint Overview Summary

| Sprint | Week | Primary Theme | Story Points Committed | Story Points Completed | Velocity |
|:---:|:---:|:---|:---:|:---:|:---:|
| **Sprint 1** | Week 1 (Aug 19-25) | Requirements, Architecture, Scenarios & Agent Foundation | 18 | 18 | 100% |
| **Sprint 2** | Week 2 (Aug 26-Sep 01) | Agent Personalities, Configuration & State Foundation | 20 | 20 | 100% |
| **Sprint 3** | Week 3 (Sep 02-08) | Orchestrator, Turn/Round State & Core Negotiation Engine | 28 | 28 | 100% |
| **Sprint 4** | Week 4 (Sep 09-15) | LLM Integration, Validation, Offers & Concessions | 25 | 25 | 100% |
| **Sprint 5** | Week 5 (Sep 16-22) | Practice Mode, UI Integration, Reporting & Dashboard | 22 | 22 | 100% |
| **Sprint 6** | Week 6 (Sep 23-24) | Testing, UI Polish, Traceability & Final Hardening | 10 | 10 | 100% |
| **Total** | **6 Weeks (27 Working Days)** | **End-to-End AI Negotiation Platform Delivery** | **123** | **123** | **100%*** |

*Story-point and velocity values are reconstructed documentation estimates rather than historical measurements stored in the repository.

---

## Sprint 1: Requirements, Architecture, Scenarios & Agent Foundation

**Duration:** Week 1 (19-25 Aug 2026)  
**Sprint Goal:** Establish the negotiation-platform problem space, architecture, core scenarios and reusable agent representation.

### Committed User Stories

- **US-SCN-01:** Provide three predefined negotiation scenarios. **(5 SP)**
- **US-SCN-02:** Represent two negotiating agents and their negotiation parameters. **(5 SP)**
- **US-SCN-04:** Establish the scenario-to-agent-configuration workflow. **(5 SP)**
- **US-QA-04:** Establish runnable backend/frontend project structure and environment setup. **(5 SP)**

### Granular Task Breakdown

1. Define the multi-agent negotiation use case and scenario boundaries.
2. Establish Vendor Pricing, Job Offer and Project Budget scenario definitions.
3. Define agent role, direction, opening, target, hard limit, goals, constraints and objective.
4. Establish the frontend/backend project boundary and initial API flow.
5. Establish runnable project setup and milestone traceability.

### Sprint Review & Demo

- **Demoed:** Scenario selection and core agent configuration foundation.
- **Delivered:** Milestone 1 scenario and agent foundation.

---

## Sprint 2: Agent Personalities, Configuration & State Foundation

**Duration:** Week 2 (26 Aug-01 Sep 2026)  
**Sprint Goal:** Make both negotiating agents independently configurable and establish the state structures required for negotiation execution.

### Committed User Stories

- **US-SCN-03:** Independent Agent A/B personality selection. **(3 SP)**
- **US-ORC-01:** Current round and current turn tracking. **(3 SP)**
- **US-ORC-02:** Offer/history state representation. **(5 SP)**
- **US-LLM-01:** Standard AgentInput contract foundation. **(3 SP)**
- **US-LLM-02:** Deterministic/mock decision foundation. **(5 SP)**
- **US-ORC-05:** Orchestrator visualization foundation. **(3 SP)**

### Granular Task Breakdown

1. Implement Aggressive, Collaborative and Risk-Averse personality definitions.
2. Allow Agent A and Agent B to select personalities independently.
3. Build negotiation state with agents, current round, current turn and status.
4. Add offer/action/history data structures.
5. Prepare the standardized input structure for agent reasoning.
6. Prepare the UI state required to visualize the orchestration flow.

### Sprint Review & Demo

- **Demoed:** Independent agent configuration and negotiation-state creation.
- **Delivered:** Personality-driven negotiation and state foundation.

---

## Sprint 3: Orchestrator, Turn/Round State & Core Negotiation Engine

**Duration:** Week 3 (02-08 Sep 2026)  
**Sprint Goal:** Implement deterministic orchestration for turns, rounds, state transitions, termination and multi-round negotiation.

### Committed User Stories

- **US-ORC-03:** Deterministic turn and round management. **(8 SP)**
- **US-ORC-04:** Agreement/rejection/max-round termination. **(5 SP)**
- **US-ORC-02:** Conversation history and offer persistence. **(5 SP)**
- **US-QA-02:** Multi-round negotiation lifecycle verification. **(5 SP)**
- **US-LLM-02:** Deterministic reasoning integration. **(5 SP)**

### Granular Task Breakdown

1. Implement orchestrator step execution.
2. Load the active agent and construct its current negotiation input.
3. Generate a decision and validate it before state mutation.
4. Append offers, counters and messages to public history.
5. Switch turns and increment rounds deterministically.
6. Implement agreement, rejection, deadlock and maximum-round outcomes.
7. Verify the multi-round negotiation lifecycle.

### Sprint Review & Demo

- **Demoed:** Multi-round negotiation progressing through turns and terminating with a defined outcome.
- **Delivered:** Deterministic orchestrator and core negotiation lifecycle.

---

## Sprint 4: LLM Integration, Validation, Offers & Concessions

**Duration:** Week 4 (09-15 Sep 2026)  
**Sprint Goal:** Add real LLM reasoning while retaining deterministic fallback, enforce server-side validation and provide negotiation intelligence.

### Committed User Stories

- **US-LLM-03:** Anthropic LLM provider. **(5 SP)**
- **US-LLM-04:** Structured response validation. **(5 SP)**
- **US-LLM-05:** Deterministic fallback. **(3 SP)**
- **US-OFR-01:** Hard-limit validation. **(5 SP)**
- **US-OFR-03:** Concession tracking. **(5 SP)**
- **US-OFR-04:** Offer favourability classification. **(3 SP)**

### Granular Task Breakdown

1. Add Anthropic provider configuration and availability detection.
2. Define structured JSON response requirements for agent decisions.
3. Parse and validate LLM output before state mutation.
4. Fall back to deterministic reasoning when the real provider is unavailable.
5. Protect hard constraints and private targets.
6. Correct invalid proposal values safely.
7. Track concession delta, percentage of range and cumulative movement.
8. Add offer classification relative to agent target.

### Sprint Review & Demo

- **Demoed:** LLM-capable negotiation with structured validation and deterministic fallback.
- **Delivered:** LLM reasoning, validation and negotiation-intelligence capability set.

---

## Sprint 5: Practice Mode, UI Integration, Reporting & Dashboard

**Duration:** Week 5 (16-22 Sep 2026)  
**Sprint Goal:** Expose the negotiation engine through usable simulation/practice workflows and provide outcome analytics.

### Committed User Stories

- **US-UI-01:** Human Agent A Practice Mode. **(5 SP)**
- **US-UI-02:** Live transcript/progress interface. **(5 SP)**
- **US-UI-03:** Negotiation intelligence/concession panels. **(3 SP)**
- **US-OFR-05:** Outcome report. **(5 SP)**
- **US-UI-04:** Session history/dashboard metrics. **(5 SP)**

### Granular Task Breakdown

1. Add human-action API for Practice Mode.
2. Add human proposal/message controls to the negotiation screen.
3. Render live transcript, participants and orchestrator stages.
4. Add negotiation intelligence and concession movement.
5. Add outcome report endpoint.
6. Add dashboard statistics and recent-session history.

### Sprint Review & Demo

- **Demoed:** AI-vs-AI simulation and human Practice Mode with live negotiation state and outcome information.
- **Delivered:** End-to-end negotiation workflow exposed through the frontend.

---

## Sprint 6: Testing, UI Polish, Traceability & Final Hardening

**Duration:** Week 6 (23-24 Sep 2026)  
**Sprint Goal:** Verify the integrated platform, refine the presentation and finalize the current release and Agile traceability.

### Committed User Stories

- **US-QA-01:** Test all three scenarios. **(3 SP)**
- **US-QA-03:** Test independent personality assignment. **(5 SP)**
- **US-UI-05:** UI/UX polish. **(2 SP)**

### Granular Task Breakdown

1. Run the automated PyTest suite.
2. Verify three scenario creation.
3. Verify the multi-round lifecycle and personality assignment.
4. Review README and milestone traceability.
5. Refine the UI presentation and documentation.
6. Finalize the Agile record for the current project period.

### Sprint Review & Demo

- **Verification Result:** 3 automated tests passed in the supplied project ZIP.
- **Delivered:** Current Milestone 1 and Milestone 2 capability set documented and traceable.

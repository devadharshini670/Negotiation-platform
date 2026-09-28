# Agile Metrics, Burn-Up & Sprint Retrospectives

## Project Title
**The Table — AI Negotiation Suite**

**Project Period:** 19 August 2026 - 24 September 2026

> Story-point figures below are reconstructed Agile planning/documentation estimates, not historical measurements stored in the repository. Test results are based on the supplied project ZIP.

---

## 1. Velocity & Sprint Performance Metrics

Across the documented project period, the engineering work is organized into six sprint iterations.

| Sprint ID | Week | Target Story Points | Completed Story Points | Completion Rate | Defects Reported | Defects Resolved |
|:---:|:---:|---:|---:|:---:|:---:|:---:|
| **Sprint 1** | Week 1 | 18 SP | 18 SP | 100%* | Not recorded | Not recorded |
| **Sprint 2** | Week 2 | 20 SP | 20 SP | 100%* | Not recorded | Not recorded |
| **Sprint 3** | Week 3 | 28 SP | 28 SP | 100%* | Not recorded | Not recorded |
| **Sprint 4** | Week 4 | 25 SP | 25 SP | 100%* | Not recorded | Not recorded |
| **Sprint 5** | Week 5 | 22 SP | 22 SP | 100%* | Not recorded | Not recorded |
| **Sprint 6** | Week 6 | 10 SP | 10 SP | 100%* | Not recorded | Not recorded |
| **TOTAL** | **6 Weeks** | **123 SP** | **123 SP** | **100%*** | **Not recorded** | **Not recorded** |

*Completion figures are reconstructed documentation values based on the current capability grouping; the repository does not contain historical sprint velocity or defect-register records.

---

## 2. Story Point Burn-Up & Cumulative Flow Trajectory

```text
Cumulative Story Points (Total: 123 SP)

123 |                                      * [SP-06: 123 SP]
110 |
100 |
 90 |                            * [SP-05: 113 SP]
 80 |
 70 |
 60 |                    * [SP-03: 66 SP]
 50 |
 40 |              * [SP-02: 38 SP]
 30 |
 20 |        * [SP-01: 18 SP]
 10 |
  0 +---------------------------------------------------------
       W1        W2        W3        W4        W5        W6
```

- **Average Planned Velocity:** 20.50 Story Points / Sprint.
- **Cumulative Story Points:** 123 SP.
- **Burn-Up Health:** The trajectory is a reconstructed documentation view, not a historical Agile measurement.
- **Test Pass Rate:** 100% of the supplied automated tests (3/3) passed.

---

## 3. Sprint-by-Sprint Retrospective Analysis

### Sprint 1 — Requirements & Agent Foundation

- **What Went Well:** Scenario boundaries and reusable agent representation established a clear foundation.
- **What Could Be Improved:** Requirements and Agile ceremony records were not maintained as separate historical artifacts.
- **Action Item:** Maintain explicit backlog and sprint records during future development.

### Sprint 2 — Personalities & State Foundation

- **What Went Well:** Independent personality configuration and explicit negotiation state support the multi-agent model.
- **What Could Be Improved:** State design should remain separated from UI-specific concerns.
- **Action Item:** Keep backend state authoritative and derive UI state from backend responses.

### Sprint 3 — Orchestration & Core Engine

- **What Went Well:** The deterministic orchestrator provides a clear authority for turn, round, validation and termination behaviour.
- **What Could Be Improved:** Orchestrator complexity should remain isolated from provider-specific reasoning.
- **Action Item:** Preserve provider abstraction and keep state transitions in the orchestrator.

### Sprint 4 — LLM & Negotiation Intelligence

- **What Went Well:** Real LLM reasoning was added without making the platform dependent on it; deterministic fallback remains available.
- **What Could Be Improved:** External LLM calls introduce response-format and availability uncertainty.
- **Action Item:** Continue enforcing structured response validation and safe fallback behaviour.

### Sprint 5 — Practice, UI & Reporting

- **What Went Well:** Practice Mode, live transcript, orchestrator visualization, reports and dashboard metrics turned the engine into a demonstrable application.
- **What Could Be Improved:** Frontend/backend state synchronization needs continued regression testing.
- **Action Item:** Add additional API/UI integration tests around practice actions and reporting.

### Sprint 6 — QA & Final Hardening

- **What Went Well:** The current repository is traceable to the Milestone 1 and Milestone 2 capability set, and the supplied automated tests pass.
- **What Could Be Improved:** Historical daily standup and story-point records were not maintained during development.
- **Action Item:** Keep future Agile artifacts alongside the codebase so actual velocity and daily activity can be measured directly.

---

## 4. Key Engineering Takeaways

| Area | Engineering Learning |
|:---|:---|
| **Deterministic Orchestration** | The orchestrator is the authority for turns, rounds, terminal conditions and protected state transitions. |
| **Provider Abstraction** | Mock and real LLM reasoning can share the same AgentInput/AgentDecision contract. |
| **Constraint Protection** | LLM output should be treated as advisory and validated before it can modify negotiation state. |
| **State-Driven UI** | Frontend views are more reliable when derived from backend negotiation state. |
| **Negotiation Analytics** | Offer history and concession records make negotiation behaviour observable. |
| **Testing** | Scenario, lifecycle and personality tests provide a regression layer for the core engine. |

---

## 5. Final Engineering Outcome

The current implementation provides an end-to-end multi-agent negotiation workflow covering scenario selection, agent configuration, personality-driven reasoning, deterministic orchestration, optional Anthropic LLM reasoning, server-side validation, offer/counteroffer handling, concession tracking, multi-round termination, Practice Mode, live orchestration visualization, outcome reporting and dashboard analytics.

---

## 6. Verification Evidence

| Verification Item | Result |
|:---|:---:|
| Automated tests executed | **3** |
| Automated tests passed | **3** |
| Test pass rate | **100%** |
| Three scenarios covered | **Yes** |
| Multi-round lifecycle covered | **Yes** |
| Independent personality assignment covered | **Yes** |
| Anthropic provider | **Implemented; requires configured API key** |
| Deterministic fallback | **Implemented** |

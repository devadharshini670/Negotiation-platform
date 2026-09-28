# 6-Week Agile Project Framework & Lifecycle

## Project Title
**The Table — AI Negotiation Suite**

---

## 1. Executive Summary & Project Context

This repository represents the work completed over a **6-week Agile development period** from **19 August 2026 to 24 September 2026**, covering **27 working days**. The engineering process is documented using the **Agile Scrum Framework** with short sprint cycles.

The objective of the project was to develop an AI-based multi-agent negotiation platform capable of scenario selection, independent agent configuration, personality-driven negotiation, deterministic multi-round orchestration, optional LLM reasoning, constraint validation, Practice Mode, outcome reporting and dashboard analytics.

> **Documentation basis:** The Agile records are reconstructed from the supplied project repository, milestone checklist, implemented source modules, tests and the supplied reference Agile documentation. Story-point values are planning/documentation estimates rather than historical measurements stored in the repository.

---

## 2. Agile Project Cadence & Structure

```text
+------------------------------------------------------------------------------------------------+
|                              6-WEEK SPRINT CADENCE (27 DAYS)                                  |
+------------------------------------------------------------------------------------------------+
| Week 1 (Aug 19-25) : Sprint 1 - Requirements, Architecture, Scenarios & Agent Foundation     |
| Week 2 (Aug 26-Sep 01) : Sprint 2 - Agent Personalities, Configuration & State Foundation    |
| Week 3 (Sep 02-08) : Sprint 3 - Orchestrator, Turns/Rounds & Core Negotiation Engine         |
| Week 4 (Sep 09-15) : Sprint 4 - LLM Integration, Validation & Negotiation Intelligence      |
| Week 5 (Sep 16-22) : Sprint 5 - Practice Mode, UI Integration, Reporting & Dashboard        |
| Week 6 (Sep 23-24) : Sprint 6 - Testing, UI Polish, Traceability & Final Hardening           |
+------------------------------------------------------------------------------------------------+
```

### Daily & Weekly Scrum Ceremonies

- **Daily Standup:** Short progress sync covering yesterday's work, today's plan, blockers and technical learnings.
- **Sprint Planning:** Define sprint backlog, estimate user stories and agree the sprint goal.
- **Backlog Refinement:** Break complex negotiation-platform work into implementable stories and refine acceptance expectations.
- **Sprint Review & Demo:** Demonstrate the completed increment, including negotiation scenarios, orchestration, UI and analytics where applicable.
- **Sprint Retrospective:** Record what went well, what needs improvement and actionable commitments for the next sprint.

---

## 3. Sprint-by-Sprint Milestone Summary

| Sprint | Week | Primary Focus Area | Delivered Features | Story Points | Velocity Status |
|:---:|:---:|:---|:---|:---:|:---:|
| **SP-01** | W1 (Aug 19-25) | Requirements & Agent Foundation | Three scenarios, two-agent model, scenario-to-agent configuration and runnable project foundation | 18 SP | 100% Completed |
| **SP-02** | W2 (Aug 26-Sep 01) | Personalities & State Foundation | Independent personalities, negotiation state, AgentInput and deterministic reasoning foundation | 20 SP | 100% Completed |
| **SP-03** | W3 (Sep 02-08) | Orchestration & Core Engine | Turn/round management, history, terminal conditions and multi-round lifecycle | 28 SP | 100% Completed |
| **SP-04** | W4 (Sep 09-15) | LLM & Negotiation Intelligence | Anthropic provider, structured validation, fallback, hard-limit protection and concessions | 25 SP | 100% Completed |
| **SP-05** | W5 (Sep 16-22) | Practice, UI & Reporting | Practice Mode, live transcript, orchestrator visualization, outcome reporting and dashboard metrics | 22 SP | 100% Completed |
| **SP-06** | W6 (Sep 23-24) | QA & Final Hardening | Scenario/lifecycle/personality verification, UI refinement and documentation traceability | 10 SP | 100% Completed |
| **TOTAL** | **6 Wks** | **Full Platform Delivery** | **End-to-End AI Negotiation Platform capability set** | **123 SP** | **100% Delivered*** |

*The completion and story-point figures are reconstructed Agile documentation values, not historical velocity measurements stored in the repository.*

---

## 4. Documentation Index

The complete Agile documentation suite is organized across the following detailed documents:

1. [**Product Backlog & Epics (`PRODUCT_BACKLOG.md`)**](./PRODUCT_BACKLOG.md)
   - Comprehensive epic breakdowns, user stories, MoSCoW prioritization, story points, milestone traceability and Definition of Done.
2. [**Sprint Plans (Week 1 to Week 6) (`SPRINT_PLANS_W01_TO_W06.md`)**](./SPRINT_PLANS_W01_TO_W06.md)
   - Sprint goals, committed stories, task breakdowns, sprint reviews and demo notes for all six sprints.
3. [**27-Day Daily Standup Logs (`DAILY_STANDUP_LOGS_27_DAYS.md`)**](./DAILY_STANDUP_LOGS_27_DAYS.md)
   - Daily entries from Day 01 through Day 27 documenting reconstructed work, blockers and technical insights.
4. [**Agile Metrics, Burn-Up & Retrospective (`RETROSPECTIVE_AND_METRICS.md`)**](./RETROSPECTIVE_AND_METRICS.md)
   - Story-point velocity, cumulative trajectory, sprint retrospectives, verification evidence and engineering learnings.

---

## 5. Team Roles & RACI Matrix

| Role | Responsibility |
|:---|:---|
| **Student Developer / Engineering Team** | Scenario modeling, agent configuration, negotiation state, orchestrator, LLM integration, backend APIs, frontend integration and testing. |
| **Project Mentor / Technical Lead** | Architecture review, milestone guidance, technical review and issue clarification. |
| **Product / Project Lead** | Requirement validation, scenario acceptance, backlog prioritization and milestone confirmation. |
| **Scrum / Agile Coordinator** | Sprint planning, standup tracking, review documentation, retrospective records and Agile process adherence. |

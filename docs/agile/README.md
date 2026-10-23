# Agile Project Framework & Lifecycle (Original Six Sprints + Latest Update)

## Project Title
**The Table — AI Negotiation Suite**

---

## 1. Executive Summary & Project Context

The original sprint records cover **19 August 2026 to 24 September 2026** across six sprints and 27 working days. A separately dated **Week 7 repository update on 23 October 2026** records the latest team increment without changing the original sprint history. The engineering process is documented using the **Agile Scrum Framework** with short sprint cycles.

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

### Latest Repository Update — Week 7 (23 October 2026)

| Update | Date | Source | Scope recorded |
|:---|:---|:---|:---|
| Latest platform increment | 23 October 2026 | [Commit `6c848ac`](https://github.com/devadharshini670/Negotiation-platform/commit/6c848ac), `Add latest updated negotiation platform` | Milestone traceability through Milestones 1–4; Practice Mode; deadlock handling; outcome analysis; downloadable transcripts/reports; account/security workflows; gamification/leaderboard; responsive UI and browser-check evidence. |

This is a later repository update, not a retroactive change to the six original sprint dates or their reconstructed story-point estimates. The commit checklist reports 65 automated tests and headless-browser runs; those are repository-reported results and were not independently rerun for this document update.

### Full Week 7 Capability Inventory — Verified Against the Uploaded Repository Snapshot

The uploaded repository snapshot's `README.md` and `MILESTONE_CHECKLIST.md` describe the following current platform scope. These are repository-documented capabilities; test claims are not represented as independently rerun here.

**Negotiation and agent engine**
- Nine predefined scenarios: Vendor Pricing, Job Offer, Project Budget Allocation, Freelance Contract, Real Estate Price, Software Development Contract, Salary & Benefits, Supplier Contract Renewal, and Project Deadline.
- Nine personalities: Aggressive, Collaborative, Risk-Averse, Competitive, Empathetic, Strategic, Opportunistic, Compromising, and Analytical.
- Agent configuration includes roles, goals, constraints, objectives, opening/target/hard-limit values, negotiation mode, engine/provider/model, and maximum rounds.
- Simulation Mode (AI vs AI) and Practice Mode (human vs AI); offers, counteroffers, accept/reject actions and free-text messages.
- Orchestrator-controlled turns, rounds, history, state transitions, hard-constraint enforcement, terminal conditions and per-negotiation locking.
- Structured LLM reasoning through Groq or Google Gemini, with a deterministic personality-driven rule engine and fallback.
- Offer validation, concession/hold/retreat tracking, deadlock detection, mediated midpoint settlement or explained breakdown.

**Analysis, reporting and replay**
- Live negotiation transcript, per-turn explanation, stance indicators, orchestrator activity log, round/gap/concession/deadlock metrics and offer-movement chart.
- Outcome screen with final status, agreement terms, rounds, objective satisfaction, concession timeline/chart, agent performance, deadlock information and insights.
- Platform-wide analytics derived from recorded sessions rather than hard-coded totals.
- Downloadable `.txt` transcript, self-contained `.html` Negotiation Report suitable for printing to PDF, `.json` report data, and a print-ready Negotiation Certificate for completed sessions.
- Replay scrubber that replays negotiation rounds and updates the chart/timeline; Deal Momentum gauge; agent avatars; command palette, dark-mode toggle and reduced-motion-aware agreement celebration.

**Accounts, privacy and security**
- Email/password registration and sign-in with email verification; Google and GitHub OAuth 2.0.
- Password hashing, one-time password-reset links, login lockout/rate limiting, HTTP-only same-site sessions with inactivity expiry, CSRF protection and per-user negotiation authorization.
- Account settings for profile/password changes, provider disconnection rules, optional TOTP two-factor authentication with recovery codes, personal data export and account deletion.
- Practice-only personal skill score/badges and leaderboard based on average skill score; leaderboard does not expose negotiation IDs or cross-user negotiation content.
- Security & Privacy page and development-only email outbox when SMTP is not configured.
- Explain-only AI Negotiation Assistant on signed-in pages: answers questions about platform/current negotiation using a detached, read-only and redacted snapshot; cannot place offers or mutate negotiations; maintains session-scoped assistant history and uses a built-in guide fallback when an LLM is unavailable.

**Architecture and stack recorded by the repository**
- Static HTML/CSS/JavaScript frontend communicating over HTTP/JSON with a Flask API.
- Python 3, Flask, python-dotenv, Groq/Gemini integrations via standard-library `urllib`, and pytest.
- No database and no frontend framework are listed in the README.
- The Orchestrator remains the authority for applying decisions; model output is advisory and validated before state mutation.

**Verification claims in the repository**
- `MILESTONE_CHECKLIST.md` marks Milestones 1–4 and cross-cutting requirements as PASS and reports 65 automated tests plus headless-browser runs.
- The same checklist names security, consistency, responsive checks at 1440/1180/820/390 px, downloads, account isolation, and assistant read-only behavior.
- This is documentation evidence from the uploaded snapshot; this update did not execute the test suite or reproduce the browser runs.

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

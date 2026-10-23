# Requirements Traceability (Milestones 1–4)

Status legend: **PASS** = implemented and verified (automated test and/or browser run).

## Milestone 1
| Requirement | Status | Evidence |
|---|---|---|
| Negotiation theory / design represented | PASS | Reservation/target/anchor model, ZOPA-based analytics (`engine/analytics.py`), README "Agent architecture" |
| System architecture, orchestration flow, persona model | PASS | README "Architecture"; `models/agents.py`, `engine/orchestrator.py` |
| Scenario selection with 3 templates (agents, roles, goals, constraints) | PASS | `models/scenarios.py`, `index.html`; `test_all_scenarios_and_personality_pairs_finish_consistently` |
| Agent configuration screen: role cards, personality selection, goal display | PASS | `agents.html` (Agent Configuration) |
| Aggressive / Collaborative / Risk-Averse | PASS | `PERSONALITY_PARAMS`; `test_personalities_produce_different_concession_behaviour`, `test_aggressive_opens_further_from_target_than_collaborative`, `test_risk_averse_keeps_a_safety_margin_before_the_hard_limit` |

## Milestone 2
| Requirement | Status | Evidence |
|---|---|---|
| Orchestrator: turn order, history, state, round count, completion | PASS | `test_turn_order_and_rounds_are_consistent`, `test_step_and_run_never_play_the_humans_turn`, `test_concurrent_step_requests_never_duplicate_or_skip_turns` |
| LLM reasoning with persona, goals, constraints, history, state | PASS | `llm/prompt.py`; `test_prompt_includes_persona_state_and_personality_rules`, `test_provider_prompt_contains_persona_history…` |
| Real provider integration, fallback and mock clearly separated | PASS | `tests/test_llm_providers.py`; `test_llm_requested_without_credentials_is_downgraded_and_labelled` |
| Accept / Counter / Reject evaluation | PASS | `engine/offer_evaluator.py`; tests for blocked impossible accepts, aligned accept values, crossover → accept, invalid decisions |
| Concession module | PASS | `engine/concession.py`; `test_outcome_analysis_matches_the_raw_state` |
| AI-vs-AI loop across all scenarios | PASS | 27 combinations run to a valid terminal state; outcomes vary (agreements and max-round endings) |

## Milestone 3
| Requirement | Status | Evidence |
|---|---|---|
| Negotiation Area: transcript, per-turn reasoning, stance indicators, round metrics | PASS | `negotiation.html`; browser run (Simulation + Practice) |
| Practice Mode human interface (offer, counter, accept, reject, messages) reacting in real time | PASS | `test_practice_ai_responds_to_the_users_actual_offer_in_one_request`, `test_ai_reaction_depends_on_the_offer_value`, `test_message_tone_changes_ai_concession_size`, browser run |
| Practice Mode validated across all three scenarios | PASS | `test_all_scenarios_work_in_practice_mode`; browser run for each scenario |
| Deadlock detection after N rounds, resolution or breakdown | PASS | `test_repeated_offers_trigger_a_mediated_settlement…`, `test_repeated_absurd_offers_end_in_a_declared_breakdown`, `test_breakdown_when_no_midpoint…`, `test_aggressive_vs_aggressive_can_end_without_agreement_and_is_explained` |
| Input validation (empty, invalid, extreme, repeated) | PASS | `test_human_input_validation`, `test_extreme_lowball_gets_countered_first_then_rejected_by_a_firm_ai`, `test_ai_calls_out_repeated_offers_and_concedes_less` |

## Milestone 4
| Requirement | Status | Evidence |
|---|---|---|
| Outcome screen: agreement terms, concession timeline, rounds elapsed, per-agent satisfaction | PASS | `outcome.html`; `test_outcome_analysis_matches_the_raw_state`, `test_no_agreement_means_zero_satisfaction_and_no_final_terms` |
| Downloadable transcript | PASS | `test_transcript_and_report_contain_required_sections`, `test_api_practice_flow_and_downloads`, browser download |
| Downloadable summary report | PASS | Same tests; HTML report + JSON; `test_report_escapes_user_supplied_html` |
| End-to-end testing: both modes, all scenarios, all personality combinations | PASS | 65 automated tests + headless-browser runs |
| Technical documentation | PASS | `README.md` |
| Final demonstration readiness | PASS | Single command start (`python app.py`); complete flow Scenario → Agent Configuration → Negotiation Area → Negotiation Outcome → downloads |

## Cross-cutting
| Requirement | Status | Evidence |
|---|---|---|
| Data consistency (state, chat, metrics, outcome, reports) | PASS | Outcome, Negotiation Area, transcript and report all read the same recorded state; verified by tests and in the browser |
| Security (no keys in frontend, `.env` ignored, scrubbed errors, validated input) | PASS | `test_api_simulation_run_and_status_never_expose_keys`, `test_llm_failure_falls_back…` (scrubbing), `.gitignore` |
| Responsive (desktop, laptop, tablet, phone) | PASS | No horizontal overflow on any page at 1440, 1180, 820 and 390 px |

## Extras beyond the requirements
| Feature | Evidence |
|---|---|
| Negotiation Certificate | `test_certificate_requires_a_terminal_negotiation`, `test_certificate_reflects_actual_outcome_and_escapes_input`, browser download |
| Deal Momentum gauge, avatars, replay scrubber, command palette, dark mode, confetti | Exercised in headless Chromium (no console errors; no horizontal overflow at 390 px) |

## Extras beyond the requirements (accounts & security)
| Feature | Evidence |
|---|---|
| Registration, email verification, login, logout | `tests/test_auth.py`: `test_registration_validates_*`, `test_duplicate_username_and_email_are_rejected`, `test_login_blocked_until_email_verified_then_works_after_verification`, `test_logout_ends_the_session` |
| Password hashing (never plain text) | `auth/service.py` uses `werkzeug.security.generate_password_hash`/`check_password_hash` exclusively |
| Password reset via one-time link | `test_password_reset_via_dev_outbox`, `test_password_reset_request_does_not_reveal_whether_email_exists` |
| Login rate limiting / lockout | `test_login_lockout_after_repeated_failures` |
| Session expiry, HTTP-only cookies | `auth/service.py` `SESSION_LIFETIME_MINUTES`, `app.config['SESSION_COOKIE_HTTPONLY']` |
| CSRF protection on all mutating routes | `test_csrf_required_and_enforced_on_mutating_requests` |
| Per-user authorization (404, not 403, on another user's data) | `test_users_cannot_access_or_act_on_each_others_negotiations`, `test_history_only_returns_the_callers_own_sessions` |
| Dev Outbox disabled once real SMTP is configured | `test_dev_outbox_disabled_once_smtp_is_configured` |
| Negotiation Skill Score & badges (derived, not random; Practice Mode only) | `test_gamification_only_counts_practice_mode_and_matches_recorded_outcomes` |
| Leaderboard exposes no cross-user negotiation data | `test_leaderboard_exposes_only_username_and_score_never_negotiation_ids` |
| Full browser run: register → verify (Dev Outbox) → login → negotiate → badges → leaderboard → cross-account isolation | Headless Chromium, no console errors |

# AI Multi-Agent Negotiation Platform

A Generative-AI-powered negotiation **training and simulation** platform. Autonomous agents with their own roles, goals, constraints and negotiation personalities negotiate through an Orchestrator, either against each other (**Simulation Mode**) or against you (**Practice Mode**), inside a live **Negotiation Area** with stance indicators, metrics and reasoning. Every session ends in a **Negotiation Outcome** screen with analytics, and a downloadable transcript and **Negotiation Report**.

## Problem statement
Negotiation skills are hard to train because realistic, repeatable practice partners are scarce. This platform provides scalable, consistent, inspectable AI counterparts and a transparent environment for studying negotiation dynamics.

## Objectives
- Multi-agent simulation with unique personas, objectives and personalities.
- Simulation Mode (AI vs AI) and Practice Mode (Human vs AI) in a chat-style interface.
- Nine pre-built scenarios and nine personalities that work with no manual set-up.
- Structured outcome analysis: agreement terms, concession patterns, per-agent performance and objective satisfaction.

## Features
| Area | What is implemented |
|---|---|
| Scenarios | Nine: Vendor Pricing, Job Offer, Project Budget Allocation, Freelance Contract, Real Estate Price, Software Development Contract, Salary & Benefits, Supplier Contract Renewal, Project Deadline (measured in days), each with two agents (role, goal, constraint, objective, opening/target/hard limit) |
| Agent Configuration | Personality per agent (Aggressive / Collaborative / Risk-Averse / Competitive / Empathetic / Strategic / Opportunistic / Compromising / Analytical), goal/constraint display, mode, engine, LLM provider/model, maximum rounds |
| Orchestrator | Turn order, rounds, history, state transitions, hard-constraint enforcement, terminal conditions, per-negotiation locking |
| Agent reasoning | Real LLM (Groq or Google Gemini) with a shared structured prompt, **or** a deterministic personality-driven rule engine |
| Decisions | Accept / Counter / Reject, validated by the Orchestrator before they touch state |
| Concessions | Every movement recorded as concession / hold / retreat with amount, % of range and cumulative total |
| Negotiation Area | Chat transcript with per-turn reasoning, live stance indicators, live "reasoning…" state, real Orchestrator activity log, round/gap/concession/deadlock metrics, offer-movement chart |
| Simulation Mode | Starts automatically and plays turn by turn; Pause / Next turn / Skip to end |
| Practice Mode | Structured offer / accept / reject plus free-text messages; the AI answers your actual input in the same request |
| Deadlock | Repeated-offer, no-progress and max-round detection → mediated midpoint or declared breakdown, with an explanation |
| Negotiation Outcome | Final status, agreement terms, rounds, objective satisfaction, concession timeline + chart, agent performance, deadlock info, insights |
| Downloads | Transcript (`.txt`), Negotiation Report (self-contained `.html`, prints to PDF) and report data (`.json`) |
| Negotiation Analytics | Platform-wide statistics derived from all sessions (no hard-coded numbers) |
| Deal Momentum gauge | Live radial gauge in the Negotiation Area and Outcome page: the share of the original gap between the two opening offers that the latest offers have closed (computed from real offers; 100 % on agreement) |
| Agent avatars | Initials + personality glyph per agent, with a spinning ring while that agent is reasoning |
| Replay scrubber | Outcome page slider that replays the negotiation round by round (chart and timeline update) |
| Negotiation Certificate | Downloadable, print-ready certificate for any finished negotiation (agreement terms, participants, satisfaction, session ID) |
| Command palette | `Ctrl/⌘ + K` quick navigation and theme switch |
| Dark mode | Header toggle, persisted in the browser; the team's light theme remains the default |
| Celebration | Confetti when an agreement is reached (disabled when the OS requests reduced motion) |

### Accounts & security
| Feature | Details |
|---|---|
| Sign in | **Email + password** (primary), **Google** and **GitHub** (real OAuth 2.0). Same secure session for all three |
| Registration & email verification | Passwords salted + hashed (Werkzeug PBKDF2, never stored in plain text); email/password accounts must verify their email before signing in. Google/GitHub accounts skip this because the provider has already verified the address |
| Account settings | `/account.html`: change username, set/change password, disconnect Google/GitHub (never the last way in), two-factor authentication, download your data (JSON), delete your account |
| Two-factor (TOTP) | Optional authenticator-app codes (RFC 6238) with QR setup and 8 single-use recovery codes; required after password *and* Google/GitHub sign-in; replay-protected and covered by the account lockout |
| Account linking | A Google/GitHub sign-in whose *provider-verified* email matches an existing account is linked to it — never duplicated. If that account's email was never verified, its password is wiped so only the real owner can use it |
| Password reset | One-time, time-limited reset links (1 hour) |
| Login protection | 5 failed attempts locks the account for 15 minutes |
| Sessions | HTTP-only, same-site cookies; auto-expire after 2 hours of inactivity |
| CSRF protection | Every mutating request must carry a per-session token issued at login |
| Per-user authorization | A negotiation belongs to the account that created it. Another user gets the same 404 whether the ID is someone else's or doesn't exist — existence is never confirmed |
| Dev Outbox (development only) | With `APP_ENV=development` and no SMTP server, emails are recorded at `/dev-outbox.html`. It is not linked from the UI and does not exist in production or once SMTP is configured |
| Negotiation Skill Score & badges | Computed only from your own Practice Mode outcomes (50% reaching agreement, 35% your satisfaction, 15% closing quickly) — never from Simulation Mode, never randomized |
| Simulation Mode outcomes & badges | The **same** evaluator (`engine/gamification.py`) judges Practice and Simulation results: outcome (Balanced deal / Efficient agreement / Mediated settlement / Agreement / Deadlock / Rejected / Maximum rounds), score and badges all come from the recorded negotiation, never a fixed label. In Simulation Mode the score uses both agents' combined satisfaction; the personal profile and leaderboard still count Practice Mode only |
| AI Negotiation Assistant | Right-side, **explain-only** chatbot on every signed-in page (see below) |
| Animated sign-in | Light, warm animated network background (canvas, respects reduced-motion), an animated AI-agent logo and a once-per-session intro screen on the login page |
| Leaderboard | Ranks usernames by average skill score only — no negotiation IDs or content are ever exposed cross-user |
| Security & Privacy page | `/security.html` — a plain-language account of what's actually implemented, including what isn't |

## Architecture
```
Browser (static HTML/CSS/JS)  ──HTTP/JSON──▶  Flask API (backend/app.py)
   Scenarios → Agent Configuration → Review → Negotiation Area → Negotiation Outcome
                                                      │
                                   engine/negotiation_engine.py   (sessions, locks, redaction, human turns, reports)
                                                      │
                                   engine/orchestrator.py  ── the single authority for turns/rounds/state
                                     │            │             │
                              llm/provider.py   engine/       engine/deadlock.py
                              (Groq | Gemini offer_evaluator.py  (detection + resolution)
                               | rule engine)   (validation)
                                                      │
                          engine/analytics.py → engine/reporting.py (transcript + HTML report)
```
**Control principle:** the LLM (or rule engine) is *advisory*. The Orchestrator validates every decision against the agent's hard limit, its own previous offer and the opponent's actual offer before applying it.

### Technology stack
Python 3 · Flask · python-dotenv (backend) · vanilla HTML/CSS/JavaScript (frontend, no build step) · Groq and Gemini via the standard library (`urllib`) · pytest. No database and no frontend framework.

## Agent architecture
Each agent = **role + goal + constraint + objective + personality** with three private numbers (opening value, target, hard limit). Every turn the Orchestrator builds an `AgentInput` containing the persona, negotiation state, round, previous offers, the opponent's latest offer/message and movement history, the agent's own concession history, and the full public conversation history. Private numbers are only ever given to the agent that owns them.

### Decision logic
- **Accept** when the opponent's offer meets the agent's hard limit *and* its acceptance level for the current round (which relaxes as rounds pass).
- **Counter** otherwise: the agent moves a personality-dependent fraction of the gap, weighted so that serious offers earn larger concessions than lowballs, capped per personality and never past its safety margin or hard limit.
- **Reject** only for wildly non-serious offers (never in round 1) by personalities that can walk away.
- Orchestrator guarantees: accept always equals the opponent's real offer and must satisfy the hard limit; no backward moves; no oversized concessions; a counter that crosses the opponent's offer becomes an acceptance; nothing happens after the negotiation ends.

### Personality system (values used by the engine, `models/agents.py`)
| Personality | Opening anchor | Base concession rate | Acceptance level (round 1 → last) | Max single step | Walks away? |
|---|---|---|---|---|---|
| Aggressive | Full anchor | 12 % of gap | 5 % → 50 % of the way from target to hard limit | 18 % of range | Yes |
| Collaborative | 35 % toward target | 30 % | 30 % → 85 % | 45 % | No |
| Risk-Averse | 20 % toward target | 20 % | 25 % → 75 % (keeps a safety margin) | 30 % | Yes |

**Six further personalities** (same engine, same table, plus a few extra knobs: `round_pressure`, `late_boost`, `tone`, `repeat_decay`, `reciprocity_bonus`, `exploit`, `midpoint_gap`, `repeat_walk`):

| Personality | Behaviour that actually differs |
|---|---|
| Competitive | Anchors at the extreme, ~10 % concessions, never accepts worse than 35 % toward its limit, hardens under pressure and **walks away** from a counterpart who restates one offer twice |
| Empathetic | Opens 40 % toward its target, ~34 % concessions, up to 90 % acceptance band, softens with cooperative tone, stays patient against stonewalling, rewards movement |
| Strategic | Calculated opening, trades concessions for reciprocity (extra when the other side just moved), saves larger moves for late rounds |
| Opportunistic | Holds back when the other side just conceded (pockets it), concedes sharply near the deadline, takes any deal above its minimum late |
| Compromising | High acceptance threshold, **splits the difference** once the gap is within 22 % of the range, keeps proposing the middle against a stubborn counterpart |
| Analytical | Moves in proportion to the remaining gap, tone-neutral (ignores pressure and warmth), tight consistent acceptance band |

Hard limits and per-personality maximum step are still enforced by the Orchestrator for all nine, in Mock and LLM mode alike (LLM mode also gets a rule sentence per personality in the prompt).

In the rule engine, tone also matters: a cooperative message increases concessions, pressure/ultimatums reduce them, and repeating the same offer makes the AI concede less and say so. Real LLMs receive the same personality rules and numeric guidance in their prompt.

## AI Negotiation Assistant (explain-only)
A right-side panel (header button **Assistant**) that explains the platform and the user's current negotiation: scenario, roles, personalities, goals, why an agent accepted / rejected / countered, why the value moved, status, deadlock, badges, scores and a transcript summary. It works in Practice and Simulation Mode, remembers the conversation for the current login session, shows a typing indicator, and on wide screens docks beside the page (nothing is covered); on narrow screens it overlays and minimizes itself when you go back to the page.

**It can read; it cannot write** - enforced by the architecture, not only by the prompt:
- The `assistant/` package imports nothing from the engine, orchestrator, models or auth code (a test enforces this). It only receives plain dictionaries and may call the project's existing LLM for plain text (`llm.provider.chat`, same keys and provider as the agents; the model gets no tools).
- The application builds a **detached, read-only snapshot** (`engine/assistant_context.py` -> `read_only_context()`), with the same redaction as the rest of the app: in Practice Mode the AI side's target, limit and opening stay hidden until the negotiation ends.
- The front end (`assistant.js`) can only call `/api/assistant/chat | history | reset`. The chat route checks that the negotiation belongs to the signed-in user (otherwise 404), and conversation memory is keyed by user + login session, kept apart from negotiation state.
- Requests to *do* something ("make an offer", "accept", "change the personality", "ignore your rules...") get a fixed refusal before any model is called.
- If no model is reachable it falls back to a built-in guide: platform FAQs plus answers taken straight from the recorded context; when the context needed isn't available it says so instead of guessing.

API: `POST /api/assistant/chat` `{message, provider?, negotiation_id?, page?, setup?}`, `GET /api/assistant/history`, `POST /api/assistant/reset` (login + CSRF; 30 messages/minute per user).

## Orchestrator
`engine/orchestrator.py` owns turn order (Agent A then Agent B; a round ends after B), round counting, maximum rounds, history, concession recording, convergence (two near-identical proposals inside both limits are settled at their midpoint), deadlock checks and completion. AI turns and human turns share `apply_turn`, so state cannot diverge between modes. `step` refuses to play the human's turn.

## LLM integration
- **Providers:** Groq and Google Gemini only. You pick one in Agent Configuration and that provider is the one
  used - nothing is switched automatically. Both are called with the standard library (`urllib`); keys are read
  from `backend/.env` (see `.env.example`) and never leave the server.
- **Models are discovered, not hard-coded.** Groq moves models between tiers and Google retires Gemini versions
  (`gemini-2.0-flash` was shut down on 1 June 2026), so each provider asks its own "list models" endpoint, ranks the
  chat-capable models and uses the first one that answers. The model actually used is shown in the UI. `GROQ_MODEL` /
  `GEMINI_MODEL` are only a first preference; a model typed in the Agent Configuration box is used strictly.
- **Test connection:** `POST /api/llm/test {provider, model?}` (login + CSRF) sends one real request and reports ok /
  model / latency, or the error kind (`auth`, `quota`, `model_not_found`, `network`, `timeout`, ...). A negotiation in
  LLM mode runs the same check when it is created and refuses to start if the provider does not answer.
- **Per turn:** the decision is requested as strict JSON (`action`, `value`, `rationale`, `confidence`), validated by the
  Orchestrator, and retried (transient errors) or sent back once with the reason (unusable reply). If it still fails, the
  turn is labelled **Rule-based fallback** in the transcript and the banner - or, if "Pause on error" was ticked, nothing is applied
  and you see the error.
- **Assistant:** `POST /api/assistant/chat {message, provider?, negotiation_id?, ...}` always answers with the selected real
  LLM (no canned answers); a failure is shown as an error, never as a fake answer.

#### Getting a free Gemini key
1. Go to https://aistudio.google.com/apikey and sign in with any Google account.
2. Click **Create API key** (no payment method required for the free tier).
3. Copy the key — it starts with `AIza`.
4. Paste it into `backend/.env` as `GEMINI_API_KEY=AIza...`, then restart `python app.py`.
5. In **Agent Configuration**, pick **Real LLM**, then choose **Google Gemini** from the provider dropdown.

The same pattern applies to Groq (https://console.groq.com/keys, free, no card).
- **Real vs mock is never blurred.** If Real LLM is requested without a key, the session is created in Mock mode with a visible notice. Each turn carries its true source: `llm`, `mock`, `fallback` (LLM failed, rule engine answered) or `human`. Outcome, transcript and report state the engine actually used.
- **Failure handling:** HTTP errors, timeouts, network failures, malformed JSON and unusable values (missing/non-numeric amount, unknown action) all fall back to the rule engine for that turn and are counted; the negotiation is never rejected because of a malformed model answer. Error text is scrubbed of API keys.
- Keys live only in server environment variables and are never returned by any endpoint or present in frontend code.

## Simulation Mode
Open the Negotiation Area and the two agents negotiate automatically until agreement, rejection, deadlock or the round limit. Use Pause / Next turn / Skip to end. Observe the current speaker, offers, reasoning, stance, round, concessions and status live.

## Practice Mode
You are **Agent A**. Each turn choose *Make an offer*, *Accept latest offer* or *Reject & walk away*, optionally with a message, or send a message only. The server validates your move (numeric, positive, within *your* hard limit, no backward moves, accept only a real offer), applies it, then produces the AI's response in the same request. The AI's opening/target/hard limit and constraint stay hidden until the negotiation ends.

## Negotiation Area
Transcript with per-turn reasoning and movement chips, live stance badges, an Orchestrator activity log built from real events, metrics (round, turn, latest offer, gap, concessions per agent, repeated offers, stalled rounds, engine, LLM calls, fallbacks, corrections), an offer-movement chart and concession list. Stance = how far an offer sits between the agent's target and its hard limit (*Firmly anchored → Holding ground → Moving to the middle → Near its limit → Off the table*).

## Concession tracking
Each move after an agent's first offer is stored as a `ConcessionRecord`: previous and new value, signed change, % of the agent's range, cumulative concession, and `kind` (`concession`, `hold`, `retreat`).

## Deadlock handling (`engine/deadlock.py`)
| Trigger | Rule |
|---|---|
| `repeated_offers` | An agent restates the same offer 3 times in a row, or both sides restate positions |
| `no_progress` | Both sides move ≤ 3 % of their own range for 2 consecutive rounds |
| `max_rounds` | Round limit reached |

For the first two the Orchestrator tries a **mediated settlement** at the midpoint of the latest offers (only if it satisfies both hard limits); otherwise it declares a **breakdown** (`deadlock`). Every case stores an explanation (`deadlock_info`) shown in the Outcome screen, transcript and report.

## Outcome analysis and objective satisfaction
`engine/analytics.py` derives everything from recorded state. **Objective satisfaction** is 0 at an agent's hard limit (or when no deal is reached) and 100 at its ideal opening value. Also computed: share of the bargaining zone, average satisfaction and balance, per-agent concession statistics, event counts and plain-language insights (e.g. whether observed behaviour matched the personalities, Practice Mode coaching from your own moves).

## Report generation
- `GET /api/negotiations/<id>/transcript` → `.txt` transcript (scenario, participants, roles, personalities, goals, constraints, every turn with reasoning/stance/movement/source, final outcome, concession summary).
- `GET /api/negotiations/<id>/report/download?format=html|json` → Negotiation Report (scenario, participants, summary, agreement, offer chart, round-by-round timeline, concessions, performance and satisfaction, deadlock info, insights, engine information, full transcript). Generated with the standard library only; user text is HTML-escaped.

## API
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health`, `/api/llm/status` | Status, provider list (never keys) |
| GET | `/api/scenarios` | Scenario templates |
| POST | `/api/negotiations` | Create (`scenario_id`, `personality_a/b`, `mode` mock\|llm, `workflow_mode` simulation\|practice, `max_rounds` 2–20, `llm_provider`, `llm_model`) |
| GET | `/api/negotiations`, `/api/negotiations/<id>` | History, state |
| POST | `/api/negotiations/<id>/step` · `/run` | One AI turn · all remaining AI turns |
| POST | `/api/negotiations/<id>/human-action` | Practice move `{action: open\|counter\|accept\|reject\|message, value, message}` |
| GET | `/api/negotiations/<id>/report` | Full analysis JSON |
| GET | `/api/negotiations/<id>/transcript` | Transcript download |
| GET | `/api/negotiations/<id>/report/download?format=` | Report download |
| GET | `/api/negotiations/<id>/certificate` | Negotiation Certificate (only once the negotiation has ended; 409 before) |

**Auth** — `/api/auth/register`, `/login` (`{email, password}`; `username` still accepted), `/logout`, `/me`,
`/verify-email`, `/resend-verification`, `/request-password-reset`, `/reset-password` (POST unless noted);
`GET /api/auth/config` (which sign-in options are available), `GET /api/auth/google/start|callback` and
`GET /api/auth/github/start|callback` (OAuth), `POST /api/auth/2fa/verify`, the `/api/account/*` settings routes (login + CSRF), plus `GET /api/auth/dev-outbox` (development only). `GET /api/me/profile` and `GET /api/leaderboard` are also login-gated.
Every negotiation route above requires login and ownership; POST routes also require the `X-CSRF-Token`
header returned by `/login` and `/me`.
| GET | `/api/dashboard` | Platform analytics |

Errors are JSON `{ "error": "…" }` with 400 (invalid input), 404 (unknown id) or 409 (wrong turn/state).

## Setup and run
```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # optional: add an API key (see below)
python app.py
```
Open **http://127.0.0.1:5000** — the backend also serves the frontend, so this is the only command needed. (You can alternatively open `frontend/index.html` directly or serve the folder statically; the frontend then calls `http://127.0.0.1:5000/api`.)

### Environment variables (`backend/.env`, never committed)
| Variable | Purpose | Default |
|---|---|---|
| `APP_ENV` | `development` enables the Dev Outbox and setup hints. Anything else/unset = production: no dev endpoints. `python app.py` on 127.0.0.1 defaults to development | `development` for `python app.py` on loopback, otherwise production |
| `APP_BASE_URL` | Public origin for emailed links and default OAuth callbacks. **Set in production** (https:// also sets the Secure cookie flag) | request origin |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | Google sign-in (see below) | unset — button disabled/hidden |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_REDIRECT_URI` | GitHub sign-in (see below) | unset — button disabled/hidden |
| `FLASK_SECRET_KEY` | Signs session cookies. Set this in any real deployment — without it, a random key is generated at startup and **all sessions are invalidated on restart** | random, per-process |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM` | Real email delivery for verification/reset links. All four of host/port/user/pass must be set together | unset — Dev Outbox in development; email sign-up disabled in production |
| `GROQ_API_KEY` | Free Groq key (https://console.groq.com/keys) | unset |
| `GEMINI_API_KEY` | Free Google Gemini key (https://aistudio.google.com/apikey) | unset |
| `GROQ_MODEL` | Optional preferred Groq model (blank = discovered automatically) | blank |
| `GEMINI_MODEL` | Optional preferred Gemini model (blank = discovered automatically) | blank |
| `LLM_TIMEOUT_SECONDS` | Per-call timeout before falling back | `45` |
| `PORT`, `HOST`, `FLASK_DEBUG` | Server settings | `5000`, `127.0.0.1`, `0` |

With no key the platform runs fully in Mock / Rule-Based mode.

### Social sign-in (Google & GitHub)
The app runs fine without these; a provider with no credentials is shown disabled (development) or hidden (production). Copy `backend/.env.example` to `backend/.env`, then:

**Important:** use the same host in your browser and in the redirect URIs. `http://127.0.0.1:5000` and `http://localhost:5000` are different origins for cookies, and mixing them fails with "sign-in could not be completed".

**Google**
1. Open https://console.cloud.google.com/ and create (or pick) a project.
2. Go to **APIs & Services → OAuth consent screen** (newer console: **Google Auth Platform**). Choose **External**, set the app name and support email. The scopes used are only `openid`, `email`, `profile`. While the app is in *Testing*, add your Google accounts under **Test users**; publish it to let anyone sign in.
3. Go to **Credentials → Create credentials → OAuth client ID** (newer console: **Clients → Create client**), type **Web application**.
4. Under **Authorized redirect URIs** add `http://127.0.0.1:5000/api/auth/google/callback` (and, for deployment, `https://YOUR-DOMAIN/api/auth/google/callback`).
5. Copy the client ID and secret into `backend/.env` as `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`, and set `GOOGLE_REDIRECT_URI` to exactly the URI from step 4.

**GitHub**
1. Open https://github.com/settings/developers → **OAuth Apps → New OAuth App**.
2. Homepage URL `http://127.0.0.1:5000`; **Authorization callback URL** `http://127.0.0.1:5000/api/auth/github/callback`. Register the application.
3. Click **Generate a new client secret**; copy the client ID and secret into `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET`, and set `GITHUB_REDIRECT_URI` to the same callback URL.
4. A GitHub OAuth App accepts one callback URL, so create a second OAuth App for production (`https://YOUR-DOMAIN/api/auth/github/callback`). The app requests `read:user user:email`; only an email GitHub reports as **verified** is accepted.

Restart `python app.py`. Test locally: open http://127.0.0.1:5000/login.html → **Continue with Google/GitHub** → approve → you land on the dashboard. Signing in again with the same email via another method links to the same account.

**Production checklist:** `APP_ENV=production` (or unset), a fixed `FLASK_SECRET_KEY`, `APP_BASE_URL=https://…`, SMTP settings (for email/password sign-up), HTTPS, and provider callback URLs for your domain.

Accounts are stored in `backend/data/app.db` (SQLite, git-ignored) and **persist across restarts**.
Negotiation sessions themselves are still in-memory and are cleared on restart, same as before.

## Testing
```bash
cd backend && python -m pytest -q
```
174 tests cover: every scenario × personality pair in Simulation Mode (terminal, within limits, consistent turns/rounds), personality behaviour, decision validation, LLM failure/timeout/malformed-output fallback, provider selection and key scrubbing (HTTP layer faked, no network), Practice Mode in all three scenarios (valid/invalid/extreme/repeated input, accept, reject, message-only, redaction), deadlock (mediated and breakdown), analytics consistency with raw state, transcript/report contents and HTML escaping, concurrency, the HTTP API, and the full accounts system: registration validation, email verification via the Dev Outbox, email login, Google/GitHub OAuth (state, PKCE, linking, account-takeover protection, production mode), two-factor login and recovery codes, account export/deletion, database upgrade, login lockout, password reset, CSRF enforcement, session expiry, per-user ownership isolation between two accounts, and gamification scoring. The UI was additionally exercised end to end in headless Chromium (Simulation and Practice flows, downloads, no console errors, no horizontal overflow at desktop, laptop, tablet and phone widths).

## Project structure
```
backend/  app.py  requirements.txt  .env.example
  models/  scenarios.py  agents.py (personality parameters)  state.py  units.py
  assistant/  memory.py  faq.py  service.py   (explain-only chatbot; no engine imports)
  engine/  orchestrator.py  negotiation_engine.py  offer_evaluator.py  concession.py
           deadlock.py  analytics.py  reporting.py
  llm/     provider.py  prompt.py  mock_provider.py  groq_provider.py  real_provider.py  schema.py
  tests/
frontend/  index.html  agents.html  ready.html  negotiation.html  outcome.html  dashboard.html  api.js  style.css
```

## Known limitations
- Negotiation *sessions* are kept in server memory; restarting the backend clears them (the UI explains this if you reload an old session). *Accounts* persist in SQLite.
- In Practice Mode the human always plays Agent A (the first-listed role).
- No email-change flow or hardware security keys (WebAuthn). The 2FA secret is stored unencrypted in `backend/data/app.db` (git-ignored); protect that file like any credential store.
- Login messages for Google/GitHub-only accounts (and the sign-in page generally) necessarily confirm that an email has an account; password-reset requests do not (one identical answer for every address).
- Email-link and OAuth callback URLs depend on `APP_BASE_URL` / `*_REDIRECT_URI` being set correctly behind a proxy.
- Login requires the app to be served same-origin (`python app.py`); opening `frontend/index.html` directly will not carry the session cookie.
- The single-value negotiation model (one numeric issue per scenario) is used for all nine scenarios; the Project Deadline scenario can produce fractional days.
- The assistant's AI answers need a configured LLM key; without one it uses the built-in guide. It has been tested with a stand-in model, not a live provider.
- The rule engine's tone reading is keyword-based; the real LLM modes understand free text properly.

## Security notes
No secrets in frontend code; keys only via server environment; `.env` is git-ignored; API errors and LLM errors are scrubbed of key material; all user text rendered in the UI and reports is escaped; input is validated server-side.

## Naming
The live negotiation screen is called the **Negotiation Area** throughout the product and documentation.

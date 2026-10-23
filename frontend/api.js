/* Shared client helpers for the AI Multi-Agent Negotiation Platform.
   No secrets live in the frontend: every LLM call is made by the backend. */
const API_BASE = window.__API_BASE__ || ((location.protocol === 'file:' || location.port !== '5000') ? 'http://127.0.0.1:5000/api' : '/api');
const PRODUCT = 'AI Multi-Agent Negotiation Platform';

const Session = {
  key: 'negotiation_suite_session',
  get() { try { return JSON.parse(sessionStorage.getItem(this.key)) || {}; } catch { return {}; } },
  set(p) { const n = { ...this.get(), ...p }; sessionStorage.setItem(this.key, JSON.stringify(n)); return n; },
  clear() { sessionStorage.removeItem(this.key); }
};

let _csrf = null, _currentUser = null;

async function call(path, opt = {}, timeoutMs = 120000) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), timeoutMs);
  let r;
  const headers = { 'Content-Type': 'application/json', ...(opt.headers || {}) };
  if (opt.method && opt.method !== 'GET' && _csrf) headers['X-CSRF-Token'] = _csrf;
  try {
    r = await fetch(API_BASE + path, { ...opt, credentials: 'same-origin', signal: ctl.signal, headers });
  } catch (e) {
    throw Error(e.name === 'AbortError' ? 'The request timed out. Please try again.' : 'Cannot reach the negotiation server. Make sure the backend is running (python app.py).');
  } finally { clearTimeout(timer); }
  let d = null;
  try { d = await r.json(); } catch { /* non-JSON error page */ }
  if (r.status === 401 && !path.startsWith('/auth/')) { location.href = 'login.html?next=' + encodeURIComponent(location.pathname + location.search); throw Error('Please log in to continue.'); }
  if (!r.ok) { const e = Error((d && d.error) || `Request failed (${r.status})`); e.status = r.status; throw e; }
  return d;
}

const post = (path, body) => call(path, { method: 'POST', body: JSON.stringify(body || {}) });
const Api = {
  assistant: {
    chat: body => post('/assistant/chat', body),
    history: () => call('/assistant/history'),
    reset: () => post('/assistant/reset')
  },
  account: {
    get: () => call('/account'),
    username: username => post('/account/username', { username }),
    password: (current_password, new_password) => post('/account/password', { current_password, new_password }),
    unlink: provider => post('/account/unlink', { provider }),
    tfaSetup: () => post('/account/2fa/setup'),
    tfaEnable: code => post('/account/2fa/enable', { code }),
    tfaDisable: code => post('/account/2fa/disable', { code }),
    remove: (confirm_username, password, code) => post('/account/delete', { confirm_username, password, code })
  },
  health: () => call('/health'),
  llm: () => call('/llm/status'),
  scenarios: () => call('/scenarios'),
  create: p => call('/negotiations', { method: 'POST', body: JSON.stringify(p) }),
  get: id => call('/negotiations/' + id),
  step: id => call('/negotiations/' + id + '/step', { method: 'POST' }),
  run: id => call('/negotiations/' + id + '/run', { method: 'POST' }),
  human: (id, p) => call('/negotiations/' + id + '/human-action', { method: 'POST', body: JSON.stringify(p) }),
  report: id => call('/negotiations/' + id + '/report'),
  dashboard: () => call('/dashboard'),
  history: () => call('/negotiations'),
  myProfile: () => call('/me/profile'),
  leaderboard: () => call('/leaderboard'),
  auth: {
    register: (username, email, password) => call('/auth/register', { method: 'POST', body: JSON.stringify({ username, email, password }) }),
    login: (email, password) => call('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
    logout: () => call('/auth/logout', { method: 'POST' }),
    me: () => call('/auth/me'),
    verifyEmail: token => call('/auth/verify-email', { method: 'POST', body: JSON.stringify({ token }) }),
    resendVerification: email => call('/auth/resend-verification', { method: 'POST', body: JSON.stringify({ email }) }),
    requestPasswordReset: email => call('/auth/request-password-reset', { method: 'POST', body: JSON.stringify({ email }) }),
    resetPassword: (token, password) => call('/auth/reset-password', { method: 'POST', body: JSON.stringify({ token, password }) }),
    devOutbox: () => call('/auth/dev-outbox'),   // development only; the endpoint doesn't exist in production
    config: () => call('/auth/config'),
    verify2fa: code => call('/auth/2fa/verify', { method: 'POST', body: JSON.stringify({ code }) }),
    /* Google/GitHub sign-in is a full-page navigation to the backend, which redirects to the provider.
       No provider secret or token ever touches this file. */
    oauthUrl: (provider, next) => API_BASE + '/auth/' + provider + '/start' + (next ? '?next=' + encodeURIComponent(next) : ''),
  }
};

/* Every protected page calls this first. Redirects to login.html if not signed
   in; otherwise primes the CSRF token used by all mutating requests and fills
   the header's profile chip. Auth pages themselves skip this. */
async function authGuard() {
  let me;
  try { me = await Api.auth.me(); } catch { me = { authenticated: false }; }
  if (!me.authenticated) {
    location.href = 'login.html?next=' + encodeURIComponent(location.pathname + location.search);
    return null;
  }
  _csrf = me.csrf_token; _currentUser = me.user;
  renderProfileChip();
  loadAssistant();
  return me.user;
}
/* The AI Negotiation Assistant (explain-only) is loaded lazily on every signed-in page that has the header button. */
function loadAssistant() {
  if (!document.getElementById('assistantTrigger') || window.__assistantLoading) return;
  window.__assistantLoading = true;
  const css = Object.assign(document.createElement('link'), { rel: 'stylesheet', href: 'assistant.css' });
  const js = Object.assign(document.createElement('script'), { src: 'assistant.js', defer: true });
  document.head.appendChild(css); document.head.appendChild(js);
}
const ICON = {
  user: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21a8 8 0 0 0-16 0"/><circle cx="12" cy="7" r="4"/></svg>',
  caret: '<svg class="profile-caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>',
  history: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v5h5"/><path d="M3.05 13a9 9 0 1 0 .5-4.5L3 8"/><path d="M12 7v5l4 2"/></svg>',
  shield: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Z"/></svg>',
  logout: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>',
  robot: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="9" width="16" height="11" rx="2"/><circle cx="9" cy="14.5" r="1.3" fill="currentColor" stroke="none"/><circle cx="15" cy="14.5" r="1.3" fill="currentColor" stroke="none"/><path d="M12 9V5"/><circle cx="12" cy="3.5" r="1.3" fill="currentColor" stroke="none"/><path d="M4 13H2M22 13h-2"/></svg>',
};

function renderProfileChip() {
  const el = document.getElementById('profileChip');
  if (!el || !_currentUser) return;
  el.innerHTML = `<button class="profile-btn" id="profileBtn" type="button" aria-haspopup="true" aria-expanded="false"><span class="profile-dot">${ICON.user}</span>${esc(_currentUser.username)}${ICON.caret}</button>
    <div class="profile-menu" id="profileMenu" hidden role="menu">
      <div class="profile-menu-head"><b>${esc(_currentUser.username)}</b><span>${esc(_currentUser.email || '')}</span></div>
      <a href="my-negotiations.html" role="menuitem">${ICON.history} My Negotiations</a>
      <a href="account.html" role="menuitem">${ICON.user} Account settings</a>
      <a href="security.html" role="menuitem">${ICON.shield} Security &amp; Privacy</a>
      <button id="logoutBtn" type="button" role="menuitem">${ICON.logout} Log out</button>
    </div>`;
  const btn = document.getElementById('profileBtn'), menu = document.getElementById('profileMenu');
  const setOpen = open => { menu.hidden = !open; btn.setAttribute('aria-expanded', String(open)); el.classList.toggle('open', open); };
  btn.onclick = () => setOpen(menu.hidden);
  document.addEventListener('click', e => { if (!el.contains(e.target)) setOpen(false); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') setOpen(false); });
  document.getElementById('logoutBtn').onclick = async () => { try { await Api.auth.logout(); } catch {} Session.clear(); location.href = 'login.html'; };
}

/* Download a text/HTML/JSON document generated by the backend. */
async function download(path, fallbackName) {
  const r = await fetch(API_BASE + path);
  if (!r.ok) { let m = 'Download failed'; try { m = (await r.json()).error || m; } catch {} throw Error(m); }
  const cd = r.headers.get('Content-Disposition') || '';
  const name = (cd.match(/filename="?([^";]+)"?/) || [])[1] || fallbackName;
  const url = URL.createObjectURL(await r.blob());
  const a = Object.assign(document.createElement('a'), { href: url, download: name });
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

const PERSONALITIES = {
  aggressive: { label: 'Aggressive', desc: 'Protects leverage, anchors strongly, concedes in small steps and applies pressure.' },
  collaborative: { label: 'Collaborative', desc: 'Seeks mutual benefit, opens reasonably and makes steady, balanced concessions.' },
  risk_averse: { label: 'Risk-Averse', desc: 'Keeps a safety margin from its limits, avoids uncertain outcomes and prefers a defensible deal.' },
  competitive: { label: 'Competitive', desc: 'Win-lose and results-driven. Anchors at the extreme, concedes very little and walks away from a counterpart who stonewalls.' },
  empathetic: { label: 'Empathetic', desc: 'Relationship-focused. Opens generously, concedes warmly and stays patient when the other side is slow to move.' },
  strategic: { label: 'Strategic', desc: 'Plans ahead. Trades concessions for reciprocity and saves its larger moves for the later rounds.' },
  opportunistic: { label: 'Opportunistic', desc: 'Holds back when the other side is generous, then concedes sharply near the deadline to take a deal.' },
  compromising: { label: 'Compromising', desc: 'Seeks the middle. Splits the difference as soon as the gap narrows and accepts fair deals early.' },
  analytical: { label: 'Analytical', desc: 'Data-driven and even-tempered. Moves in proportion to the remaining gap and ignores tone and pressure.' }
};
const P = PERSONALITIES;
const STATUS = {
  not_started: 'Not started', in_progress: 'In progress', agreed: 'Agreement reached', rejected: 'Rejected',
  deadlock: 'Deadlock', completed: 'Completed', max_rounds_reached: 'Maximum rounds reached'
};
const SOURCE = { llm: 'Live LLM', mock: 'Rule-based engine', fallback: 'Rule-based fallback', human: 'You' };
const PROVIDER_LABEL = { groq: 'Groq', gemini: 'Gemini' };
/* Provider-aware label for one transcript turn, e.g. "Live LLM · Gemini". Falls
   back to the plain SOURCE label when there's no provider to show (mock/human/fallback). */
function sourceLabel(turnSource, negotiationState) {
  if (turnSource === 'llm' && negotiationState && negotiationState.llm_provider) {
    return `${SOURCE.llm} · ${PROVIDER_LABEL[negotiationState.llm_provider] || negotiationState.llm_provider}`;
  }
  return SOURCE[turnSource] || turnSource;
}
const ACTION = { open: 'Opening offer', counter: 'Counteroffer', accept: 'Accepted', reject: 'Rejected', message: 'Message' };
const TERMINAL = ['agreed', 'rejected', 'deadlock', 'max_rounds_reached', 'completed'];

function esc(x) { const d = document.createElement('div'); d.textContent = x ?? ''; return d.innerHTML; }
function money(v, unit = '$') {
  if (v == null) return '—';
  const n = Number(v);
  const text = n.toLocaleString(undefined, { minimumFractionDigits: Number.isInteger(n) ? 0 : 2, maximumFractionDigits: 2 });
  if (!unit) return text;
  if (unit === '%') return text + '%';
  return /^[A-Za-z]/.test(unit) ? `${text} ${unit}` : unit + text;      // "$1,200" for currency, "45 days" for word units
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

/* "OR  Continue with Google / GitHub" block shared by the login and register pages.
   Rendered hidden, then revealed by initOAuthBlock() once the server says which providers are set up. */
const OAUTH_ICON = {
  google: '<svg viewBox="0 0 18 18" aria-hidden="true"><path fill="#4285F4" d="M17.64 9.2045c0-.6381-.0573-1.2518-.1636-1.8409H9v3.4814h4.8436c-.2086 1.125-.8427 2.0782-1.7959 2.7164v2.2581h2.9087c1.7018-1.5668 2.6836-3.874 2.6836-6.615z"/><path fill="#34A853" d="M9 18c2.43 0 4.4673-.806 5.9564-2.1805l-2.9087-2.2581c-.8059.54-1.8368.859-3.0477.859-2.344 0-4.3282-1.5831-5.036-3.7104H.9574v2.3318C2.4382 15.9832 5.4818 18 9 18z"/><path fill="#FBBC05" d="M3.964 10.71c-.18-.54-.2822-1.1168-.2822-1.71s.1023-1.17.2823-1.71V4.9582H.9573A8.9965 8.9965 0 0 0 0 9c0 1.4523.3477 2.8268.9573 4.0418L3.964 10.71z"/><path fill="#EA4335" d="M9 3.5795c1.3214 0 2.5077.4541 3.4405 1.346l2.5813-2.5814C13.4632.8918 11.426 0 9 0 5.4818 0 2.4382 2.0168.9573 4.9582L3.964 7.29C4.6718 5.1627 6.6559 3.5795 9 3.5795z"/></svg>',
  github: '<svg viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>'
};
function oauthBlock() {
  const btn = (p, label) => `<a class="btn secondary oauth-btn" data-provider="${p}" href="#">${OAUTH_ICON[p]}<span>Continue with ${label}</span></a>`;
  return `<div class="oauth-block" id="oauth" hidden><div class="auth-divider"><span>OR</span></div><div class="oauth-list">${btn('google', 'Google')}${btn('github', 'GitHub')}</div><div class="auth-hint oauth-hint" id="oauthHint"></div></div>`;
}
/* Wires the buttons to the backend. A provider that isn't configured is removed in production and
   shown disabled with a setup hint in development. Returns the server's auth config (or null). */
async function initOAuthBlock(next) {
  const box = document.getElementById('oauth');
  if (!box) return null;
  let cfg;
  try { cfg = await Api.auth.config(); } catch { return null; }
  const hints = [];
  box.querySelectorAll('[data-provider]').forEach(el => {
    const p = (cfg.providers || {})[el.dataset.provider] || {};
    if (p.enabled) { el.href = Api.auth.oauthUrl(el.dataset.provider, next); return; }
    if (!p.hint) { el.remove(); return; }
    el.removeAttribute('href'); el.setAttribute('aria-disabled', 'true'); el.title = p.hint; hints.push(p.hint);
  });
  document.getElementById('oauthHint').textContent = hints.join(' ');
  box.hidden = !box.querySelector('[data-provider]');
  return cfg;
}

/* Animated AI-agent mark: faint network nodes appear, two agents form, a signal passes between them,
   then the mark settles into its final still state (the CSS default). Subtle, ~3.5s, plays once per page
   (once per session in the app header). prefers-reduced-motion shows the settled mark immediately. */
function logoSVG(opts = {}) {
  const { animate = false, size = 26 } = opts;
  return `<svg class="ai-logo${animate ? ' logo-anim' : ''}" width="${size}" height="${size}" viewBox="0 0 48 48" fill="none" aria-hidden="true" focusable="false">
    <line class="lg-edge e1" x1="9" y1="11" x2="11.4" y2="20.6"/><line class="lg-edge e2" x1="39" y1="10" x2="36.6" y2="20.6"/>
    <line class="lg-edge e3" x1="10" y1="38" x2="11.4" y2="28.2"/><line class="lg-edge e4" x1="38" y1="38" x2="36.6" y2="28.2"/>
    <circle class="lg-node n1" cx="9" cy="11" r="1.7"/><circle class="lg-node n2" cx="39" cy="10" r="1.7"/>
    <circle class="lg-node n3" cx="10" cy="38" r="1.7"/><circle class="lg-node n4" cx="38" cy="38" r="1.7"/>
    <circle class="lg-pulse" cx="24" cy="24" r="16"/>
    <line class="lg-link" x1="21.4" y1="24" x2="26.6" y2="24"/>
    <circle class="lg-agent a" cx="16" cy="24" r="5.2"/><circle class="lg-agent b" cx="32" cy="24" r="5.2"/>
    <circle class="lg-core a" cx="16" cy="24" r="1.7"/><circle class="lg-core b" cx="32" cy="24" r="1.7"/>
    <circle class="lg-signal" cx="16" cy="24" r="2"/>
  </svg>`;
}
/* Full brand logo (matches the reference artwork): two agents - slate and copper - facing each other with
   chat bubbles inside an orbit ring. Animation: the orbit and network nodes form -> the two agents appear ->
   their messages appear -> a signal travels around the orbit -> the logo settles into its final still state. */
function logoFull(opts = {}) {
  const { animate = false, width = 150 } = opts, id = 'lf' + Math.random().toString(36).slice(2, 7);
  const body = 'M34 138 C30 108 46 94 70 91 C94 90 106 102 104 124 C103 130 100 135 96 138 Z';
  const head = 'M70 36 C86 35 92 49 90 60 C89 65 92 68 90 71 C88 74 84 74 84 79 C84 86 79 90 72 91 C58 92 48 80 49 64 C50 48 58 37 70 36 Z';
  const figure = (grad, cls) => `<g class="lf-agent ${cls}"><path d="${body}" fill="url(#${id}${grad}b)"/><path d="${head}" fill="url(#${id}${grad}h)"/>
      <path d="M36 134 C40 114 54 104 76 104" stroke="#fff" stroke-opacity=".55" stroke-width="1.6" fill="none" stroke-linecap="round"/>
      <circle class="lf-ring" cx="68" cy="64" r="8.5" fill="none" stroke="#fff" stroke-width="3"/><circle cx="68" cy="64" r="8.5" fill="none" stroke="url(#${id}${grad}h)" stroke-width=".9" stroke-opacity=".8"/></g>`;
  return `<svg class="ai-logo-full${animate ? ' lf-anim' : ''}" width="${width}" height="${Math.round(width * 160 / 220)}" viewBox="0 0 220 160" fill="none" role="img" aria-label="Multi-Agent AI Negotiation Platform logo">
    <defs>
      <linearGradient id="${id}sh" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#a7b8c5"/><stop offset=".6" stop-color="#617a8c"/><stop offset="1" stop-color="#7f95a4"/></linearGradient>
      <linearGradient id="${id}sb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6c8496"/><stop offset=".7" stop-color="#9fb1be" stop-opacity=".85"/><stop offset="1" stop-color="#e9eef1" stop-opacity=".15"/></linearGradient>
      <linearGradient id="${id}ch" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e6bf9c"/><stop offset=".6" stop-color="#b98259"/><stop offset="1" stop-color="#c79774"/></linearGradient>
      <linearGradient id="${id}cb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#b57f57"/><stop offset=".7" stop-color="#d7b393" stop-opacity=".85"/><stop offset="1" stop-color="#f4e6d9" stop-opacity=".15"/></linearGradient>
    </defs>
    <circle class="lf-orbit" cx="110" cy="80" r="66" stroke="#8d9ca8" stroke-opacity=".55" stroke-width="1" pathLength="100"/>
    <g class="lf-orbit-dot"><circle cx="110" cy="14" r="3.2" fill="#486675"/></g>
    <circle class="lf-node" cx="110" cy="14" r="4.6" fill="#7b8f9e"/><circle class="lf-node" cx="110" cy="146" r="4.6" fill="#7b8f9e"/>
    <circle class="lf-node" cx="158" cy="33" r="3" fill="#c28f68"/><circle class="lf-node" cx="62" cy="127" r="2.4" fill="#9db0bd"/>
    ${figure('s', 'left')}
    <g transform="translate(220 0) scale(-1 1)">${figure('c', 'right')}</g>
    <g class="lf-bubble b1"><path d="M96 53h30a5 5 0 0 1 5 5v13a5 5 0 0 1-5 5h-22l-8 7 2-7a5 5 0 0 1-5-5V58a5 5 0 0 1 5-5Z" fill="#6f8798"/><path d="M102 61h20M102 68h13" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/></g>
    <g class="lf-bubble b2"><path d="M104 83h30a5 5 0 0 1 5 5v13a5 5 0 0 1-5 5h-3l6 7-12-7h-16a5 5 0 0 1-5-5V88a5 5 0 0 1 5-5Z" fill="#c59a79"/><path d="M110 91h20M110 98h13" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/></g>
  </svg>`;
}

/* In the app header the animation plays only the first time in a browser session. */
function headerLogo() {
  let first = false;
  try { first = !sessionStorage.getItem('np_logo_played'); sessionStorage.setItem('np_logo_played', '1'); } catch { }
  return logoSVG({ animate: first, size: 26 });
}

function authHeader() {
  initTheme();
  const onLogin = /login\.html$/.test(location.pathname);       // the login card carries its own larger animated logo
  return `<canvas id="neuralBg" aria-hidden="true"></canvas><script src="neural-bg.js"></script><div class="auth-top"><a class="brand" href="login.html" aria-label="${PRODUCT}"><span class="brandmark">${logoSVG({ animate: !onLogin, size: 26 })}</span><span>Multi-Agent Negotiation Platform<span class="brand-sub">GENERATIVE AI · SIMULATION &amp; PRACTICE</span></span></a></div>`;
}

function nav(active) {
  initTheme();
  return `<a class="skip" href="#main">Skip to content</a><header><div class="nav"><a class="brand" href="index.html" aria-label="${PRODUCT} — home"><span class="brandmark">${headerLogo()}</span><span>Multi-Agent Negotiation Platform<span class="brand-sub">GENERATIVE AI · SIMULATION &amp; PRACTICE</span></span></a><nav aria-label="Primary"><a class="${active === 'home' ? 'active' : ''}" href="index.html">Scenarios</a><a class="${active === 'mine' ? 'active' : ''}" href="my-negotiations.html">My Negotiations</a><a class="${active === 'dash' ? 'active' : ''}" href="dashboard.html">Negotiation Analytics</a></nav><div class="nav-right"><button class="assistant-trigger" id="assistantTrigger" type="button" aria-label="Open AI Negotiation Assistant" aria-expanded="false" title="AI Negotiation Assistant"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12Z"/><path d="M9 11h6M9 14h3.5"/></svg><span>Assistant</span></button><button class="cmdk-trigger" id="cmdkTrigger" type="button" aria-label="Open command palette" title="Quick actions (Ctrl/⌘ K)"><span>⌘</span>K</button><button class="theme-toggle" id="themeToggle" type="button" aria-label="Toggle dark mode" title="Toggle dark mode"><span class="tt-icon"></span></button><span id="engineBadge" class="engine-badge" title="Reasoning engine status"><i></i> Checking engine</span><span class="profile-wrap" id="profileChip"></span></div></div></header>${cmdkMarkup()}`;
}

/* ─────────────────────────  Theme toggle (additive dark mode)  ───────────────────────── */
const THEME_KEY = 'np_theme';
function initTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  const theme = saved || (window.matchMedia && window.matchMedia('prefers-color-scheme: dark').matches ? 'dark' : 'light');
  document.documentElement.setAttribute('data-theme', theme);
  document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('themeToggle');
    if (btn) btn.onclick = toggleTheme;
    const t = document.getElementById('cmdkTrigger');
    if (t) t.onclick = () => openPalette();
    document.addEventListener('keydown', e => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        const bd = document.getElementById('cmdkBackdrop'); if (!bd) return;
        bd.hidden ? openPalette() : closePalette();
      }
    });
  });
}
function toggleTheme() {
  const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem(THEME_KEY, next);
}

/* ─────────────────────────  Command palette (Ctrl/⌘ K)  ───────────────────────── */
function cmdkMarkup() {
  return `<div class="cmdk-backdrop" id="cmdkBackdrop" hidden><div class="cmdk" role="dialog" aria-modal="true" aria-label="Quick actions">
    <input id="cmdkInput" placeholder="Jump to a page or action…" autocomplete="off" aria-label="Search quick actions">
    <div class="cmdk-list" id="cmdkList" role="listbox"></div>
    <div class="cmdk-foot"><span>↑↓ navigate</span><span>↵ select</span><span>esc close</span></div>
  </div></div>`;
}
function paletteActions() {
  const s = Session.get();
  const acts = [
    { label: 'Start a new negotiation', hint: 'Scenarios', go: 'index.html' },
    { label: 'My Negotiations', hint: 'Skill score & badges', go: 'my-negotiations.html' },
    { label: 'Negotiation Analytics', hint: 'Platform stats & leaderboard', go: 'dashboard.html' },
    { label: 'Security & Privacy', hint: 'Account protections', go: 'security.html' },
  ];
  if (s.scenarioId) acts.push({ label: 'Agent Configuration', hint: s.scenarioName || '', go: 'agents.html' });
  if (s.negotiationId) {
    acts.push({ label: 'Negotiation Area', hint: 'Resume live session', go: 'negotiation.html' });
    acts.push({ label: 'Negotiation Outcome', hint: 'View results', go: 'outcome.html?id=' + encodeURIComponent(s.negotiationId) });
  }
  acts.push({ label: 'Toggle dark / light mode', hint: 'Appearance', run: toggleTheme });
  if (_currentUser) acts.push({ label: 'Log out', hint: _currentUser.username, run: async () => { try { await Api.auth.logout(); } catch {} location.href = 'login.html'; } });
  return acts;
}
let _cmdkBound = false, _cmdkSel = 0;
function openPalette() {
  const bd = document.getElementById('cmdkBackdrop'); if (!bd) return;
  bd.hidden = false; _cmdkSel = 0;
  renderPalette('');
  const input = document.getElementById('cmdkInput'); input.value = ''; input.focus();
  if (!_cmdkBound) {
    _cmdkBound = true;
    input.addEventListener('input', () => { _cmdkSel = 0; renderPalette(input.value); });
    document.addEventListener('keydown', e => {
      if (document.getElementById('cmdkBackdrop').hidden) return;
      if (e.key === 'Escape') closePalette();
      else if (e.key === 'ArrowDown') { e.preventDefault(); moveSel(1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); moveSel(-1); }
      else if (e.key === 'Enter') { e.preventDefault(); const items = document.querySelectorAll('#cmdkList .cmdk-item'); if (items[_cmdkSel]) items[_cmdkSel].click(); }
    });
    bd.addEventListener('click', e => { if (e.target === bd) closePalette(); });
  }
}
function closePalette() { const bd = document.getElementById('cmdkBackdrop'); if (bd) bd.hidden = true; }
function moveSel(d) {
  const items = document.querySelectorAll('#cmdkList .cmdk-item'); if (!items.length) return;
  _cmdkSel = (_cmdkSel + d + items.length) % items.length;
  items.forEach((it, i) => it.classList.toggle('sel', i === _cmdkSel));
  items[_cmdkSel].scrollIntoView({ block: 'nearest' });
}
function renderPalette(q) {
  const list = document.getElementById('cmdkList');
  const acts = paletteActions().filter(a => !q || a.label.toLowerCase().includes(q.toLowerCase()));
  list.innerHTML = acts.length ? acts.map((a, i) => `<div class="cmdk-item ${i === 0 ? 'sel' : ''}" role="option" data-i="${i}"><b>${esc(a.label)}</b>${a.hint ? `<small>${esc(a.hint)}</small>` : ''}</div>`).join('')
    : '<div class="cmdk-empty">No matching action.</div>';
  list.querySelectorAll('.cmdk-item').forEach(el => el.onclick = () => { const a = acts[Number(el.dataset.i)]; closePalette(); if (a.run) a.run(); else location.href = a.go; });
}

/* ─────────────────────────  Agent avatar (identity + live "thinking" ring)  ───────────────────────── */
const PERSONALITY_GLYPH = { aggressive: '▲', collaborative: '◆', risk_averse: '●', competitive: '▼', empathetic: '♥', strategic: '■', opportunistic: '◗', compromising: '⬢', analytical: '◈' };
const PERSON_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21a8 8 0 0 0-16 0"/><circle cx="12" cy="7" r="4"/></svg>';

/* ── Role icons: one distinct icon per role, shared by the scenario cards, agent configuration, negotiation and outcome pages.
   Resolved from the role label of the selected scenario's agents, so a new scenario only needs a role name that matches a rule
   below (or falls back to the generic person icon). ── */
const _svg = inner => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${inner}</svg>`;
const ROLE_ICONS = {
  buyer: _svg('<circle cx="9" cy="20" r="1.2"/><circle cx="18" cy="20" r="1.2"/><path d="M2 3h3l2.7 11.4a2 2 0 0 0 2 1.6h7.7a2 2 0 0 0 2-1.5L21 7H6"/>'),                          // shopping cart
  seller: _svg('<path d="M3 9.5 5 4h14l2 5.5"/><path d="M3 9.5a3 3 0 0 0 6 0 3 3 0 0 0 6 0 3 3 0 0 0 6 0"/><path d="M5 12.5V20h14v-7.5"/><path d="M10 20v-4h4v4"/>'),                              // storefront
  candidate: _svg('<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"/><path d="M3 13h18"/>'),                                                          // briefcase
  employer: _svg('<path d="M4 21V5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v16"/><path d="M14 10h5a1 1 0 0 1 1 1v10"/><path d="M2 21h20"/><path d="M8 8h2M8 12h2M8 16h2M17 14h.01M17 18h.01"/>'),                   // office building
  recruiter: _svg('<circle cx="9" cy="8" r="3.2"/><path d="M3 20a6 6 0 0 1 12 0"/><circle cx="17.5" cy="9" r="2.4"/><path d="M16.5 14.2A5 5 0 0 1 21.5 19"/>'),                                      // people
  projectlead: _svg('<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V3h6v1"/><path d="m8.5 11 1.5 1.5 3-3"/><path d="M8.5 16.5h7"/>'),                                               // clipboard with check
  finance: _svg('<rect x="5" y="2.5" width="14" height="19" rx="2"/><rect x="8" y="5.5" width="8" height="4" rx="1"/><path d="M8.5 13h.01M12 13h.01M15.5 13h.01M8.5 17h.01M12 17h.01M15.5 17h.01"/>'),   // calculator
  freelancer: _svg('<rect x="4" y="5" width="16" height="11" rx="1.5"/><path d="M2 20h20"/><path d="M9 20l.6-4h4.8l.6 4"/>'),                                                                        // laptop
  client: _svg('<circle cx="12" cy="8" r="4"/><path d="M5 21a7 7 0 0 1 14 0"/><path d="m16.5 14.5 1.5 1.5 3-3"/>'),                                                                                   // verified user
  agency: _svg('<path d="m8 8-5 4 5 4"/><path d="m16 8 5 4-5 4"/><path d="m14 5-4 14"/>'),                                                                                                          // code
  supplier: _svg('<rect x="1.5" y="6" width="13" height="10" rx="1"/><path d="M14.5 9h4l3 3.5V16h-7"/><circle cx="6" cy="18" r="1.8"/><circle cx="17.5" cy="18" r="1.8"/>'),                           // delivery truck
  manufacturer: _svg('<path d="M3 21V10l6 3.5V10l6 3.5V6h4a2 2 0 0 1 2 2v13"/><path d="M2 21h20"/><path d="M8 17h1M13 17h1M18 17h1"/>'),                                                              // factory
  sponsor: _svg('<circle cx="12" cy="8" r="4"/><path d="M5 21a7 7 0 0 1 14 0"/><path d="M12 14v3.5"/><path d="m10.5 15.5 1.5 2 1.5-2"/>'),                                                              // exec / sponsor
  deptA: _svg('<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 12.5 9 5 9-5"/><path d="m3 17 9 5 9-5"/>'),                                                                                          // layers: the roadmap-heavy side
  deptB: _svg('<path d="M21 8 12 3 3 8v8l9 5 9-5V8Z"/><path d="m3 8 9 5 9-5"/><path d="M12 13v8"/>'),                                                                                              // box: the deliverables side
  department: _svg('<rect x="3" y="3" width="8" height="8" rx="1.5"/><rect x="13" y="3" width="8" height="8" rx="1.5"/><rect x="3" y="13" width="8" height="8" rx="1.5"/><path d="M17 13v8M13 17h8"/>'),   // grid / department
  person: PERSON_ICON,
};
/* Ordered rules: first match wins. Roles with the same word in different scenarios (e.g. "Buyer") intentionally share an icon. */
const ROLE_RULES = [
  [/hiring manager|recruit|\bhr\b/i, 'recruiter'], [/employer/i, 'employer'], [/candidate|applicant|job seeker/i, 'candidate'],
  [/finance|financial|cfo|accountant|budget owner/i, 'finance'],
  [/freelanc|contractor|consultant|designer/i, 'freelancer'],
  [/agency|developer|engineer|vendor of software/i, 'agency'],
  [/client/i, 'client'],
  [/project sponsor|sponsor|executive/i, 'sponsor'], [/delivery lead|delivery|project manager|\bpm\b/i, 'projectlead'],
  [/(department|dept)\s*a\b/i, 'deptA'], [/(department|dept)\s*b\b/i, 'deptB'], [/department|dept|team lead/i, 'department'],
  [/manufactur/i, 'manufacturer'], [/supplier|distributor/i, 'supplier'],
  [/buyer|purchas|procure|customer/i, 'buyer'],
  [/vendor|seller|merchant|retailer|shop/i, 'seller'],
];
function roleIconKey(role) { const r = String(role || ''); const hit = ROLE_RULES.find(([re]) => re.test(r)); return hit ? hit[1] : 'person'; }
function roleIcon(role) { return ROLE_ICONS[roleIconKey(role)]; }
function avatarHTML(role, personality, opts = {}) {
  const glyph = PERSONALITY_GLYPH[personality] || '';
  const cls = ['avatar', opts.human ? 'human' : '', opts.active ? 'active' : '', opts.thinking ? 'thinking' : ''].filter(Boolean).join(' ');
  const title = `${role || 'Agent'}${opts.human ? ' (you)' : ''}`;
  return `<span class="${cls}" aria-hidden="true" title="${esc(title)}" data-role-icon="${roleIconKey(role)}"><em>${roleIcon(role)}</em>${glyph ? `<i class="glyph">${glyph}</i>` : ''}</span>`;
}

/* ─────────────────────────  Deal Momentum gauge (derived from real offer gap trend)  ───────────────────────── */
/* momentum = how much closer the two latest offers are than the two opening offers, 0-100. */
function computeMomentum(agents, history, status) {
  const isOffer = o => (o.action === 'open' || o.action === 'counter') && o.value != null;
  const byAgent = id => history.filter(o => o.agent_id === id && isOffer(o));
  if (agents.length < 2) return null;
  const a = byAgent(agents[0].id), b = byAgent(agents[1].id);
  if (!a.length || !b.length) return { pct: 0, label: 'Awaiting offers', detail: 'Both sides need to make an opening offer.' };
  if (TERMINAL.includes(status)) {
    if (status === 'agreed') return { pct: 100, label: 'Deal closed', detail: 'An agreement was reached.' };
    return { pct: Math.max(0, Math.round(100 - Math.min(100, Math.abs(b[b.length - 1].value - a[a.length - 1].value) / Math.max(Math.abs(b[0].value - a[0].value), 1e-9) * 100))), label: 'Ended without a deal', detail: 'The negotiation ended before positions met.' };
  }
  const initGap = Math.abs(b[0].value - a[0].value) || 1e-9;
  const nowGap = Math.abs(b[b.length - 1].value - a[a.length - 1].value);
  const pct = Math.max(0, Math.min(100, Math.round((1 - nowGap / initGap) * 100)));
  const label = pct >= 80 ? 'Very close to a deal' : pct >= 50 ? 'Converging' : pct >= 20 ? 'Early positioning' : 'Far apart';
  return { pct, label, detail: `Positions have closed ${pct}% of the original gap.` };
}
function gaugeSVG(pct, size = 96) {
  const r = size / 2 - 8, c = size / 2, circ = 2 * Math.PI * r;
  const dash = circ * Math.max(0, Math.min(100, pct)) / 100;
  return `<svg viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" class="gauge" role="img" aria-label="Deal momentum ${pct}%">
    <circle cx="${c}" cy="${c}" r="${r}" class="gauge-bg"/>
    <circle cx="${c}" cy="${c}" r="${r}" class="gauge-fg" stroke-dasharray="${dash.toFixed(1)} ${circ.toFixed(1)}" transform="rotate(-90 ${c} ${c})"/>
    <text x="${c}" y="${c - 3}" class="gauge-num" text-anchor="middle">${pct}%</text>
    <text x="${c}" y="${c + 15}" class="gauge-cap" text-anchor="middle">momentum</text>
  </svg>`;
}

/* ─────────────────────────  Confetti burst (cosmetic only, respects reduced motion)  ───────────────────────── */
function celebrate() {
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const host = document.createElement('canvas');
  host.className = 'confetti-canvas';
  document.body.appendChild(host);
  const ctx = host.getContext('2d');
  const resize = () => { host.width = innerWidth; host.height = innerHeight; };
  resize();
  const colors = ['#55788a', '#b08a62', '#5e8f74', '#a65e59'];
  const bits = Array.from({ length: 90 }, () => ({
    x: Math.random() * host.width, y: -20 - Math.random() * host.height * .3,
    vx: (Math.random() - .5) * 2.4, vy: 2 + Math.random() * 3, r: 3 + Math.random() * 4,
    rot: Math.random() * Math.PI, vr: (Math.random() - .5) * .3, c: colors[Math.floor(Math.random() * colors.length)]
  }));
  let frame = 0;
  (function tick() {
    frame++;
    ctx.clearRect(0, 0, host.width, host.height);
    bits.forEach(b => {
      b.x += b.vx; b.y += b.vy; b.vy += .03; b.rot += b.vr;
      ctx.save(); ctx.translate(b.x, b.y); ctx.rotate(b.rot); ctx.fillStyle = b.c;
      ctx.fillRect(-b.r, -b.r * .6, b.r * 2, b.r * 1.2); ctx.restore();
    });
    if (frame < 160) requestAnimationFrame(tick); else host.remove();
  })();
  setTimeout(() => host.isConnected && host.remove(), 4000);
}
function engineBadge() {
  Api.health().then(h => {
    const b = document.getElementById('engineBadge'); if (!b) return;
    const verified = (h.llm.providers || []).some(p => p.verified);
    b.innerHTML = `<i></i> ${verified ? 'Live LLM verified' : h.llm.configured ? 'LLM key found · not tested' : 'Mock engine only'}`;
    b.classList.toggle('live', verified);
  }).catch(() => { const b = document.getElementById('engineBadge'); if (b) b.innerHTML = '<i></i> Backend offline'; });
}

/* Engine description derived from real counters (never from the requested mode alone). */
function engineLabel(s) {
  if (s.mode === 'llm') {
    const base = `Live LLM${s.llm_provider ? ' · ' + (PROVIDER_LABEL[s.llm_provider] || s.llm_provider) : ''}`;
    return s.fallback_count ? `${base} (${s.fallback_count} fallback turn${s.fallback_count > 1 ? 's' : ''})` : base;
  }
  return 'Mock / Rule-based';
}

/* Offer-movement chart. `history` items need {agent_id, action, value}. Pure SVG, theme-aware via CSS classes. */
function offerChart(agents, history, unit, finalValue, compact = false) {
  const pts = history.map((o, i) => ({ i, o })).filter(x => (x.o.action === 'open' || x.o.action === 'counter') && x.o.value != null);
  if (!pts.length) return '<div class="empty" style="padding:14px">Offer movement appears once offers are made.</div>';
  const W = compact ? 270 : 640, H = compact ? 190 : 230, L = compact ? 50 : 62, R = compact ? 10 : 18, T = 18, B = 30;
  const vals = pts.map(p => p.o.value).concat(finalValue != null ? [finalValue] : []);
  let lo = Math.min(...vals), hi = Math.max(...vals); const pad = (hi - lo) * .14 || 1; lo -= pad; hi += pad;
  const n = Math.max(1, Math.max(...pts.map(p => p.i)));
  const X = i => L + (W - L - R) * (i / n), Y = v => T + (H - T - B) * (1 - (v - lo) / (hi - lo));
  let g = '';
  const ticks = compact ? 3 : 5;
  for (let k = 0; k < ticks; k++) { const v = lo + (hi - lo) * k / (ticks - 1); g += `<line class="gridln" x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}"/><text class="axis" x="${L - 8}" y="${Y(v) + 4}" text-anchor="end">${esc(money(v, unit))}</text>`; }
  let lines = '';
  agents.forEach((a, ci) => {
    const mine = pts.filter(p => p.o.agent_id === a.id); if (!mine.length) return;
    lines += `<polyline class="ln ln${ci}" fill="none" points="${mine.map(p => X(p.i).toFixed(1) + ',' + Y(p.o.value).toFixed(1)).join(' ')}"/>` +
      mine.map(p => `<circle class="dot dot${ci}" cx="${X(p.i).toFixed(1)}" cy="${Y(p.o.value).toFixed(1)}" r="4"><title>${esc(a.role_label || a.role)} · R${p.o.round}: ${esc(money(p.o.value, unit))}</title></circle>`).join('');
  });
  const fin = finalValue != null ? `<line class="finalln" x1="${L}" x2="${W - R}" y1="${Y(finalValue)}" y2="${Y(finalValue)}"/>${compact ? '' : `<text class="finaltxt" x="${L + 8}" y="${Y(finalValue) - 6}" text-anchor="start">Agreement ${esc(money(finalValue, unit))}</text>`}` : '';
  const legend = agents.map((a, i) => `<span class="lg"><i class="lgdot lgdot${i}"></i>${esc(a.role_label || a.role)}</span>`).join('');
  return `<div class="chart-legend">${legend}</div><svg class="chart${compact ? " compact" : ""}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Offer movement by turn">${g}${fin}${lines}<text class="axis" x="${L}" y="${H - 8}">${compact ? 'Offers in order →' : 'Offers in order of play →'}</text></svg>`;
}

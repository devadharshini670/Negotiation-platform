/* AI Negotiation Assistant — front end.
   READ-ONLY by design: this file only ever calls /api/assistant/* (chat, history, reset). It has no code
   path that touches negotiations (no create / step / run / human-action calls), so it cannot change one. */
(() => {
  if (window.__assistantReady) return;
  window.__assistantReady = true;
  const trigger = document.getElementById('assistantTrigger');
  if (!trigger) return;

  const PAGE = (location.pathname.split('/').pop() || 'index.html');
  const OPEN_KEY = 'np_assistant_open';
  const WIDE = 1180;                                    // docked (page reflows) at or above this width
  const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const $ = id => document.getElementById(id);
  let busy = false, built = false, open = false;

  /* ---------- what the assistant is looking at (sent as ids only; the server builds the read-only context) ---------- */
  function currentContext() {
    const qs = new URLSearchParams(location.search), s = Session.get();
    const onNegotiation = /^(negotiation|outcome)\.html$/.test(PAGE);
    const negotiation_id = onNegotiation ? (qs.get('id') || s.negotiationId || null) : null;
    const pick = side => { const e = document.querySelector(`.personality.selected[data-side="${side}"]`); return e ? e.dataset.p : null; };   // choices on the agents page that aren't saved yet
    const wf = document.querySelector('#modeTiles .tile[aria-pressed="true"]');
    const setup = !negotiation_id && s.scenarioId ? { scenario_id: s.scenarioId, personality_a: pick('a') || s.personalityA, personality_b: pick('b') || s.personalityB, workflow_mode: (wf && wf.dataset.wf) || s.workflowMode, mode: s.mode } : null;
    const providerSel = document.getElementById('provider');           // the agents page dropdown, if visible
    const provider = (providerSel && providerSel.value) || s.llmProvider || null;
    return { page: PAGE, negotiation_id, setup, provider, phase: negotiation_id ? (PAGE === 'outcome.html' ? 'result' : 'negotiation') : setup ? 'setup' : 'general' };
  }

  const QUICK = {
    general: { general: ['What does this platform do?', 'How do the personalities differ?', 'How are scores and badges calculated?'], current: [] },
    setup: { general: ['What does this platform do?', 'What is the difference between Practice and Simulation mode?'], current: ['Explain the scenario I selected', 'What will the personalities I chose do?'] },
    negotiation: { general: ['What is a deadlock?', 'How do the personalities affect a negotiation?'], current: ['What is the current status?', 'Why did the last agent counter?', 'Summarize the transcript so far'] },
    result: { general: ['How are scores and badges calculated?'], current: ['Why did this negotiation end this way?', 'Explain my badge and score', 'Which agent conceded more?'] }
  };
  const WELCOME = "Hi! I'm your Negotiation Assistant. I can explain how the platform works, the scenario and personalities, and — when a negotiation is open — why an agent acted as it did and what the result means.\n\nI only explain: I can't change offers, personalities or results. You stay in control.";

  /* ---------- build the panel once ---------- */
  function build() {
    if (built) return; built = true;
    const el = document.createElement('aside');
    el.id = 'assistantPanel'; el.className = 'assistant'; el.hidden = true;
    el.setAttribute('role', 'complementary'); el.setAttribute('aria-label', 'AI Negotiation Assistant');
    el.innerHTML = `
      <div class="as-head"><div class="as-title"><span class="brandmark">${logoSVG({ animate: false, size: 22 })}</span><div><b>AI Negotiation Assistant</b><small id="asContext">General help</small></div></div>
        <div class="as-actions">
          <button type="button" id="asReset" title="Start a new conversation" aria-label="Start a new conversation"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg></button>
          <button type="button" id="asClose" title="Minimize" aria-label="Minimize the assistant"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M6 12h12"/></svg></button>
        </div></div>
      <div class="as-body" id="asBody" aria-live="polite"></div>
      <div class="as-quick" id="asQuick"></div>
      <form class="as-form" id="asForm" autocomplete="off"><textarea id="asInput" rows="1" maxlength="800" placeholder="Ask about the platform or your negotiation…" aria-label="Your question"></textarea>
        <button type="submit" id="asSend" aria-label="Send question"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4 20-7Z"/></svg></button></form>
      <div class="as-foot">Explains only — it can't make offers or change anything in your negotiation.</div>`;
    document.body.appendChild(el);
    $('asClose').onclick = () => setOpen(false);
    $('asReset').onclick = resetConversation;
    $('asForm').onsubmit = e => { e.preventDefault(); send($('asInput').value); };
    const input = $('asInput');
    input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input.value); } });
    input.addEventListener('input', () => { input.style.height = 'auto'; input.style.height = Math.min(110, input.scrollHeight) + 'px'; });
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && open && !document.querySelector('.cmdk-backdrop:not([hidden])')) setOpen(false); });
    // Overlay mode: going back to the page minimizes the panel so it never sits on top of the controls.
    document.addEventListener('pointerdown', e => {
      if (open && !docked() && !el.contains(e.target) && !trigger.contains(e.target)) setOpen(false);
    }, true);
    window.addEventListener('resize', () => { if (open) applyLayout(); });
    restoreHistory();
  }

  const docked = () => window.innerWidth >= WIDE;
  function applyLayout() {
    const head = document.querySelector('header');                       // the panel sits below the header so the header never moves
    document.documentElement.style.setProperty('--assistant-top', (head ? Math.round(head.getBoundingClientRect().bottom) : 0) + 'px');
    const wasDocked = document.documentElement.classList.contains('assistant-docked');
    if (open && !docked() && wasDocked && /^(negotiation|outcome)\.html$/.test(PAGE)) { setOpen(false); return; }   // resized too narrow: get out of the way
    document.documentElement.classList.toggle('assistant-docked', open && docked());
  }

  function setOpen(next, remember = true) {
    build();
    const panel = $('assistantPanel');
    open = next;
    trigger.setAttribute('aria-expanded', String(open));
    if (remember) try { sessionStorage.setItem(OPEN_KEY, open ? '1' : '0'); } catch { }
    if (open) {
      panel.hidden = false; refreshHeader();
      void panel.offsetWidth;                                  // let the browser register the start position so it slides in
      panel.classList.add('show'); applyLayout();
      setTimeout(() => $('asInput').focus({ preventScroll: true }), reduceMotion ? 0 : 280);
    } else {
      panel.classList.remove('show'); document.documentElement.classList.remove('assistant-docked');
      setTimeout(() => { if (!open) panel.hidden = true; }, reduceMotion ? 0 : 300);
    }
  }

  /* ---------- messages ---------- */
  function scrollDown() { const b = $('asBody'); b.scrollTop = b.scrollHeight; }
  function addBubble(role, text) {
    const d = document.createElement('div');
    d.className = 'as-msg ' + (role === 'user' ? 'me' : 'bot');
    d.textContent = text || '';                                // always textContent: replies are never interpreted as HTML
    $('asBody').appendChild(d); scrollDown();
    return d;
  }
  function addNote(text) {
    if (!text) return;
    const n = document.createElement('div'); n.className = 'as-note'; n.textContent = text; $('asBody').appendChild(n); scrollDown();
  }
  function typingBubble() {
    const d = document.createElement('div'); d.className = 'as-msg bot as-typing'; d.setAttribute('aria-label', 'Assistant is typing');
    d.innerHTML = '<i></i><i></i><i></i>'; $('asBody').appendChild(d); scrollDown(); return d;
  }
  /* Simple typewriter: finishes in about two seconds whatever the length. */
  function typeInto(el, text) {
    return new Promise(resolve => {
      if (reduceMotion) { el.textContent = text; scrollDown(); return resolve(); }
      const per = Math.max(1, Math.ceil(text.length / 110)); let i = 0;
      const tick = () => { i = Math.min(text.length, i + per); el.textContent = text.slice(0, i); scrollDown(); i >= text.length ? resolve() : setTimeout(tick, 16); };
      tick();
    });
  }

  async function restoreHistory() {
    $('asBody').innerHTML = '';
    addBubble('bot', WELCOME);
    try {
      const { messages } = await Api.assistant.history();
      for (const m of messages) addBubble(m.role === 'user' ? 'user' : 'bot', m.content);
    } catch { /* offline: just show the welcome */ }
    renderQuick();
  }

  function renderQuick() {
    const phase = currentContext().phase, q = QUICK[phase];
    const picks = [...q.current.slice(0, 2), ...q.general.slice(0, 2)].slice(0, 4);
    const box = $('asQuick');
    box.innerHTML = '<span class="lbl">Quick questions</span>';
    for (const text of picks) {
      const b = document.createElement('button'); b.type = 'button'; b.textContent = text; b.onclick = () => send(text); box.appendChild(b);
    }
  }

  function refreshHeader() {
    const c = currentContext();
    $('asContext').textContent = { general: 'General help', setup: 'Your selected setup', negotiation: 'Current negotiation', result: 'Negotiation result' }[c.phase];
    renderQuick();
  }

  const PROVIDER_NAME = { groq: 'Groq', gemini: 'Gemini' };
  function addError(text, retryText) {
    const d = document.createElement('div'); d.className = 'as-msg bot as-err'; d.setAttribute('role', 'alert');
    d.textContent = text;
    if (retryText) {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'as-retry'; b.textContent = 'Try again';
      b.onclick = () => { d.remove(); send(retryText); }; d.appendChild(b);
    }
    $('asBody').appendChild(d); scrollDown(); return d;
  }

  async function send(raw) {
    const text = (raw || '').trim();
    if (!text || busy) return;
    if (text.length > 800) { addError('That message is too long (' + text.length + ' characters). Please keep it under 800 characters.'); return; }
    busy = true; $('asSend').disabled = true;
    const input = $('asInput'); input.value = ''; input.style.height = 'auto';
    addBubble('user', text);
    const typing = typingBubble();
    const c = currentContext();
    try {
      const out = await Api.assistant.chat({ message: text, page: c.page, negotiation_id: c.negotiation_id, setup: c.setup, provider: c.provider });
      typing.remove();
      const bubble = addBubble('bot', '');
      await typeInto(bubble, out.reply);
      if (out.source === 'ai') addNote(`Answered by ${PROVIDER_NAME[out.provider] || out.provider}${out.model ? ' · ' + out.model : ''}`);
      else if (out.source === 'builtin') addNote('Built-in safety notice (not an AI answer)');
    } catch (e) {
      typing.remove();
      const msg = e.status === 429 ? 'You are asking very quickly — please wait a moment and try again.'
        : e.status === 0 || e instanceof TypeError ? 'Could not reach the server. Check that the backend is running, then try again.'
        : (e.message || 'The AI assistant could not answer.');
      addError(msg + ' Your negotiation is unaffected.', e.status === 400 ? null : text);
    } finally { busy = false; $('asSend').disabled = false; input.focus({ preventScroll: true }); }
  }

  async function resetConversation() {
    try { await Api.assistant.reset(); } catch { }
    await restoreHistory();
  }

  trigger.onclick = () => setOpen(!open);
  let wasOpen = false; try { wasOpen = sessionStorage.getItem(OPEN_KEY) === '1'; } catch { }
  if (wasOpen && docked()) setOpen(true, false);                // reopen on the next page only when it can dock without covering anything
})();

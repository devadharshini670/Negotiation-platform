/* Animated AI / neural-network background for the sign-in screens.
   A light, slow-moving network of nodes and connections with small data pulses travelling along them.
   Colours follow the app theme (warm light by default, adapts to dark mode). Pure canvas, no libraries.
   Respects prefers-reduced-motion (draws one still frame), pauses in hidden tabs, and is capped for performance. */
(() => {
  const canvas = document.getElementById('neuralBg');
  if (!canvas || canvas.dataset.started) return;
  canvas.dataset.started = '1';
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const PALETTES = {
    light: { node: [112, 138, 154], warm: [190, 140, 100], line: [120, 140, 155], pulse: [72, 102, 117], lineA: .17, nodeA: .55, ribbon: [255, 255, 255], spark: [214, 170, 130],
             waves: [{ c: [238, 206, 178], a: .20, y: .80, amp: 30, f: .0042, v: .00022, from: 'bottom' }, { c: [172, 192, 205], a: .15, y: .88, amp: 24, f: .0034, v: -.00018, from: 'bottom' }, { c: [240, 214, 188], a: .16, y: .12, amp: 26, f: .0038, v: .00016, from: 'top' }] },
    dark:  { node: [127, 166, 184], warm: [190, 150, 118], line: [127, 166, 184], pulse: [157, 193, 207], lineA: .13, nodeA: .45, ribbon: [200, 225, 235], spark: [210, 170, 130],
             waves: [{ c: [90, 120, 140], a: .10, y: .82, amp: 28, f: .0040, v: .00020, from: 'bottom' }, { c: [140, 110, 90], a: .07, y: .12, amp: 24, f: .0036, v: .00015, from: 'top' }] }
  };
  let pal = PALETTES.light, w = 0, h = 0, dpr = 1, nodes = [], pulses = [], linkDist = 140, last = 0, lastSpawn = 0, themeCheck = 0, raf = 0;
  const rgba = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
  const rand = (a, b) => a + Math.random() * (b - a);

  function readTheme() {
    pal = document.documentElement.getAttribute('data-theme') === 'dark' ? PALETTES.dark : PALETTES.light;
  }

  function build() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = window.innerWidth; h = window.innerHeight;
    canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
    canvas.style.width = w + 'px'; canvas.style.height = h + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const count = Math.round(Math.min(64, Math.max(24, (w * h) / 26000)));
    linkDist = Math.min(170, Math.max(105, Math.sqrt(w * h) / 8.5));
    nodes = Array.from({ length: count }, (_, i) => ({
      x: rand(0, w), y: rand(0, h), vx: rand(-.045, .045), vy: rand(-.03, .03), r: rand(1.5, 2.8),
      warm: Math.random() < .22, seed: Math.random() * 6.28, glow: 0, agent: i % 11 === 0
    }));
    pulses = [];
  }

  function step(dt, t) {
    for (const n of nodes) {
      // slow drift plus a gentle shared flow so the whole field seems to breathe
      n.x += (n.vx + Math.sin(t * .00022 + n.y * .004 + n.seed) * .018) * dt * .06;
      n.y += (n.vy + Math.cos(t * .00018 + n.x * .004 + n.seed) * .014) * dt * .06;
      if (n.x < -30) n.x = w + 30; else if (n.x > w + 30) n.x = -30;
      if (n.y < -30) n.y = h + 30; else if (n.y > h + 30) n.y = -30;
      n.glow = Math.max(0, n.glow - dt * .0016);
    }
  }

  function neighbours(a) {
    const out = [];
    for (const b of nodes) {
      if (b === a) continue;
      const dx = a.x - b.x, dy = a.y - b.y;
      if (dx * dx + dy * dy < linkDist * linkDist) out.push(b);
    }
    return out;
  }

  function spawnPulse(now) {
    if (pulses.length >= 8) return;
    const a = nodes[(Math.random() * nodes.length) | 0], near = neighbours(a);
    if (!near.length) return;
    pulses.push({ a, b: near[(Math.random() * near.length) | 0], t0: now, dur: rand(1500, 2600) });
  }

  /* Soft layered waves + two luminous ribbons with travelling sparkles (the "flowing" backdrop). */
  function waveY(x, t, wv) { return h * wv.y + Math.sin(x * wv.f + t * wv.v * 5) * wv.amp + Math.sin(x * wv.f * .43 - t * wv.v * 3.4) * wv.amp * .55; }
  function drawWaves(t) {
    for (const wv of pal.waves) {
      ctx.beginPath(); ctx.moveTo(0, wv.from === 'top' ? 0 : h);
      for (let x = 0; x <= w + 14; x += 14) ctx.lineTo(x, waveY(x, t, wv));
      ctx.lineTo(w + 14, wv.from === 'top' ? 0 : h); ctx.closePath();
      const g = ctx.createLinearGradient(0, wv.from === 'top' ? 0 : h * wv.y - 40, 0, wv.from === 'top' ? h * wv.y + 40 : h);
      g.addColorStop(wv.from === 'top' ? 0 : 1, rgba(wv.c, wv.a)); g.addColorStop(wv.from === 'top' ? 1 : 0, rgba(wv.c, wv.a * .15));
      ctx.fillStyle = g; ctx.fill();
    }
  }
  const ribbons = [{ y: .40, a1: 52, a2: 80, f1: .0035, f2: .0011, v: .00035, ph: 0 }, { y: .64, a1: 40, a2: 64, f1: .003, f2: .0013, v: -.0003, ph: 2.1 }];
  function ribbonY(r, x, t) { return h * r.y + Math.sin(x * r.f1 + t * r.v + r.ph) * r.a1 + Math.sin(x * r.f2 - t * r.v * .8 + r.ph) * r.a2; }
  function drawRibbons(t) {
    for (const r of ribbons) {
      const g = ctx.createLinearGradient(0, 0, w, 0);
      g.addColorStop(0, rgba(pal.ribbon, 0)); g.addColorStop(.22, rgba(pal.ribbon, .55)); g.addColorStop(.5, rgba(pal.spark, .32)); g.addColorStop(.78, rgba(pal.ribbon, .55)); g.addColorStop(1, rgba(pal.ribbon, 0));
      ctx.strokeStyle = g; ctx.lineWidth = 1.4; ctx.beginPath();
      for (let x = -10; x <= w + 10; x += 10) { const y = ribbonY(r, x, t); x === -10 ? ctx.moveTo(x, y) : ctx.lineTo(x, y); }
      ctx.stroke();
      for (let k = 0; k < 7; k++) {                    // sparkles drifting along the ribbon
        const u = ((t * (.000045 + k * .000006) * (r.v > 0 ? 1 : -1) + k / 7) % 1 + 1) % 1, x = u * w, y = ribbonY(r, x, t);
        const a = Math.sin(Math.PI * u) * (.35 + .35 * Math.sin(t * .002 + k));
        ctx.fillStyle = rgba(k % 3 === 0 ? pal.spark : pal.ribbon, a); ctx.beginPath(); ctx.arc(x, y, k % 3 === 0 ? 2.1 : 1.4, 0, 6.283); ctx.fill();
      }
    }
  }

  function draw(now) {
    ctx.clearRect(0, 0, w, h);
    drawWaves(now); drawRibbons(now);
    ctx.lineWidth = 1;
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j++) {
        const b = nodes[j], dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy;
        if (d2 > linkDist * linkDist) continue;
        const k = 1 - Math.sqrt(d2) / linkDist;
        ctx.strokeStyle = rgba(pal.line, pal.lineA * k);
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
    }
    for (const n of nodes) {
      const c = n.warm ? pal.warm : pal.node, glow = n.glow;
      if (n.agent) {                                  // a few ring-shaped "agent" nodes
        ctx.fillStyle = rgba(c, .07 + glow * .1); ctx.beginPath(); ctx.arc(n.x, n.y, 12 + glow * 3, 0, 6.283); ctx.fill();   // soft halo
        ctx.strokeStyle = rgba(c, .38 + glow * .4); ctx.lineWidth = 1.2;
        ctx.beginPath(); ctx.arc(n.x, n.y, 5.5 + glow * 2, 0, 6.283); ctx.stroke();
        ctx.fillStyle = rgba(c, .5 + glow * .4);
        ctx.beginPath(); ctx.arc(n.x, n.y, 1.9, 0, 6.283); ctx.fill();
      } else {
        ctx.fillStyle = rgba(c, pal.nodeA * (.7 + n.r / 6) + glow * .35);
        ctx.beginPath(); ctx.arc(n.x, n.y, n.r + glow * 1.4, 0, 6.283); ctx.fill();
      }
    }
    for (let i = pulses.length - 1; i >= 0; i--) {   // data pulses: a soft dot with a short fading tail
      const p = pulses[i], u = (now - p.t0) / p.dur;
      if (u >= 1) { p.b.glow = 1; pulses.splice(i, 1); continue; }
      const e = u * u * (3 - 2 * u);
      for (let s = 0; s < 6; s++) {
        const q = Math.max(0, e - s * .035);
        const x = p.a.x + (p.b.x - p.a.x) * q, y = p.a.y + (p.b.y - p.a.y) * q;
        ctx.fillStyle = rgba(pal.pulse, (s === 0 ? .8 : .32 / (s + .5)) * Math.sin(Math.PI * Math.min(1, u * 1.02)));
        ctx.beginPath(); ctx.arc(x, y, s === 0 ? 2.2 : 1.6 - s * .15, 0, 6.283); ctx.fill();
      }
    }
  }

  function frame(now) {
    const dt = Math.min(48, now - (last || now)); last = now;
    if (now - themeCheck > 600) { readTheme(); themeCheck = now; }
    step(dt, now);
    if (now - lastSpawn > 520) { spawnPulse(now); lastSpawn = now; }
    draw(now);
    raf = requestAnimationFrame(frame);
  }

  let resizeTimer = 0;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { build(); readTheme(); if (reduce) draw(0); }, 150);
  });
  document.addEventListener('visibilitychange', () => {
    if (reduce) return;
    if (document.hidden) cancelAnimationFrame(raf); else { last = 0; raf = requestAnimationFrame(frame); }
  });

  readTheme(); build();
  if (reduce) draw(0); else raf = requestAnimationFrame(frame);
})();

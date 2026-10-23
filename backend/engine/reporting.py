"""Downloadable Negotiation Transcript (plain text) and Negotiation Report
(self-contained HTML that prints cleanly to PDF). Both are rendered purely from
the analytics dict + recorded state, using only the standard library."""
from html import escape as h
from datetime import datetime, timezone
from engine.analytics import money, PERSONALITY_LABELS

PLATFORM = 'AI Multi-Agent Negotiation Platform'
SOURCE_LABELS = {'llm': 'Live LLM', 'mock': 'Mock / rule-based engine', 'fallback': 'Rule-based fallback (LLM unavailable)', 'human': 'Human participant'}
PROVIDER_LABELS = {'groq': 'Groq', 'gemini': 'Gemini'}


def _source_label(source, state):
    if source == 'llm' and state.llm_provider:
        return f"{SOURCE_LABELS['llm']} · {PROVIDER_LABELS.get(state.llm_provider, state.llm_provider)}"
    return SOURCE_LABELS.get(source, source)
ACTION_LABELS = {'open': 'OPENING OFFER', 'counter': 'COUNTEROFFER', 'accept': 'ACCEPTED', 'reject': 'REJECTED', 'message': 'MESSAGE'}


def _ts(iso):
    try:
        return datetime.fromisoformat(iso).strftime('%Y-%m-%d %H:%M:%S UTC')
    except Exception:
        return iso or '—'


def _who(state, agent_id):
    a = next(x for x in state.agents if x.id == agent_id)
    tag = ' (You)' if state.workflow_mode == 'practice' and a.id == state.agents[0].id else ''
    return f'{a.role_label}{tag}'


def _mode_label(state):
    return 'Practice Mode (Human vs AI)' if state.workflow_mode == 'practice' else 'Simulation Mode (AI vs AI)'


def _private(e, unit='$'):
    if e.get('hard_limit') is None:
        return 'Opening / target / hard limit: confidential until the negotiation ends'
    return f'Opening value {money(e["opening_value"], unit)} · Target {money(e["target"], unit)} · Hard limit {money(e["hard_limit"], unit)}'


# ─────────────────────────────  TRANSCRIPT  ─────────────────────────────
def transcript_text(state, scenario, an):
    u = scenario.unit
    L = []
    add = L.append
    bar = '=' * 78
    add(bar); add(f'{PLATFORM.upper()} — NEGOTIATION TRANSCRIPT'); add(bar)
    add(f'Scenario        : {scenario.name}')
    add(f'Description     : {scenario.description}')
    add(f'Issue           : {scenario.issue_label} ({scenario.total_context})')
    add(f'Session ID      : {state.id}')
    add(f'Mode            : {_mode_label(state)}')
    add(f'Reasoning engine: {an["llm"]["engine_label"]}' + (f' — {an["llm"]["provider"]} / {an["llm"]["model"]}' if an['llm']['provider'] else ''))
    if an['llm']['notice']:
        add(f'Engine notice   : {an["llm"]["notice"]}')
    add(f'Started         : {_ts(state.started_at)}')
    add(f'Ended           : {_ts(state.completed_at) if state.completed_at else "still in progress"}')
    add(f'Rounds          : {an["rounds_used"]} of {an["max_rounds"]}')
    add('')
    add('PARTICIPANTS'); add('-' * 78)
    for i, e in enumerate(an['agents']):
        who = 'Human participant (you)' if e['controlled_by'] == 'human' else 'AI agent'
        add(f'Agent {"AB"[i]}: {e["role"]} — {who}')
        add(f'   Personality : {e["personality_label"]}')
        add(f'   Goal        : {e.get("goals", "—")}')
        add(f'   Constraint  : {e.get("constraints", "Confidential until the negotiation ends.")}')
        add(f'   Objective   : {e.get("objective", "—")}')
        add(f'   {_private(e, u)}')
    add('')
    add('TRANSCRIPT'); add('-' * 78)
    for block in an['timeline']:
        add(f'\n── Round {block["round"]} ' + '─' * 60)
        for x in block['entries']:
            who = _who(state, x['agent_id'])
            head = f'[{_ts(x["timestamp"])[11:19]}] {who} — {ACTION_LABELS[x["action"]]}'
            if x['value'] is not None:
                head += f': {money(x["value"], u)}'
            add(head)
            if x['stance']:
                add(f'    Stance     : {x["stance"]}')
            if x['move_kind']:
                mv = {'concession': 'concession', 'hold': 'held position', 'retreat': 'moved backwards'}[x['move_kind']]
                add(f'    Movement   : {mv} ({x["moved_by"]:+,.2f} = {x["move_pct"]}% of own range)')
            if x['message']:
                add(f'    Message    : {x["message"]}')
            if x['rationale'] and x['rationale'] != x['message']:
                add(f'    Reasoning  : {x["rationale"]}')
            add(f'    Source     : {_source_label(x["source"], state)}')
            if x['corrected']:
                add(f'    Orchestrator note: {x["correction_note"]}')
    add('')
    add('FINAL OUTCOME'); add('-' * 78)
    add(f'Status           : {an["status_label"]}')
    add(f'Final agreement  : {an["final_display"] or "None"}' + (f'  ({an["resolution_label"]})' if an['resolution_label'] else ''))
    add(f'Reason           : {an["outcome_reason"] or "—"}')
    dl = an['deadlock']
    if dl and dl.get('triggered'):
        add(f'Deadlock         : {dl["trigger"].replace("_", " ")} → {dl["resolution"]}')
        add(f'                   {dl["explanation"]}')
    add('')
    add('CONCESSION SUMMARY'); add('-' * 78)
    for e in an['agents']:
        add(f'{e["role"]:<22} moves={e["offers_made"]}  concessions={e["concession_count"]}  holds={e["hold_count"]}  retreats={e["retreat_count"]}  '
            f'total conceded={e["total_conceded_pct"]}% of range  satisfaction={e["satisfaction"] if e["satisfaction"] is not None else "n/a"}/100')
    add('')
    add(f'Generated by {PLATFORM}.')
    return '\n'.join(L) + '\n'


# ─────────────────────────────  REPORT (HTML)  ─────────────────────────────
def _svg_chart(state, an, unit):
    pts = [(p['index'], p['value'], aid) for aid, ser in an['series'].items() for p in ser]
    if not pts:
        return '<p class="muted">No offers were made.</p>'
    W, H, PL, PR, PT, PB = 720, 280, 74, 24, 24, 40
    ys = [v for _, v, _ in pts] + ([an['final_value']] if an['final_value'] is not None else [])
    lo, hi = min(ys), max(ys)
    pad = (hi - lo) * .12 or 1
    lo, hi = lo - pad, hi + pad
    n = max(i for i, _, _ in pts) + 1
    X = lambda i: PL + (W - PL - PR) * (i / max(n - 1, 1))
    Y = lambda v: PT + (H - PT - PB) * (1 - (v - lo) / (hi - lo))
    colors = ['#7c5a47', '#5d806a']
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Offer movement chart" xmlns="http://www.w3.org/2000/svg">']
    for k in range(5):
        v = lo + (hi - lo) * k / 4
        out.append(f'<line x1="{PL}" x2="{W-PR}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="#d5c7ba" stroke-width="1"/>'
                   f'<text x="{PL-8}" y="{Y(v)+4:.1f}" font-size="11" text-anchor="end" fill="#655b54">{h(money(v, unit))}</text>')
    for ci, a in enumerate(state.agents):
        ser = an['series'][a.id]
        if not ser:
            continue
        path = ' '.join(f'{X(p["index"]):.1f},{Y(p["value"]):.1f}' for p in ser)
        out.append(f'<polyline fill="none" stroke="{colors[ci]}" stroke-width="2.5" points="{path}"/>')
        for p in ser:
            out.append(f'<circle cx="{X(p["index"]):.1f}" cy="{Y(p["value"]):.1f}" r="4" fill="{colors[ci]}"><title>{h(a.role_label)} R{p["round"]}: {h(money(p["value"], unit))}</title></circle>')
    if an['final_value'] is not None:
        out.append(f'<line x1="{PL}" x2="{W-PR}" y1="{Y(an["final_value"]):.1f}" y2="{Y(an["final_value"]):.1f}" stroke="#a67f66" stroke-dasharray="5 4"/>'
                   f'<text x="{PL+8}" y="{Y(an["final_value"])-6:.1f}" font-size="11" text-anchor="start" fill="#7c5a47">Final {h(money(an["final_value"], unit))}</text>')
    out.append(f'<text x="{PL}" y="{H-12}" font-size="11" fill="#655b54">Offers in order of play →</text>')
    out.append('</svg>')
    legend = ''.join(f'<span class="lg"><i style="background:{colors[i]}"></i>{h(a.role_label)}</span>' for i, a in enumerate(state.agents))
    return f'<div class="legend">{legend}</div>' + ''.join(out)


CSS = """
:root{--bg:#f4efe9;--card:#fffaf5;--line:#d5c7ba;--ink:#29231f;--muted:#655b54;--accent:#7c5a47;--green:#5d806a;--red:#a65e59;--amber:#9a7748}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 Inter,ui-sans-serif,system-ui,'Segoe UI',sans-serif}
.page{max-width:980px;margin:0 auto;padding:40px 24px 80px}
header.top{border-bottom:2px solid var(--accent);padding-bottom:18px;margin-bottom:26px}
.eyebrow{font-size:11px;letter-spacing:.17em;text-transform:uppercase;color:var(--accent);font-weight:700}
h1{font-family:Georgia,serif;font-size:32px;margin:6px 0 4px;letter-spacing:-.02em}h2{font-family:Georgia,serif;font-size:21px;margin:34px 0 12px;border-bottom:1px solid var(--line);padding-bottom:6px}
.muted{color:var(--muted)}.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px;margin:12px 0;break-inside:avoid}
table{width:100%;border-collapse:collapse;font-size:13.5px}th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}th{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}.stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 14px}.stat label{display:block;font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--muted)}.stat b{font-size:22px;font-family:Georgia,serif}
.pill{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:700;background:#efe6dc;color:var(--accent)}.pill.agreed{background:#e2eee6;color:var(--green)}.pill.rejected,.pill.deadlock{background:#f3dfdd;color:var(--red)}.pill.max_rounds_reached,.pill.in_progress{background:#f3ead8;color:var(--amber)}
.bar{height:10px;background:#e8ded4;border-radius:99px;overflow:hidden}.bar span{display:block;height:100%;background:var(--accent)}
.legend{display:flex;gap:16px;margin-bottom:6px;font-size:13px}.lg i{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
ul.ins{padding-left:20px}ul.ins li{margin:6px 0}pre.tx{white-space:pre-wrap;font:12px/1.5 ui-monospace,Menlo,Consolas,monospace;background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px}
footer{margin-top:40px;font-size:12px;color:var(--muted);text-align:center}
@media print{body{background:#fff}.page{padding:0}details{display:block}details>summary{display:none}}
"""


def report_html(state, scenario, an):
    u = scenario.unit
    e0, e1 = an['agents']
    rows = []
    for e in an['agents']:
        rows.append(f'<tr><td><b>{h(e["role"])}</b><br><span class="muted">{"Human participant" if e["controlled_by"] == "human" else "AI agent"}</span></td>'
                    f'<td>{h(e["personality_label"])}</td><td>{h(e.get("goals", "—"))}</td><td>{h(e.get("constraints", "Confidential until the negotiation ends."))}</td>'
                    f'<td>{h(e.get("objective", "—"))}<br><span class="muted">{h(_private(e, u))}</span></td></tr>')
    participants = ('<table><thead><tr><th>Role</th><th>Personality</th><th>Goal</th><th>Constraint</th><th>Objective &amp; positions</th></tr></thead><tbody>'
                    + ''.join(rows) + '</tbody></table>')

    tl = []
    for blk in an['timeline']:
        for x in blk['entries']:
            mv = ''
            if x['move_kind']:
                mv = f'{ {"concession": "Concession", "hold": "Held", "retreat": "Backward"}[x["move_kind"]] } ({x["moved_by"]:+,.2f} · {x["move_pct"]}%)'
            text = ' — '.join(t for t in (x['message'], x['rationale'] if x['rationale'] != x['message'] else None) if t)
            tl.append(f'<tr><td>{blk["round"]}</td><td>{h(_who(state, x["agent_id"]))}</td><td>{h(ACTION_LABELS[x["action"]].title())}</td>'
                      f'<td>{h(money(x["value"], u)) if x["value"] is not None else "—"}</td><td>{h(mv) or "—"}</td><td>{h(x["stance"] or "—")}</td>'
                      f'<td>{h(text)}<br><span class="muted">{h(_source_label(x["source"], state))}</span></td></tr>')
    timeline = ('<table><thead><tr><th>Round</th><th>Participant</th><th>Action</th><th>Value</th><th>Movement</th><th>Stance</th><th>Reasoning / message</th></tr></thead><tbody>'
                + ''.join(tl) + '</tbody></table>') if tl else '<p class="muted">No turns were taken.</p>'

    conc = ''.join(f'<tr><td><b>{h(e["role"])}</b></td><td>{e["offers_made"]}</td><td>{e["concession_count"]}</td><td>{e["hold_count"]}</td><td>{e["retreat_count"]}</td>'
                   f'<td>{e["total_conceded_pct"]}%</td><td>{e["avg_step_pct"]}%</td><td>{e["largest_step_pct"]}%</td></tr>' for e in an['agents'])
    conc_table = ('<table><thead><tr><th>Participant</th><th>Offers</th><th>Concessions</th><th>Holds</th><th>Retreats</th><th>Total conceded</th><th>Avg. step</th><th>Largest step</th></tr></thead><tbody>'
                  + conc + '</tbody></table>')

    perf = ''
    for e in an['agents']:
        s = e['satisfaction']
        perf += (f'<div class="card"><b>{h(e["role"])}</b> <span class="muted">· {h(e["personality_label"])} · {"you" if e["controlled_by"] == "human" else "AI"}</span>'
                 f'<div style="margin:10px 0 4px">Objective satisfaction: <b>{"n/a" if s is None else f"{s}/100"}</b>'
                 + ('' if e['target_met'] is None else f' &nbsp;·&nbsp; target {"met" if e["target_met"] else "not met"}') + '</div>'
                 f'<div class="bar"><span style="width:{s or 0}%"></span></div>'
                 f'<div class="muted" style="margin-top:8px">Final position {h(money(e["final_position"], u))} · behaviour: {h(e["observed_behavior"])}</div></div>')
    if an['joint']:
        perf += f'<p class="muted">Average satisfaction {an["joint"]["average_satisfaction"]}/100 · balance {an["joint"]["balance"]}/100.</p>'

    dl = an['deadlock']
    if dl and dl.get('triggered'):
        deadlock = (f'<div class="card"><b>{h(dl["trigger"].replace("_", " ").title())}</b> → {h(dl["resolution"].title())}<br>{h(dl["explanation"])}'
                    f'<br><span class="muted">Detected in round {dl["round"]} after {dl["stalled_rounds"]} stalled round(s).</span></div>')
    else:
        deadlock = '<p class="muted">No deadlock was detected in this negotiation.</p>'

    llm = an['llm']
    engine = (f'<div class="card"><b>{h(llm["engine_label"])}</b><br>'
              + (f'Provider {h(PROVIDER_LABELS.get(llm["provider"], str(llm["provider"])))} · model {h(str(llm["model"]))} · ' if llm['provider'] else '')
              + f'{llm["llm_calls"]} LLM call(s) · {llm["fallback_turns"]} fallback turn(s) · {llm["ai_turns"]} AI turn(s)'
              + (f'<br><span class="muted">{h(llm["notice"])}</span>' if llm['notice'] else '') + '</div>')

    s = an['status']
    agreement = (f'<div class="grid"><div class="stat"><label>Status</label><span class="pill {s}">{h(an["status_label"])}</span></div>'
                 f'<div class="stat"><label>Agreed {h(scenario.issue_label)}</label><b>{h(an["final_display"] or "—")}</b></div>'
                 f'<div class="stat"><label>Rounds</label><b>{an["rounds_used"]}/{an["max_rounds"]}</b></div>'
                 f'<div class="stat"><label>Resolution</label><b style="font-size:15px">{h(an["resolution_label"] or "—")}</b></div></div>'
                 f'<p>{h(an["outcome_reason"] or "The negotiation is still in progress.")}</p>')
    ev = an['events']
    summary = (f'<div class="grid"><div class="stat"><label>Total turns</label><b>{ev["total_turns"]}</b></div><div class="stat"><label>Openings</label><b>{ev["openings"]}</b></div>'
               f'<div class="stat"><label>Counteroffers</label><b>{ev["counteroffers"]}</b></div><div class="stat"><label>Accepts / Rejects</label><b>{ev["accepts"]} / {ev["rejects"]}</b></div>'
               f'<div class="stat"><label>Messages</label><b>{ev["messages"]}</b></div><div class="stat"><label>Corrections</label><b>{ev["corrections"]}</b></div></div>')
    insights = '<ul class="ins">' + ''.join(f'<li>{h(t)}</li>' for t in an['insights']) + '</ul>'
    tx = transcript_text(state, scenario, an)
    partial = '' if an['terminal'] else '<div class="card"><b>Partial report.</b> This negotiation is still in progress; the report reflects the state at download time.</div>'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Negotiation Report — {h(scenario.name)}</title><style>{CSS}</style></head><body><div class="page">
<header class="top"><div class="eyebrow">{PLATFORM}</div><h1>Negotiation Report</h1><div class="muted">{h(scenario.name)} · {h(_mode_label(state))} · Session {h(state.id)} · Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</div></header>{partial}
<h2>1. Scenario information</h2><div class="card"><b>{h(scenario.name)}</b><br>{h(scenario.description)}<br><span class="muted">Issue: {h(scenario.issue_label)} · {h(scenario.total_context)} · Started {h(_ts(state.started_at))} · Ended {h(_ts(state.completed_at)) if state.completed_at else 'in progress'}</span></div>
<h2>2. Participants, roles, goals, constraints &amp; personalities</h2>{participants}
<h2>3. Negotiation summary</h2>{summary}
<h2>4. Final outcome &amp; agreement terms</h2>{agreement}
<h2>5. Offer movement</h2><div class="card">{_svg_chart(state, an, u)}</div>
<h2>6. Round-by-round timeline (offers, counteroffers, decisions)</h2>{timeline}
<h2>7. Concessions</h2>{conc_table}
<h2>8. Agent performance &amp; objective satisfaction</h2>{perf}
<h2>9. Deadlock information</h2>{deadlock}
<h2>10. Negotiation insights</h2>{insights}
<h2>11. Reasoning engine</h2>{engine}
<h2>12. Full transcript</h2><details open><summary>Show transcript</summary><pre class="tx">{h(tx)}</pre></details>
<footer>Generated by {PLATFORM}. All figures are derived from the recorded negotiation state.</footer></div></body></html>"""


# ─────────────────────────────  CERTIFICATE  ─────────────────────────────
CERT_CSS = """
:root{--ink:#29231f;--muted:#655b54;--accent:#7c5a47;--line:#c9a876;--paper:#fffdf7}
*{box-sizing:border-box}body{margin:0;background:#e9e2d6;font-family:Georgia,'Times New Roman',serif;color:var(--ink)}
.sheet{width:900px;max-width:96vw;margin:34px auto;background:var(--paper);border:2px solid var(--line);border-radius:4px;position:relative;padding:56px 64px;box-shadow:0 24px 60px rgba(60,44,28,.22)}
.sheet::before{content:"";position:absolute;inset:12px;border:1px solid var(--line);pointer-events:none}
.eyebrow{text-align:center;font-family:Inter,sans-serif;font-size:11px;letter-spacing:.28em;text-transform:uppercase;color:var(--accent);font-weight:700}
h1{text-align:center;font-size:34px;margin:10px 0 2px;letter-spacing:.02em}
.sub{text-align:center;color:var(--muted);font-size:13px;margin:0 0 26px}
.divider{width:120px;height:2px;background:var(--accent);margin:0 auto 26px}
.grant{text-align:center;font-size:15px;line-height:1.8;margin:0 0 22px}
.grant b{font-size:19px}
.terms{display:flex;justify-content:center;gap:46px;margin:26px 0;font-family:Inter,sans-serif}
.terms div{text-align:center}
.terms label{display:block;font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.terms b{font-size:26px;color:var(--accent)}
table.parties{width:100%;border-collapse:collapse;margin:26px 0;font-family:Inter,sans-serif;font-size:12.5px}
table.parties th{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
table.parties td{padding:8px;border-bottom:1px solid #ece2d2}
.seal{width:96px;height:96px;border-radius:50%;border:3px double var(--accent);display:grid;place-items:center;margin:0 auto 10px;font-family:Inter,sans-serif;font-weight:800;font-size:11px;letter-spacing:.06em;color:var(--accent);text-align:center;line-height:1.3}
.foot{display:flex;justify-content:space-between;align-items:flex-end;margin-top:34px;font-family:Inter,sans-serif;font-size:11px;color:var(--muted)}
.foot .sig{border-top:1px solid var(--ink);padding-top:6px;width:220px;text-align:center}
.code{font-family:ui-monospace,Menlo,Consolas,monospace;letter-spacing:.05em}
@media print{body{background:#fff}.sheet{box-shadow:none;margin:0;border:none}.sheet::before{display:none}}
"""


def certificate_html(state, scenario, an):
    u = scenario.unit
    agreed = an['status'] == 'agreed'
    verdict = 'Agreement Certified' if agreed else {'rejected': 'Negotiation Concluded — No Agreement', 'deadlock': 'Negotiation Concluded — Deadlock',
              'max_rounds_reached': 'Negotiation Concluded — Round Limit Reached'}.get(an['status'], 'Negotiation Concluded')
    parties = ''.join(f'<tr><td><b>{h(e["role"])}</b>{" (Human participant)" if e["controlled_by"]=="human" else ""}</td><td>{h(e["personality_label"])}</td>'
                      f'<td>{h(money(e.get("final_position") if not agreed else an["final_value"], u)) if e.get("final_position") is not None or agreed else "—"}</td>'
                      f'<td>{"n/a" if e["satisfaction"] is None else f"{e['satisfaction']}/100"}</td></tr>' for e in an['agents'])
    terms = (f'<div class="terms"><div><label>Agreed {h(scenario.issue_label)}</label><b>{h(an["final_display"])}</b></div>'
             f'<div><label>Rounds</label><b>{an["rounds_used"]}/{an["max_rounds"]}</b></div>'
             f'<div><label>Resolution</label><b style="font-size:15px">{h(an["resolution_label"] or "—")}</b></div></div>') if agreed else \
            (f'<div class="terms"><div><label>Rounds elapsed</label><b>{an["rounds_used"]}/{an["max_rounds"]}</b></div>'
             f'<div><label>Status</label><b style="font-size:16px">{h(an["status_label"])}</b></div></div>')
    grant = (f'This certifies that <b>{h(an["agents"][0]["role"])}</b> and <b>{h(an["agents"][1]["role"])}</b> conducted a negotiation over '
             f'<b>{h(scenario.issue_label)}</b> under the {PLATFORM}, and reached a final agreement at <b>{h(an["final_display"])}</b>.') if agreed else \
            (f'This certifies that <b>{h(an["agents"][0]["role"])}</b> and <b>{h(an["agents"][1]["role"])}</b> conducted a negotiation over '
             f'<b>{h(scenario.issue_label)}</b> under the {PLATFORM}, which concluded without a final agreement.')
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Negotiation Certificate — {h(scenario.name)}</title><style>{CERT_CSS}</style></head><body><div class="sheet">
<div class="eyebrow">{PLATFORM}</div><h1>Certificate of Negotiation</h1><div class="sub">{h(scenario.name)} · {h(_mode_label(state))} · {h(verdict)}</div><div class="divider"></div>
<div class="seal">{h(PLATFORM.split()[0])}<br>{"VERIFIED" if agreed else "RECORD"}</div>
<p class="grant">{grant}</p>
{terms}
<table class="parties"><thead><tr><th>Participant</th><th>Personality</th><th>Final position</th><th>Satisfaction</th></tr></thead><tbody>{parties}</tbody></table>
<div class="foot"><div>Session <span class="code">{h(state.id)}</span><br>Issued {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</div>
<div class="sig">Orchestrator-Verified Outcome</div></div>
</div></body></html>"""

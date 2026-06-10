# Brut Chat Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A fixed, always-on right-side chat panel (30% width) in the cockpit, in the rounded near-black Brut language, where every agent reply arrives as structured blocks (data rows + actionable buttons) via a new presenter layer — never lumps of text.

**Architecture:** Backend: a `presenter` module turns any reply dict into a `blocks[]` contract; `/api/saakshe/ask` adds `blocks` to its response (backward compatible — `text` stays). Frontend: a self-contained `web/chat-panel.js` + CSS injected into `cockpit.html`, rendering blocks (text / data / actions / slider / progress) with the validated animations from the atlas demo. The kalai media flow (quote → slider re-quote → render → receipt → approve) is the first fully-wired block conversation.

**Tech Stack:** vanilla JS (no framework — matches existing cockpit), FastAPI, existing `/api/saakshe/ask` + new `/api/kalai/media/*` endpoints (from the media-crew plan — that plan ships FIRST).

**Dependency:** Requires `2026-06-10-kalai-media-crew.md` Tasks 1–4 deployed.

---

## File map

| File | Responsibility |
|---|---|
| Create `service/presenter.py` | reply dict → blocks[] contract; media intents → action blocks |
| Create `common/tests/test_presenter.py` if presenter lands in common — NO: service has no tests dir; create `tests/test_presenter.py` (repo-root, per existing layout) |
| Create `web/chat-panel.js` | the panel: feed, tabs, block renderer, media flow wiring |
| Create `web/chat-panel.css` | rounded near-black Brut tokens + grain + animations |
| Modify `web/cockpit.html` | mount `<div id="sa-chatpane">`, include the two files, grid 70/30 |
| Modify `service/app.py:455-473` | `ask()` returns `blocks` alongside `text` |

## The blocks contract (one place, documented in presenter.py)

```json
{"blocks": [
  {"t": "text",    "who": "kalai/router", "md": "Two paths fit."},
  {"t": "data",    "rows": [["A · generate (Veo 8s)", "$3.20 ✗"], ["B · compute", "$0.05 ✓"]]},
  {"t": "actions", "items": [{"label": "PATH B — COMPUTE", "kind": "primary",
                               "action": "media.quote", "args": {"path": "B"}}]},
  {"t": "slider",  "action": "media.requote", "min": 1, "max": 8, "value": 4,
                    "quote": {"total_usd": 0.027, "est_wall_sec": 58}},
  {"t": "progress","job_id": "abc123"},
  {"t": "receipt", "rows": [["cpu", "$0.021"], ["total", "$0.021 of $1.00"]],
                    "verify": {"ok": true, "hdr_format": "HLG BT.2020 10-bit"}}
]}
```

---

### Task 1: presenter — replies become blocks

**Files:**
- Create: `service/presenter.py`
- Test: `tests/test_presenter.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_presenter.py
from service import presenter

def test_witness_reply_becomes_text_block():
    blocks = presenter.to_blocks({"kind": "witness", "text": "hello", "pills": ["a", "b"]})
    assert blocks[0] == {"t": "text", "who": "saakshe/witness", "md": "hello"}
    assert {"t": "actions"} .items() <= blocks[1].items() or blocks[1]["t"] == "data"

def test_media_intent_detected():
    assert presenter.media_intent("make my image an hdr video, budget $1") == {
        "is_media": True, "budget_usd": 1.0, "wants_hdr": True}
    assert presenter.media_intent("what changed yesterday?")["is_media"] is False

def test_quote_becomes_blocks():
    q = {"path": "B", "seconds": 4, "total_usd": 0.027, "budget_usd": 1.0,
         "fits_budget": True, "est_wall_sec": 58, "rationale": "source exists",
         "lines": [{"item": "render_cpu", "usd": 0.027}]}
    blocks = presenter.quote_blocks(q)
    kinds = [b["t"] for b in blocks]
    assert kinds == ["text", "data", "slider", "actions"]
    assert blocks[2]["max"] == 8

def test_refusal_blocks_show_counter_offer():
    q = {"path": "B", "seconds": 8, "total_usd": 0.07, "budget_usd": 0.01,
         "fits_budget": False, "est_wall_sec": 100, "rationale": "r",
         "lines": [], "counter_offer": {"seconds": 1, "total_usd": 0.009}}
    blocks = presenter.quote_blocks(q)
    labels = [i["label"] for b in blocks if b["t"] == "actions" for i in b["items"]]
    assert any("1s" in l for l in labels)   # the counter-offer button
```

- [ ] **Step 2: Run to verify failure** — ImportError.

- [ ] **Step 3: Implement `service/presenter.py`**

```python
"""saakshe — the presenter seat. Formats, never authors.

Any faculty's raw reply becomes a `blocks[]` list the chat panel renders as
data rows + actionable buttons. Words pass through untouched (kural's rule:
format is not authorship).
"""
from __future__ import annotations
import re

def media_intent(text: str) -> dict:
    low = text.lower()
    is_media = any(w in low for w in ("hdr", "video", "reel", "animate", "motion"))
    m = re.search(r"\$\s*(\d+(?:\.\d+)?)", low)
    return {"is_media": is_media,
            "budget_usd": float(m.group(1)) if m else 1.0,
            "wants_hdr": "hdr" in low}

def to_blocks(reply: dict) -> list[dict]:
    blocks = [{"t": "text", "who": "saakshe/witness", "md": reply.get("text", "")}]
    pills = reply.get("pills") or []
    if pills:
        blocks.append({"t": "data", "rows": [[p, ""] for p in pills]})
    return blocks

def quote_blocks(q: dict) -> list[dict]:
    rows = [[l["item"].replace("_", " "), f"${l['usd']:.3f}"] for l in q["lines"]]
    rows.append(["total", f"${q['total_usd']:.3f} of ${q['budget_usd']:.2f}"])
    blocks = [
        {"t": "text", "who": "kalai/router",
         "md": f"Path {q['path']} — {q['rationale']}."},
        {"t": "data", "rows": rows},
        {"t": "slider", "action": "media.requote", "min": 1, "max": 8,
         "value": q["seconds"],
         "quote": {"total_usd": q["total_usd"], "est_wall_sec": q["est_wall_sec"]}},
    ]
    if q["fits_budget"]:
        items = [{"label": "RENDER", "kind": "primary", "action": "media.render",
                  "args": {"seconds": q["seconds"]}},
                 {"label": "PICK FX (12)", "kind": "plain", "action": "media.fxmenu",
                  "args": {}}]
    else:
        items = [{"label": "OVER BUDGET", "kind": "blocked", "action": "noop", "args": {}}]
        co = q.get("counter_offer")
        if co:
            items.append({"label": f"FITS: {co['seconds']}s · ${co['total_usd']:.3f}",
                          "kind": "primary", "action": "media.requote",
                          "args": {"seconds": co["seconds"]}})
    blocks.append({"t": "actions", "items": items})
    return blocks

def receipt_blocks(job: dict) -> list[dict]:
    r, v = job["receipt"], job["verify"]
    return [
        {"t": "text", "who": "kalai/verifier",
         "md": f"done — {v['hdr_format']}." if v["ok"] else "render finished but HDR verification FAILED — not shipping."},
        {"t": "receipt",
         "rows": [["estimated", f"${r['estimated_usd']:.3f}"],
                  ["cpu", f"{r['measured_vcpu_sec']} vCPU-s · ${r['cpu_usd']:.3f}"],
                  ["vertex", f"${r['vertex_usd']:.3f}"],
                  ["total", f"${r['total_usd']:.3f}"]],
         "verify": v},
        {"t": "actions", "items": (
            [{"label": "VIEW HDR", "kind": "primary", "action": "media.view", "args": {}},
             {"label": "DISCARD", "kind": "no", "action": "media.discard", "args": {}}]
            if v["ok"] else
            [{"label": "RETRY", "kind": "primary", "action": "media.render", "args": {}}])},
    ]
```

- [ ] **Step 4: Run tests** — 4 passed.
- [ ] **Step 5: Commit** — `git commit -m "feat(service): presenter — replies become actionable blocks"`

---

### Task 2: ask() returns blocks (+ media intent routes to quote)

**Files:**
- Modify: `service/app.py` `ask()` (line ~455)
- Test: extend `tests/test_presenter.py`

- [ ] **Step 1: Add the failing test**

```python
# append to tests/test_presenter.py
from fastapi.testclient import TestClient
from service.app import app
client = TestClient(app)

def test_ask_returns_blocks():
    r = client.post("/api/saakshe/ask", json={"text": "hello there"})
    assert "blocks" in r.json()

def test_ask_media_question_returns_quote_blocks():
    r = client.post("/api/saakshe/ask",
                    json={"text": "make my image an HDR video, budget $1"})
    d = r.json()
    assert d["kind"] == "media_quote"
    assert any(b["t"] == "slider" for b in d["blocks"])
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Modify `ask()`** — insert before the decision-hints check:

```python
    from service import presenter
    mi = presenter.media_intent(text)
    if mi["is_media"]:
        q = media_crew.quote(seconds=4, budget_usd=mi["budget_usd"],
                             has_source_image=True, wants_hdr=mi["wants_hdr"])
        return {"kind": "media_quote", "quote": q,
                "blocks": presenter.quote_blocks(q)}
```

and change the final return to:

```python
    reply = await witness.respond(text, req.run_id, sess.stream)
    return {"kind": "witness", **reply, "blocks": presenter.to_blocks(reply)}
```

- [ ] **Step 4: Run tests** — all pass (existing ask tests too: run full `tests/` dir).
- [ ] **Step 5: Commit** — `git commit -m "feat(service): ask() speaks blocks; media questions quote immediately"`

---

### Task 3: chat-panel.css — the rounded near-black Brut skin

**Files:**
- Create: `web/chat-panel.css`

- [ ] **Step 1:** Port the validated styles from `~/Desktop/Working/_reports/2026-06-10_agent-atlas-chat-panel.html` (the `.chatpane`/`.msg`/`.acts`/`.sld`/`.typing` rules and keyframes, plus the grain `body::after` and tokens `--ink:#141118; --grad:linear-gradient(135deg,#141118,#241c2e 70%,#3a2a4a)`) into `web/chat-panel.css`, all selectors prefixed `#sa-chatpane` so cockpit styles are untouched. Same animation timings (slidein .28s cubic-bezier(.2,.9,.3,1.2), pulse 1.6s, bnc 1s).
- [ ] **Step 2:** Commit — `git commit -m "feat(web): chat panel Brut skin — near-black, rounded, grain"`

---

### Task 4: chat-panel.js — block renderer + media flow

**Files:**
- Create: `web/chat-panel.js`

- [ ] **Step 1: Implement.** Core (complete file skeleton — fill nothing later):

```javascript
/* saakshe chat panel — always-on right pane. Renders presenter blocks. */
(function () {
  const pane = document.getElementById('sa-chatpane');
  pane.innerHTML = `
    <div class="ch-head"><span class="brand">SΛΛKSHE</span>
      <span class="t">· COMPANY CHAT</span><span class="live"></span></div>
    <div class="ch-tabs">
      <span class="ch-tab on" data-q="saakshe">saakshe</span>
      <span class="ch-tab" data-q="manas">● manas</span>
      <span class="ch-tab" data-q="arivu">◆ arivu</span>
      <span class="ch-tab" data-q="kalai">▲ kalai</span>
      <span class="ch-tab" data-q="kural">■ kural</span></div>
    <div class="ch-feed" id="ch-feed"></div>
    <div class="ch-input"><input id="ch-inp" placeholder="ask saakshe…">
      <button id="ch-send">→</button></div>`;
  const feed = document.getElementById('ch-feed');
  const state = { budget: 1.0, seconds: 4, fx: 'sat_sort', image: null, job: null };

  const el = h => { const d = document.createElement('div'); d.innerHTML = h; return d.firstElementChild; };
  const down = () => { feed.scrollTop = feed.scrollHeight; };
  const esc = s => s.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

  function msg(who, inner, user) {
    const m = el(`<div class="msg${user ? ' user' : ''}">
      <div class="who">${esc(who)}</div></div>`);
    if (typeof inner === 'string') m.appendChild(el(`<p>${inner}</p>`));
    else inner.forEach(n => m.appendChild(n));
    feed.appendChild(m); down(); return m;
  }

  function typing(cb, ms = 700) {
    const t = el('<div class="typing"><span></span><span></span><span></span></div>');
    feed.appendChild(t); down();
    setTimeout(() => { t.remove(); cb(); down(); }, ms);
  }

  function renderBlocks(blocks) {
    blocks.forEach(b => {
      if (b.t === 'text') msg(b.who.toUpperCase(), esc(b.md));
      else if (b.t === 'data' || b.t === 'receipt') {
        const rows = b.rows.map(r => `<div class="row"><span>${esc(r[0])}</span><b>${esc(r[1])}</b></div>`).join('');
        feed.lastElementChild.appendChild(el(`<div class="data">${rows}</div>`));
        if (b.verify) feed.lastElementChild.appendChild(
          el(`<div class="data"><div class="row"><span>verify</span><b>${b.verify.ok ? '✓ ' + esc(b.verify.hdr_format) : '✗ FAILED'}</b></div></div>`));
      }
      else if (b.t === 'actions') {
        const btns = b.items.map((i, n) =>
          `<button class="act ${i.kind}" data-action="${i.action}" data-args='${JSON.stringify(i.args)}'>${esc(i.label)}</button>`).join('');
        feed.lastElementChild.appendChild(el(`<div class="acts">${btns}</div>`));
      }
      else if (b.t === 'slider') {
        const s = el(`<div class="sld"><div class="lab"><span>DURATION</span><span class="dv">${b.value}s</span></div>
          <input type="range" min="${b.min}" max="${b.max}" value="${b.value}">
          <div class="quote"><span>est. cost</span><b class="qc">$${b.quote.total_usd.toFixed(3)}</b></div>
          <div class="quote"><span>est. render</span><b class="qt">~${b.quote.est_wall_sec}s</b></div></div>`);
        s.querySelector('input').oninput = async e => {
          state.seconds = +e.target.value;
          s.querySelector('.dv').textContent = state.seconds + 's';
          const q = await api('/api/kalai/media/quote',
            { seconds: state.seconds, budget_usd: state.budget, has_source_image: true });
          s.querySelector('.qc').textContent = '$' + q.total_usd.toFixed(3);
          s.querySelector('.qt').textContent = '~' + q.est_wall_sec + 's';
        };
        feed.lastElementChild.appendChild(s);
      }
      else if (b.t === 'progress') pollJob(b.job_id);
    });
    down();
  }

  async function api(url, body) {
    const r = await fetch(url, { method: 'POST',
      headers: (window.SA_HEADERS || Object)({ 'content-type': 'application/json' }),
      body: JSON.stringify(body) });
    return r.json();
  }

  feed.addEventListener('click', async e => {
    const b = e.target.closest('.act'); if (!b || b.classList.contains('done')) return;
    b.closest('.acts').querySelectorAll('.act').forEach(x => x.classList.add('done'));
    const action = b.dataset.action, args = JSON.parse(b.dataset.args || '{}');
    if (action === 'media.render') startRender();
    else if (action === 'media.requote') { state.seconds = args.seconds || state.seconds; askMedia(); }
    else if (action === 'media.fxmenu') fxMenu();
    else if (action === 'media.view' && state.job) window.open('/api/kalai/media/file/' + state.job);
  });

  function fxMenu() {
    const FX = ['sat_sort','dark_sort','vert_sort','hue_sort','ripple','wave',
                'light_sweep','charcoal','lith','sabattier','cinestill','ca_pulse'];
    typing(() => {
      const m = msg('▲ KALAI · FX-PICKER', 'pick the effect:');
      m.appendChild(el('<div class="acts">' + FX.map(f =>
        `<button class="act ${f === 'sat_sort' ? 'ok' : 'plain'}" data-action="media.fx" data-args='{"fx":"${f}"}'>${f.replace('_',' ').toUpperCase()}</button>`).join('') + '</div>'));
      m.querySelectorAll('[data-action="media.fx"]').forEach(x => x.onclick = () => {
        state.fx = JSON.parse(x.dataset.args).fx; startRender();
      });
    });
  }

  async function startRender() {
    if (!state.image) {  // ask for an image if none picked yet
      const m = msg('▲ KALAI · PRODUCER', 'drop the source image:');
      const inp = el('<input type="file" accept="image/*" style="margin-top:8px">');
      inp.onchange = () => { state.image = inp.files[0]; startRender(); };
      m.appendChild(inp); return;
    }
    const fd = new FormData();
    fd.append('image', state.image);
    fd.append('fx', state.fx); fd.append('seconds', state.seconds);
    fd.append('budget_usd', state.budget);
    const r = await fetch('/api/kalai/media/render',
      { method: 'POST', headers: (window.SA_HEADERS || Object)({}), body: fd });
    const d = await r.json();
    if (d.job_id) { state.job = d.job_id; pollJob(d.job_id); }
    else msg('▲ KALAI · ROUTER', esc(d.error || 'refused'));
  }

  function pollJob(jid) {
    const m = msg('▲ KALAI · RENDERER', 'frame 0 · starting…');
    const p = m.querySelector('p');
    const iv = setInterval(async () => {
      const s = await (await fetch('/api/kalai/media/job/' + jid,
        { headers: (window.SA_HEADERS || Object)({}) })).json();
      if (s.status === 'rendering') p.textContent = `frame ${s.frame}/${s.frames} · rendering…`;
      else {
        clearInterval(iv);
        if (s.status === 'done') renderBlocks(s.blocks || fallbackReceipt(s));
        else p.textContent = 'error: ' + (s.error || 'unknown');
      }
      down();
    }, 1500);
  }
  function fallbackReceipt(s) {
    return [{ t: 'text', who: 'kalai/verifier',
              md: s.verify.ok ? 'done — ' + s.verify.hdr_format : 'HDR verify FAILED' },
            { t: 'receipt', rows: [['total', '$' + s.receipt.total_usd]], verify: s.verify },
            { t: 'actions', items: [{ label: 'VIEW HDR', kind: 'primary', action: 'media.view', args: {} }] }];
  }

  async function askMedia() {
    const q = await api('/api/kalai/media/quote',
      { seconds: state.seconds, budget_usd: state.budget, has_source_image: true });
    typing(() => renderBlocks([
      { t: 'text', who: 'kalai/pricer', md: 'requoted.' },
      { t: 'slider', action: 'media.requote', min: 1, max: 8, value: q.seconds,
        quote: { total_usd: q.total_usd, est_wall_sec: q.est_wall_sec } },
      { t: 'actions', items: [{ label: 'RENDER', kind: 'primary', action: 'media.render', args: {} },
                              { label: 'PICK FX (12)', kind: 'plain', action: 'media.fxmenu', args: {} }] }]));
  }

  async function send() {
    const i = document.getElementById('ch-inp');
    const text = i.value.trim(); if (!text) return;
    msg('YOU', esc(text), true); i.value = '';
    const m = text.match(/\$\s*(\d+(?:\.\d+)?)/); if (m) state.budget = +m[1];
    typing(async () => {
      const d = await api('/api/saakshe/ask', { text });
      renderBlocks(d.blocks || [{ t: 'text', who: 'saakshe', md: d.text || '…' }]);
    });
  }
  document.getElementById('ch-send').onclick = send;
  document.getElementById('ch-inp').addEventListener('keydown', e => { if (e.key === 'Enter') send(); });
  document.querySelectorAll('.ch-tab').forEach(t => t.onclick = () => {
    document.querySelectorAll('.ch-tab').forEach(x => x.classList.remove('on'));
    t.classList.add('on');
  });
})();
```

- [ ] **Step 2:** Commit — `git commit -m "feat(web): chat-panel.js — block renderer + live media flow"`

---

### Task 5: mount in cockpit

**Files:**
- Modify: `web/cockpit.html`

- [ ] **Step 1:** Wrap the existing cockpit body content in `<div class="sa-app-main">` and add `<div id="sa-chatpane"></div>` as a sibling; add to head: `<link rel="stylesheet" href="chat-panel.css">`; before `</body>`: `<script src="chat-panel.js"></script>`; add layout CSS (scoped, additive):

```css
@media(min-width:1100px){
  body{display:grid;grid-template-columns:1fr 30%;}
  .sa-app-main{min-width:0;}
  #sa-chatpane{position:sticky;top:0;max-height:100vh;display:flex;flex-direction:column;border-left:2px solid #141118;background:#fff;}
}
@media(max-width:1099px){#sa-chatpane{display:none}}
```

- [ ] **Step 2:** Open locally (`./run_hybrid.sh`, browse cockpit), verify: panel fixed right at 30%, chat round-trips `/api/saakshe/ask`, media question produces slider + buttons, slider re-quotes live, render completes with receipt + verify badge.
- [ ] **Step 3:** Run the full per-directory suite + `tests/`.
- [ ] **Step 4:** Commit — `git commit -m "feat(web): always-on Brut chat panel mounted in cockpit (70/30)"`

---

### Task 6: deploy + live verify + report

- [ ] **Step 1:** `./deploy_cloudrun.sh` (standing instruction: deploy once tests pass).
- [ ] **Step 2:** On prod: sign in, ask "make my image an HDR video, budget $1", complete a 2s render, download, ffprobe-verify locally.
- [ ] **Step 3:** Brut HTML report to the founder (brut-reports skill): what shipped, screenshots, receipt sample, what's deferred (DV8.4, credits wiring for render, Veo path live-call).

---

## Self-review notes

- Coverage: 30% fixed panel✓ never collapses (≥1100px)✓ tabs per faculty✓ blocks not lumps✓ presenter never authors (passes text through)✓ slider 1–8s live re-quote✓ all 12 FX menu✓ receipt + verify badge✓ light mode only (dark deferred — user allowed).
- Contract consistency: block kinds (`text/data/actions/slider/progress/receipt`) identical in presenter.py and chat-panel.js; action names (`media.render/requote/fxmenu/view`) match between Task 1 buttons and Task 4 handler.
- Honest gaps flagged in final report: faculty tabs are visual-only v1 (all questions go to the same ask endpoint); job receipt blocks come from `fallbackReceipt` unless service adds `blocks` to job status (acceptable v1).

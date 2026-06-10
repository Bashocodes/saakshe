"""Build web/samples.html from live manas ingestion captures — in setu's design system.

The samples are REAL runs: each famous open-source product was connected through
the product's own ingest pipeline (real shallow clone + real site fetch + live
Gemini imbibers + curation) and the resulting Context Pack was captured VERBATIM —
facts, citations, and the clarifying questions manas asked back. Nothing is
hand-written. Re-run a capture, re-run this script, and the page updates.

The page is a sibling of web/setu.html and reuses its switchboard system
verbatim — tokens (light bakelite / dark exchange-room), Saira/Hanken
Grotesk/Martian Mono type, .panel/.demo/.jacks/.pack/.qcard/.stamp components,
the setu-theme pre-paint boot, and setu's ABSOLUTE RULE: no colored band /
stripe / border-accent on any container edge; system hues only as dots <=12px.

Usage:
    python scripts/build_samples_page.py <capture.json> [<capture.json> ...]

Each capture (canonical copies in deploy/samples/) is:
    {org, version, grounded, ingest_status, fact_count, facts, questions,
     captured_at, sources: [[label, url], ...]}
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "samples.html"

MAX_PACK_LINES = 10

_JACK_NAMES = {"github": "code repo", "website": "website"}


def esc(s: object) -> str:
    return html.escape(str(s or ""))


def _jack_kind(label: str) -> str:
    return "github" if "github" in label else "website"


def render_sample(idx: int, cap: dict) -> str:
    org = cap.get("org") or {}
    facts = cap.get("facts") or []
    questions = cap.get("questions") or []
    sources = cap.get("sources") or []
    version = esc(cap.get("version") or "v1")
    n = len(facts)

    jacks = "".join(
        f'<li><span class="jack" aria-pressed="true">'
        f'<span class="jdot" aria-hidden="true"></span>'
        f'<span class="jname">{esc(_JACK_NAMES[_jack_kind(label)])}</span>'
        f'<span class="jstate">patched</span></span></li>'
        for label, _u in sources
    )
    src_tags = "".join(
        f'<a class="tag" href="{esc(u)}" target="_blank" rel="noopener">{esc(label)}</a>'
        for label, u in sources
    )

    shown = facts[:MAX_PACK_LINES]
    lines = "".join(
        f'<li>{esc(f.get("claim"))} <span class="src">· {esc(f.get("source"))}</span></li>'
        for f in shown
    )
    if n > MAX_PACK_LINES:
        lines += (
            f'<li class="more">… +{n - MAX_PACK_LINES} more cited lines in this pack '
            f'(captured verbatim in deploy/samples/)</li>'
        )

    qcards = "".join(
        f'<div class="qcard"><div class="qmeta">manas asked back · {esc(q.get("trigger", "").replace("_", " "))}</div>'
        f'<h3>{esc(q.get("text"))}</h3>'
        f'<p class="ink2" style="font-size:15px;margin-bottom:0">why · {esc(q.get("why"))}</p></div>'
        for q in questions
    )

    return f"""
<section>
  <div class="wrap">
    <span class="sec-no">0{idx} — {esc(org.get("name"))}</span>
    <div class="demo">
      <div class="demo-head">
        <div>
          <div class="eyebrow">patched in over setu · read live</div>
          <h3 style="margin-top:6px">{esc(org.get("name"))}</h3>
          <p class="ink2" style="font-size:15px;max-width:58ch;margin:8px 0 0">{esc(org.get("one_liner"))}</p>
        </div>
        <div class="flex">{src_tags}<span class="tag">{n} cited facts</span></div>
      </div>
      <div class="demo-grid">
        <div>
          <div class="label" style="margin-bottom:8px">granted sources</div>
          <ul class="jacks">{jacks}</ul>
          <p class="readonly-note">read-only · a shallow clone and a page fetch — exactly what any
          founder grants on day one. Every line on the right traces back to one of these.</p>
        </div>
        <div>
          <div class="label" style="margin-bottom:8px">manas imbibers · context pack</div>
          <div class="pack live">
            <div><span class="ver">Context Pack {version}</span><span class="verdot" aria-hidden="true"></span>
              <span class="grounded">grounded</span></div>
            <ul>{lines}</ul>
          </div>
          {qcards}
          <div style="margin-top:14px"><span class="stamp">answers fold back · the pack ticks {version} → v{int(version.lstrip("v") or 1) + 1}</span></div>
        </div>
      </div>
    </div>
  </div>
</section>"""


def build(captures: list[dict], captured_at: str) -> str:
    sections = "\n".join(render_sample(i + 1, c) for i, c in enumerate(captures))
    names = " · ".join(esc((c.get("org") or {}).get("name")) for c in captures)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<link rel="icon" href="data:,">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>samples — repos the company had never seen</title>
<meta name="description" content="Three famous open-source products ({names}) connected through saakshe's own ingest pipeline — real clone, real site fetch, live Gemini imbibers, a versioned source-cited Context Pack, and the clarifying questions manas asked back. Captured verbatim; verify every line against the public repos.">

<script>(function(){{
  var d=document.documentElement; d.className='js';
  var q={{}}; try{{ (location.search||'').replace(/^\\?/,'').split('&').forEach(function(p){{
    if(!p)return; var kv=p.split('='); q[decodeURIComponent(kv[0])]=decodeURIComponent(kv[1]||''); }}); }}catch(e){{}}
  var t=q.theme;
  if(t!=='light'&&t!=='dark'){{ try{{t=localStorage.getItem('setu-theme');}}catch(e2){{}} }}
  if(t!=='light'&&t!=='dark'){{ t=(window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches)?'dark':'light'; }}
  d.setAttribute('data-theme',t);
}})();</script>

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Saira:wght@400;500;600;700&family=Hanken+Grotesk:wght@400;500;600;700&family=Martian+Mono:wght@400;500;600&display=swap">

<style>
/* SETU system, verbatim — the switchboard. ABSOLUTE RULE: no colored band /
   stripe / border-accent on ANY container edge; hues only as dots <=12px. */
:root{{
  --bg:#f3f1ec; --bg-2:#efece5; --panel:#faf8f3; --panel-2:#f6f3ec; --well:#ece8df;
  --ink:#232520; --ink-2:#5d5a51; --muted:#84807548; --muted-s:#827e72;
  --rule:#d8d3c7; --rule-2:#cdc7b9; --ghost:#e8e4da;
  --acc:#3f7d6e; --acc-press:#2f5d52; --acc-ring:#3f7d6e55;
  --sw-off:#cfcabd; --sw-on:#3f7d6e; --brass:#9a8c5e;
  --manas:#b8862f; --arivu:#6a4fd0; --kalai:#b9602f; --kural:#2f54c0; --saakshe:#4a4d52;
  --sel-bg:#dfe9e4; --sel-fg:#1c241f; color-scheme:light;
}}
[data-theme="dark"]{{
  --bg:#16181a; --bg-2:#191c1e; --panel:#1e2123; --panel-2:#1a1d1f; --well:#121315;
  --ink:#e8e6df; --ink-2:#a6a399; --muted:#6f6c6388; --muted-s:#8c897e;
  --rule:#34383a; --rule-2:#3e4244; --ghost:#212527;
  --acc:#5fb89e; --acc-press:#7fd0b6; --acc-ring:#5fb89e55;
  --sw-off:#3a3e3f; --sw-on:#5fb89e; --brass:#b6a877;
  --manas:#e6b454; --arivu:#9a82f0; --kalai:#e08a55; --kural:#6f8cf5; --saakshe:#9aa0a8;
  --sel-bg:#274038; --sel-fg:#e8f3ee; color-scheme:dark;
}}
*{{box-sizing:border-box}} html{{-webkit-text-size-adjust:100%}}
body{{margin:0;background:var(--bg);color:var(--ink);
  font-family:"Hanken Grotesk",system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  font-size:16px;line-height:1.65;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}}
::selection{{background:var(--sel-bg);color:var(--sel-fg)}}
h1,h2,h3{{font-family:"Saira",sans-serif;font-weight:600;letter-spacing:-0.01em;line-height:1.08;margin:0}}
h1{{font-size:clamp(34px,6vw,62px);font-weight:700;letter-spacing:-0.02em;font-stretch:semi-condensed}}
h3{{font-size:clamp(18px,2.4vw,23px)}}
p{{margin:0 0 1em 0}}
.lead{{font-size:clamp(18px,2.2vw,20px);line-height:1.6;color:var(--ink-2);max-width:62ch}}
a{{color:var(--acc);text-decoration:none;border-bottom:1px solid var(--acc-ring)}}
a:hover{{color:var(--acc-press)}}
.eyebrow{{font-family:"Martian Mono",monospace;font-size:13px;font-weight:500;letter-spacing:0.16em;text-transform:uppercase;color:var(--acc)}}
.label{{font-family:"Martian Mono",monospace;font-size:13px;letter-spacing:0.1em;color:var(--muted-s)}}
.acc{{color:var(--acc)}} .ink2{{color:var(--ink-2)}}
.wrap{{max-width:1080px;margin:0 auto;padding:0 24px}}
section{{padding:56px 0;border-top:1px solid var(--rule)}}
section:first-of-type{{border-top:none}}
.sec-no{{font-family:"Martian Mono",monospace;font-size:13px;letter-spacing:0.14em;color:var(--muted-s);margin-bottom:14px;display:block}}
.sec-head{{max-width:64ch;margin-bottom:28px}} .sec-head h1{{margin-bottom:16px}}
.panel{{background:var(--panel);border:1px solid var(--rule);border-radius:10px;padding:24px}}
.tag{{display:inline-flex;align-items:center;font-family:"Martian Mono",monospace;font-size:13px;
  letter-spacing:0.05em;color:var(--ink-2);border:1px solid var(--rule);border-radius:999px;
  padding:5px 11px;background:var(--panel-2)}}
a.tag{{border-bottom-width:1px}} a.tag:hover{{color:var(--acc);border-color:var(--rule-2)}}
.flex{{display:flex;flex-wrap:wrap;gap:10px;align-items:center}}
.stamp{{display:inline-flex;align-items:center;gap:7px;font-family:"Martian Mono",monospace;
  font-size:13px;letter-spacing:0.08em;color:var(--acc);border:1px solid var(--rule-2);
  border-radius:5px;padding:6px 11px;background:var(--well);text-transform:uppercase}}
.stamp::before{{content:"";width:6px;height:6px;border-radius:50%;background:var(--acc);flex:none}}
.topbar{{position:sticky;top:0;z-index:40;background:var(--bg);border-bottom:1px solid var(--rule)}}
.topbar .wrap{{display:flex;align-items:center;justify-content:space-between;padding-top:14px;padding-bottom:14px}}
.brand{{display:flex;align-items:baseline;gap:10px;font-family:"Saira",sans-serif;font-weight:700;font-size:20px;letter-spacing:-0.01em}}
.brand .sib{{font-family:"Martian Mono",monospace;font-size:13px;font-weight:500;letter-spacing:0.08em;color:var(--muted-s)}}
.tgl{{font-family:"Martian Mono",monospace;font-size:13px;letter-spacing:0.08em;color:var(--ink-2);
  background:var(--panel);border:1px solid var(--rule);border-radius:7px;padding:8px 13px;cursor:pointer}}
.tgl:hover{{border-color:var(--rule-2);color:var(--ink)}}
.tgl .dot{{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--acc);vertical-align:middle;margin-right:7px}}
.hero{{padding-top:56px}} .hero h1{{margin-bottom:18px;max-width:18ch}}
.demo{{background:var(--panel);border:1px solid var(--rule);border-radius:12px;padding:24px}}
.demo-head{{display:flex;flex-wrap:wrap;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:18px}}
.demo-grid{{display:grid;gap:18px}}
@media(min-width:860px){{.demo-grid{{grid-template-columns:0.8fr 1.2fr}}}}
.jacks{{list-style:none;margin:0;padding:0;display:grid;gap:9px}}
.jack{{display:flex;align-items:center;gap:11px;width:100%;background:var(--well);
  border:1px solid var(--rule);border-radius:8px;padding:11px 14px;font-size:15px;color:var(--ink)}}
.jack .jdot{{width:11px;height:11px;border-radius:50%;background:var(--sw-off);flex:none}}
.jack .jname{{flex:1;font-weight:500}}
.jack .jstate{{font-family:"Martian Mono",monospace;font-size:13px;letter-spacing:0.06em;color:var(--muted-s)}}
.jack[aria-pressed="true"] .jdot{{background:var(--manas)}}
.jack[aria-pressed="true"] .jstate{{color:var(--acc)}}
.readonly-note{{font-size:14px;color:var(--ink-2);margin:12px 0 0}}
.pack{{background:var(--well);border:1px solid var(--rule);border-radius:8px;padding:16px}}
.pack .ver{{font-family:"Saira",sans-serif;font-weight:700;font-size:22px;color:var(--ink)}}
.pack .verdot{{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--acc);margin-left:8px;vertical-align:middle}}
@keyframes pulse{{0%,100%{{opacity:.3}}50%{{opacity:1}}}}
.live .verdot{{animation:pulse 1.8s ease-in-out infinite}}
.pack .grounded{{font-family:"Martian Mono",monospace;font-size:13px;letter-spacing:0.06em;color:var(--acc);margin-left:10px}}
.pack ul{{list-style:none;margin:12px 0 0;padding:0;display:grid;gap:6px}}
.pack li{{font-family:"Martian Mono",monospace;font-size:13px;letter-spacing:0.02em;color:var(--ink-2);line-height:1.5}}
.pack li::before{{content:"› ";color:var(--acc)}}
.pack li .src{{color:var(--muted-s)}}
.pack li.more{{color:var(--muted-s)}}
.qcard{{background:var(--well);border:1px solid var(--rule);border-radius:8px;padding:18px;margin-top:16px}}
.qcard h3{{margin-bottom:6px;font-size:clamp(16px,2vw,19px)}}
.qcard .qmeta{{font-family:"Martian Mono",monospace;font-size:13px;letter-spacing:0.06em;color:var(--acc);margin-bottom:10px}}
.btn{{font-family:"Saira",sans-serif;font-weight:600;font-size:15px;color:var(--bg);background:var(--acc);
  border:1px solid var(--acc);border-radius:8px;padding:11px 20px;cursor:pointer;display:inline-block}}
.btn:hover{{background:var(--acc-press);border-color:var(--acc-press)}}
a.btn{{color:var(--bg);border-bottom:1px solid var(--acc)}}
.btn-ghost{{color:var(--ink-2);background:var(--panel);border:1px solid var(--rule)}}
a.btn-ghost{{color:var(--ink-2)}} .btn-ghost:hover{{color:var(--ink);background:var(--panel-2);border-color:var(--rule-2)}}
.foot{{border-top:1px solid var(--rule);padding:56px 0 64px}}
.seam{{font-family:"Martian Mono",monospace;font-size:13px;letter-spacing:0.06em;color:var(--muted-s);line-height:1.9;margin:0 0 26px}}
.siblings{{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:24px}}
.siblings a{{font-family:"Martian Mono",monospace;font-size:13px;letter-spacing:0.06em;
  border:1px solid var(--rule);border-radius:999px;padding:8px 15px;color:var(--ink-2);background:var(--panel)}}
.siblings a:hover{{color:var(--acc);border-color:var(--rule-2)}}
.siblings a.self{{color:var(--acc);border-color:var(--acc-ring)}}
.footmeta{{font-family:"Martian Mono",monospace;font-size:13px;letter-spacing:0.03em;color:var(--muted-s);line-height:1.8}}
</style>
</head>
<body>

<header class="topbar">
  <div class="wrap">
    <div class="brand">samples <span class="sib">· receipts of the first minute</span></div>
    <button class="tgl" id="themeToggle" type="button" aria-label="Toggle light or dark theme">
      <span class="dot" aria-hidden="true"></span><span id="themeLabel">dark room</span>
    </button>
  </div>
</header>

<main>

<section class="hero">
  <div class="wrap">
    <span class="sec-no">00 — receipts, not claims</span>
    <div class="sec-head">
      <h1>Products the company had never seen.</h1>
      <p class="lead">Each product below was patched in over <a href="setu.html">setu</a> exactly the way a
      founder would — a public repo jack and a website jack, read-only. <span class="acc">manas</span>'s
      imbibers read the real sources with live Gemini, committed a versioned Context Pack where
      <strong>every line carries the file or URL it came from</strong>, and asked back what the sources
      couldn't answer. Nothing here is hand-written — check any line against the public repo.</p>
      <p class="label">captured {captured_at} · manas.ingest_connected, live · gemini-3.5-flash imbibers · curation gate ≥ 0.80</p>
    </div>
  </div>
</section>
{sections}

<section>
  <div class="wrap">
    <span class="sec-no">04 — run it on yours</span>
    <div class="panel">
      <h3 style="margin-bottom:8px">This is minute one with any company.</h3>
      <p class="ink2" style="max-width:62ch">Patch your own jacks, watch the Pack form, answer what manas asks —
      then the rest of the company (arivu decides · kalai makes · kural engages) works only from that
      cited memory, behind your two gates.</p>
      <div class="flex">
        <a class="btn" href="setu.html">how connection works →</a>
        <a class="btn-ghost btn" href="saakshe_landing.html">about saakshe</a>
      </div>
    </div>
  </div>
</section>

</main>

<footer class="foot">
  <div class="wrap">
    <p class="seam">knows → manas &nbsp;·&nbsp; decides → arivu &nbsp;·&nbsp; makes → kalai &nbsp;·&nbsp; engages → kural &nbsp;·&nbsp; witnesses → saakshe</p>
    <div class="siblings">
      <a href="setu.html">setu</a>
      <a href="manas.html">manas</a>
      <a href="arivu.html">arivu</a>
      <a href="kalai.html">kalai</a>
      <a href="kural.html">kural</a>
      <a href="cockpit.html">saakshe</a>
    </div>
    <p class="footmeta">samples — three real ingestion captures, verbatim. {names}.<br>
    read-only sources · every fact cited · the questions are what manas actually asked &nbsp;·&nbsp;
    built on ADK &nbsp;·&nbsp; Gemini + Claude via Vertex AI.</p>
  </div>
</footer>

<script>
(function(){{
  var toggle=document.getElementById('themeToggle'), lbl=document.getElementById('themeLabel');
  function paint(){{
    var t=document.documentElement.getAttribute('data-theme');
    if(lbl) lbl.textContent = (t==='dark') ? 'day room' : 'dark room';
  }}
  if(toggle) toggle.addEventListener('click',function(){{
    var cur=document.documentElement.getAttribute('data-theme');
    var next=(cur==='dark')?'light':'dark';
    document.documentElement.setAttribute('data-theme',next);
    try{{ localStorage.setItem('setu-theme',next); }}catch(e){{}}
    paint();
  }});
  paint();
}})();
</script>
</body>
</html>
"""


def main() -> None:
    paths = [Path(p) for p in sys.argv[1:]]
    if not paths:
        sys.exit("usage: build_samples_page.py <capture.json> [...]")
    captures = [json.loads(p.read_text()) for p in paths]
    captured_at = captures[0].get("captured_at", "")
    OUT.write_text(build(captures, captured_at))
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {len(captures)} samples)")


if __name__ == "__main__":
    main()

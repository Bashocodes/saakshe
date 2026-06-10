"""Build web/samples.html from live manas ingestion captures.

The samples are REAL runs: each famous open-source product was connected
through the product's own ingest pipeline (real shallow clone + real site
fetch + live Gemini imbibers + curation) and the resulting Context Pack was
captured VERBATIM — facts, citations, and the clarifying questions manas
asked back. Nothing is hand-written. Re-run a capture, re-run this script,
and the page updates.

Usage:
    python scripts/build_samples_page.py <capture.json> [<capture.json> ...]

Each capture is the JSON written by an ingest run:
    {org, version, grounded, ingest_status, fact_count, facts, questions,
     captured_at?, sources?}
The canonical captures live in deploy/samples/.
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "samples.html"


def esc(s: object) -> str:
    return html.escape(str(s or ""))


def render_sample(cap: dict) -> str:
    org = cap.get("org") or {}
    facts = cap.get("facts") or []
    questions = cap.get("questions") or []
    sources = cap.get("sources") or []
    src_chips = "".join(
        f'<a class="chip" href="{esc(u)}" target="_blank" rel="noopener">{esc(label)}</a>'
        for label, u in sources
    )
    fact_rows = "".join(
        f'<li><span class="claim">{esc(f.get("claim"))}</span>'
        f'<span class="cite">{esc(f.get("source"))}</span></li>'
        for f in facts
    )
    q_rows = "".join(
        f'<li><span class="qtext">{esc(q.get("text"))}</span>'
        f'<span class="qwhy">why · {esc(q.get("why"))}</span></li>'
        for q in questions
    )
    status = f'{esc(cap.get("version"))} · {"grounded" if cap.get("grounded") else "needs answers"}'
    return f"""
<section class="sample">
  <header>
    <h2>{esc(org.get("name"))}</h2>
    <p class="oneliner">{esc(org.get("one_liner"))}</p>
    <div class="meta"><span class="pack">{status}</span>{src_chips}</div>
  </header>
  <div class="cols">
    <div>
      <h3>{len(facts)} cited facts manas extracted</h3>
      <ul class="facts">{fact_rows}</ul>
    </div>
    <div>
      <h3>{len(questions)} questions manas asked back</h3>
      <ul class="questions">{q_rows}</ul>
      <p class="qnote">Answers fold back into the memory as cited facts and the
      Context Pack version ticks — the same loop a founder gets.</p>
    </div>
  </div>
</section>"""


def build(captures: list[dict], captured_at: str) -> str:
    sections = "\n".join(render_sample(c) for c in captures)
    return f"""<!doctype html>
<html lang="en" data-theme="dark">
<head>
<meta charset="utf-8">
<link rel="icon" href="data:,">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>samples — manas breakdowns of repos it had never seen</title>
<meta name="description" content="Three famous open-source products connected through saakshe's real ingest pipeline — live Gemini extraction, source-cited facts, and the clarifying questions manas asked back. Captured verbatim, verifiable against the public repos.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;0,9..144,600;0,9..144,700&family=Spline+Sans:wght@400;500;600;700&family=Spline+Sans+Mono:wght@400;500;600&display=swap">
<style>
:root{{
  --bg:#0B0B14; --well:#14132A; --panel:#13131F; --panel-2:#181826;
  --ink:#E6E3F2; --ink-2:#BFBCD8; --muted:#8C88B8; --rule:#262538; --rule-2:#302F47;
  --accent:#E8B84B; --accent-soft:rgba(232,184,75,.16);
  --disp:'Fraunces',Georgia,serif; --body:'Spline Sans',system-ui,sans-serif;
  --mono:'Spline Sans Mono',ui-monospace,monospace;
  color-scheme:dark;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:radial-gradient(1200px 700px at 50% -120px,var(--well),var(--bg) 70%) var(--bg);
  color:var(--ink);font:16px/1.65 var(--body);min-height:100vh;padding-bottom:90px}}
.wrap{{max-width:1080px;margin:0 auto;padding:0 28px}}
.top{{padding:54px 0 8px}}
.top .eyebrow{{font-family:var(--mono);font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent)}}
h1{{font-family:var(--disp);font-weight:600;font-size:clamp(30px,4.6vw,44px);letter-spacing:-.01em;margin:10px 0 14px}}
.lede{{color:var(--ink-2);max-width:760px}}
.lede b{{color:var(--ink)}}
.provenance{{margin:18px 0 0;font-family:var(--mono);font-size:12px;color:var(--muted)}}
.sample{{margin:46px 0 0;background:var(--panel);border:1px solid var(--rule);border-radius:14px;padding:30px 32px}}
.sample h2{{font-family:var(--disp);font-weight:600;font-size:27px}}
.oneliner{{color:var(--ink-2);margin:6px 0 12px;max-width:820px}}
.meta{{display:flex;flex-wrap:wrap;gap:8px;align-items:center}}
.pack{{font-family:var(--mono);font-size:12px;color:var(--accent);background:var(--accent-soft);
  border-radius:99px;padding:3px 11px}}
.chip{{font-family:var(--mono);font-size:12px;color:var(--muted);border:1px solid var(--rule-2);
  border-radius:99px;padding:3px 11px;text-decoration:none}}
.chip:hover{{color:var(--ink)}}
.cols{{display:grid;grid-template-columns:1.25fr 1fr;gap:30px;margin-top:24px;
  border-top:1px solid var(--rule);padding-top:22px}}
@media(max-width:820px){{.cols{{grid-template-columns:1fr}}}}
h3{{font-family:var(--mono);font-size:12px;letter-spacing:.12em;text-transform:uppercase;
  color:var(--muted);margin-bottom:14px}}
ul{{list-style:none}}
.facts li,.questions li{{padding:10px 0;border-bottom:1px solid var(--rule);display:block}}
.facts li:last-child,.questions li:last-child{{border-bottom:none}}
.claim{{display:block;font-size:14.5px;color:var(--ink)}}
.cite{{display:block;margin-top:4px;font-family:var(--mono);font-size:11.5px;color:var(--muted)}}
.cite::before{{content:'cited · '}}
.qtext{{display:block;font-size:14.5px;color:var(--ink);font-style:italic}}
.qwhy{{display:block;margin-top:4px;font-family:var(--mono);font-size:11.5px;color:var(--muted)}}
.qnote{{margin-top:16px;font-size:13px;color:var(--muted)}}
.foot{{margin-top:54px;border-top:1px solid var(--rule);padding-top:24px;color:var(--muted);font-size:14px}}
.foot a{{color:var(--accent);text-decoration:none}}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <p class="eyebrow">samples · manas, the company's mind</p>
    <h1>Repos it had never seen, broken down live.</h1>
    <p class="lede">Each product below was connected through saakshe's own ingest pipeline —
    a real shallow clone of the public repo, a real fetch of the public site, <b>live Gemini
    imbibers</b> extracting claims, and the curation gate committing a versioned, source-cited
    Context Pack. What you see is the captured output, <b>verbatim</b>: nothing here is
    hand-written, and every fact carries the file or URL it came from — check it against the
    public repo directly. The questions are what manas asked back when its sources fell short.</p>
    <p class="provenance">captured {captured_at} · pipeline: manas.ingest_connected (live) ·
    models: gemini-3.5-flash imbibers + gemini-3.1-pro curation seat</p>
  </header>
  {sections}
  <footer class="foot">
    <p>This is the first minute of saakshe with any company: connect, imbibe, get asked the
    questions your sources can't answer. <a href="/saakshe_landing.html">About saakshe</a> ·
    <a href="/manas.html">how manas works</a></p>
  </footer>
</div>
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

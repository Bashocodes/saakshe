# saakshe — landing/home page spec (dual-theme: Brut light / Obsidian dark)

BUILD ONE self-contained file: `~/Desktop/Working/saakshe_landing.html` (no build step,
no external JS deps; Google Fonts CDN only). It is the saakshe **home/landing page**.
Do NOT touch anything under `~/Desktop/Working/saakshe/` (the backend is being built by
other sessions). Style/logo reference to REUSE: `~/Desktop/Working/example_hackathon_decoded.html`
(its CSS `>_ | SAAKSHE` logo lockup + Bauhaus tokens). Serve/verify at
`http://localhost:8770/saakshe_landing.html`.

## THE PRODUCT MODEL (front-end = THREE, arivu is the shared decision engine)
The founder sees **three faculties**, each a Bauhaus shape:
- ⬤ **manas** (circle) — THE MIND: knows + grounds. Imbibes the founder's repo, site,
  socials into one cited, versioned memory (Context Pack). Refuses out-of-corpus.
- ▲ **kalai** (triangle) — MAKES: on-brand creative (image/copy), brand-fidelity loop,
  fail-closed compliance. No channel keys.
- ◼ **kural** (square) — ENGAGES: the only mouth. Posts, outreach, replies; every claim
  fact-checked; publish behind the founder's tap.
**arivu = the shared DECISION chamber all three call.** NOT a 4th shape. It is the company's
judgment engine: 5 advisor agents argue from manas's memory → debate → a Claude·Vertex verdict
→ an adversarial prosecutor must clear defensibility ≥ 0.80 → ONE founder tap → it commits.
manas decides through it; kalai and kural run their hard calls through it too. Frame arivu as
the crown jewel — "multi-agent beats a single agent," made shared. (Backend is 4 quadrants /
28 seats; the front-end speaks 3 + the shared chamber. Never say "four" in the landing copy.)
**saakshe = the witness.** One cockpit the founder talks to (chat + voice). Initiates nothing;
answers only from live telemetry; refuses beyond its data — that refusal is what makes it an
agent. Two human gates total (decide-tap @ arivu, publish-tap @ kural).
The flywheel: connect your project → manas learns → arivu decides → kalai makes → kural engages
→ manas learns again. The witness watches it live; you tap the gates.

## CONTENT (marketing voice; speak to a solo founder / small company)
NO "Sundara Coffee Co." anywhere — that canned example is dead. Speak generically ("your
company", "your repo + site + socials"). Sections (in order):
1. HERO — the `>_ | SAAKSHE` logo (CSS text, reuse the lockup), a light/dark toggle (top-right,
   persists via localStorage, set before paint), one-line tagline (e.g. "The agentic company
   you talk to." / "One founder. A whole company. One witness."), a sub (2-3 lines: you connect
   your project; three faculties run it; one witness you talk to), and the THREE shapes shown
   big (circle/triangle/square = manas/kalai/kural) with the shared arivu decision engine implied
   between them. A primary CTA ("Connect your project") + secondary ("See the cockpit ↓").
2. THE THREE + THE CHAMBER — three faculty cards (manas/kalai/kural) each with its shape, verb,
   one-line "does", and a "decides through arivu" line; plus a distinct arivu panel: the shared
   decision chamber (5 advisors → debate → verdict → prosecutor ≥0.80 → your tap). + the witness
   (saakshe) one-liner: you talk only to saakshe; it refuses beyond what it can see.
3. HOW IT WORKS — the flywheel as a clean diagram/row: connect → manas learns → arivu decides →
   kalai makes → kural engages → (loops). Mark the two founder taps (decide, publish).
4. GOVERNED, REAL ACTION — BYOK (your Gemini key, your Claude-via-Vertex, your channel keys),
   two human gates, dry-run by default, fail-closed compliance, never writes a price/revenue
   column. Track 3 (B2B / Marketplace / BYOK).
5. BUILT ON GOOGLE'S STACK — ADK (Sequential/Parallel/Loop), Gemini (latest 3.x) for the many
   + Claude via Vertex AI for the high-stakes judgment, Agent Engine deploy, A2A between
   faculties, eval @0.8, OTel observability. Honest: "live Gemini today; Claude·Vertex on the
   high-stakes seats."
6. ★ COCKPIT SHOWCASE (the main ask) — rebuild a stylized cockpit OVERVIEW *in the active theme*:
   a topbar (SAAKSHE wordmark + a few status pills + theme chip), a left nav rail (Overview ·
   manas · kalai · kural · Questions · Activity · Settings), a center "THE COMPANY, WATCHED" with
   THREE quadrant cards (manas/kalai/kural — each: name + verb tag + a state line + a tiny
   sparkline + 2-3 stat chips + the Bauhaus shape in the corner) and a shared "arivu · decision
   chamber" strip, and a right WITNESS panel (● SAAKSHE — the witness · ask/taps/today tabs · a
   couple of chat bubbles · fact pills · a red/green primary action button · chip buttons). This
   is a static visual showcase (no real backend calls) — it must adopt Brut in light, Obsidian in
   dark. Use neutral placeholder data ("your company · connected · Context Pack v3", generic
   costs) — NO Sundara, NO forbidden sealed numbers.
7. CTA + FOOTER — connect-your-project CTA; footer with the small logo, the verb map
   (knows→manas · decides→arivu · makes→kalai · engages→kural · witnesses→saakshe), Track 3·BYOK,
   "Google for Startups AI Agents Challenge".

## TWO THEMES (one page, a toggle swaps the WHOLE aesthetic; both must be excellent)
LIGHT = **Brut — poster brutalist**:
- Warm cream bg `#F4EEE2` + faint grid; near-black ink `#161410`; thick BLACK borders (2.5–3px).
- Big BOLD UPPERCASE grotesque display (Space Grotesk 700 / Archivo). Mono labels (IBM Plex Mono):
  QUADRANTS, KNOWS, CORE DENSE, // section markers.
- BLACK header strips on cards; the verb tag (KNOWS/MAKES/ENGAGES) in a black pill.
- Quadrant tints: manas `#F1DC95`/accent `#E3A52B`, kalai `#EBBAAC`/`#CC4632`, kural `#BFE0C6`/`#3E8F5E`,
  arivu `#C6CFF2`/`#3551C8`. **Per-quadrant hard accent drop-shadow** (offset 8px colored block
  behind each card, e.g. manas card casts an amber+black offset). Red `#CC4632` = primary action.
- Bauhaus geometric shape (circle/triangle/square/semicircle) in each card corner, in the accent.
- Wordmark = Michroma (the `>_ | SAAKSHE` lockup with a hard offset shadow box).
DARK = **Obsidian — phosphor terminal**:
- Near-black bg `#0A0D0A` + faint grid; phosphor green `#5EF08A` accents + subtle glow.
- MONOSPACE-forward (IBM Plex Mono / JetBrains Mono) for headings + data; the display line as a
  command prompt: `saakshe@cockpit:~$ <heading>_` with a blinking cursor.
- `// 00 / SECTION` comment markers; chips shown as **bracketed tokens** `[ connect your project ]`.
- Quadrant cards = very dark tinted washes with a colored 1px outline + soft glow; the focus/active
  card (arivu) gets a bright green focus border + corner **focus-brackets** ⌐ ¬ and glow.
- Hues stay per-quadrant but muted on black (amber/blue/red/green). Green = primary action.
- Same `>_ | SAAKSHE` lockup, green-tinted, on black.

## BEHAVIORS / QUALITY BARS
- Theme toggle: persists (localStorage `saakshe-theme`), applied before first paint (no flash);
  default light. A `?theme=dark` URL param also works (handy for screenshots).
- Fully responsive (works 390 / 768 / 1440); the cockpit showcase may scale/scroll on mobile.
- No horizontal overflow; readable contrast in BOTH themes (≥4.5:1 body); no colored edge-bands
  that read as a "streak" on container left/right edges (hard offset shadows + full borders are OK).
- Tasteful motion only (scroll-reveal / cursor blink / sparkline); respects prefers-reduced-motion;
  works with JS off (content + a static theme visible). ZERO JS console errors.
- Self-contained single file; Google Fonts via CDN (Space Grotesk, Archivo, IBM Plex Mono,
  JetBrains Mono, Michroma). Add `<link rel="icon" href="data:,">` to kill the favicon 404.

## VERIFY (headless, both themes)
Screenshot light + dark at 1440 + 390. Assert: logo lockup present (CSS text, NOT an <img>);
exactly THREE faculty shapes (circle/triangle/square) in the model + showcase; the word "arivu"
appears as the shared decision chamber (not a 4th faculty card); a cockpit-showcase section
exists with a witness panel; theme toggle flips bg light↔dark and persists; no "Sundara",
no "watched as four"/"four systems" in copy; 0 JS errors; no horizontal scroll.

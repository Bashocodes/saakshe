# cockpit.html v9 — DEEP PASS SPEC (2026-06-07, binding) — FINAL
Synthesized from a 4-agent audit (UI 12 · content 13 · chat 12 findings) + the allow-list fact bank
`.cockpit_factbank.json` (28 seats / 16 desks / forbidden list — READ IT; every fact in new content must be on it).
The LAST frontend polish before backend wiring. Extends `.cockpit_v2_spec.md` + `.cockpit_v3_spec.md`.
Baseline = v8 (saakshe · manas/arivu/kalai/kural · Soft Clay). Backup: `.cockpit_v8arivu_backup_2026_06_07.html`.
**EVOLVE surgically. The loved surfaces — overview, top-level desks-across quadrant pages, sidebar nav, Soft Clay tokens — are touched lightly or not at all.**

## 0 · HARD RULES (violations got builds rejected — absolute)
- NEVER colored bands/stripes on container edges. Containers: borderless shadow-depth (Soft Clay) or uniform neutral hairline. Tint washes on SURFACES are fine.
- NO scrolling anywhere except `.chatlog`.
- 28 seats (manas 7 · arivu 9 · kalai 5 · kural 7) · EXACTLY 8 Claude rings, 2/quadrant. Ring rendering stays DATA-DRIVEN from QDATA `claude:true` — never hand-paste `.ring` spans (the count is checked per-state).
- Canonical numbers EXACT, no invention: $39→$34 (grandfather · 30-day notice) · 0.84/0.88 · 6.8→8.4→9.1 (two regens, $0.10+$0.10) · $4.18 = 0.74+2.31+0.20+0.93 = 1.92+2.06+0.20 · $40/day cap · Pack v14→v15 (+2 voice convictions · 1 rule softened) · 11 days · 2 taps · 8 questions · 12 events · 3 cafés/1 booked/@0.8 · master v3 · 9.1/10 · deck p14/22 · 38 comments · 6 citations/1 conflict · 12 fragments→5 buckets · /resolutions/sundara-pro-pricing-2026-06 · cliff at $39 breaks ~$36 · $29 dissent tier · $9.99→$19→$29 lineage · Enterprise $200–500/mo.
- **ALLOW-LIST: every fact/number in new content must exist in `.cockpit_factbank.json` (or verbatim in the current file). Sibling pages are wording-flavor only — NEVER a number source. saakshe.html's "79 events · 3 actions" is FORBIDDEN in the cockpit.**
- Idle seats get richness from DESIGN (standing role · provenance · desk-flow · model), NEVER invented activity.
- Plain-grasp labels. Light + dark both flawless (new surfaces get the contrast walk in BOTH themes — dark recessed surfaces are the v2-816-failures zone).
- Soft Clay vocabulary only: Georgia display moments, Helvetica body, mono eyebrows, tint washes, recessed wells (surface-2), shadow depth, rgba-white pills, accent ring selection. No new fonts, no Google Fonts.

## 0.5 · THE PER-SEAT CANON TABLE (authored by the orchestrator from the fact bank — BINDING)
Builder uses EXACTLY these content hooks. "today:" = quote/compose from these verbatim in-file facts.
"role:" = standing-role line for idle seats (flavor wording, NO activity claim, NO numbers).
"prov:" = reads/feeds line — only where stated in CONNS/copy. "whyClaude:" = one terse high-stakes line.
**Do NOT rewrite any twoWord/threeWord string in QDATA — the 2-word/3-word labels are user canon.**

### manas (knows)
- MIND KEEPER · working · today: "routed 12 fragments to 5 buckets" · prov: reads ← all six grants → routes to buckets
- DOCUMENT READER · working · today: "parsing brand deck, page 14 of 22" · prov: reads ← document vault → canon bucket
- VISUAL READER · idle · role: "tags the visual library as brand assets land" · prov: reads ← brand assets → look bucket
- VOICE READER · idle · role: "transcribes founder notes into the voice bucket" (no conn line — none stated)
- SENTIMENT READER · working · today: "scanning 38 new social comments" · prov: reads ← social feeds (X + Instagram) → voice bucket
- MEMORY CURATOR ◉Claude · working · today: "verified 6 citations, flagged 1 conflict" · whyClaude: "high-stakes — citation integrity" · prov: commits → Context Pack (versioned)
- FOUNDER VOICE ◉Claude · idle · role: "answers as the founder, only from stored knowledge" · output: "founder-essence card: direct-trade conviction, cited to about-page + email-32" · whyClaude: "high-stakes — speaks as you"

### arivu (decides)
- MEETING CALLER · idle · today: brought "Raise Sundara Pro to $39?" to the table
- REVENUE LENS · idle · today: "$34 holds gross margin at target" · prov: reads ← Stripe · RevenueCat
- GROWTH LENS · idle · today: "dissents — wants a kept $29 tier (on the record)"
- BRAND LENS · idle · today: "consistent with the value promise" · prov: reads ← memory (Pack v15)
- CHURN HUNTER · idle · today: "caught the cliff at $39 — curve breaks past ~$36"
- OPERATIONS LENS · idle · today: "rollout effort low · 30-day notice"
- VERDICT MAKER ◉Claude · idle · today: "reconciled the dissent — sealed Raise to $34, defensibility 0.84" · whyClaude: "high-stakes — verdict synthesis"
- VERDICT BREAKER ◉Claude · idle · today: "stress-tested the seal — the prosecution" · whyClaude: "high-stakes — adversarial stress-test"
- ORDER DISPATCHER · working · today: "A2A dispatch — price-change order → kalai + kural" · prov: change-commit ASKED — runs only on your grant

### kalai (makes)
- STUDIO DIRECTOR ◉Claude · idle · today: "scoped the launch brief — one brief, multi-platform pack" · whyClaude: "high-stakes — owns the brief"
- VISUAL MAKER · idle · today: "rendered banner master v3" · prov: makes via ← Generative AI MCP (example)
- WORD SMITH · idle · today: "drafted the launch caption"
- BRAND CHECK · idle · today: "scored the loop 6.8 → 8.4 → 9.1 — two regenerations"
- LEGAL CHECK ◉Claude · idle · today: "compliance-cleared master v3" · whyClaude: "high-stakes — can we say this safely" · prov: cleared master → handoff to kural

### kural (engages)
- ENVOY LEAD ◉Claude · idle · today: "qualifying an inbound prospect — a warm buying question" · whyClaude: "high-stakes — leads the only mouth"
- PROSPECT SCOUT · working · today: "fanning parallel research across wholesale cafés"
- MARKET WATCHER · working · today: "tracking competitor moves"
- OUTREACH WRITER · idle · today: "3 tailored emails drafted, fact-checked @0.8"
- CLAIM JUDGE ◉Claude · idle · today: "verifies every outreach fact — the @0.8 gate" · whyClaude: "high-stakes — nothing unverified leaves"
- EMAIL ENVOY · waiting · today: "sent · 1 meeting booked — awaiting send clearance"
- CHANNEL MOUTH · waiting · today: "holding the publish gate — master v3 at 9.1 waits on your tap" · prov: holds the keys → X + Instagram

### Desk side panels (the desk in today's story — reuse existing canonical blocks):
MIND KEEPER → 12-fragments line + 8-bucket mini-grid + compaction line · SOURCE READERS → imbibe pipe + grant-per-reader (CONNS) · MEMORY CURATOR → citations + Pack v14→v15 commit + cited·versioned legend · FOUNDER VOICE → founder-essence output + answers-with-citations · MEETING CALLER → the docket question + resolution path · ADVISOR COUNCIL → five-lenses pipe verbatim · VERDICT BENCH → verdict (Georgia headline) + 0.84/0.88 metrics + dissent block · ORDER DISPATCHER → A2A dispatch + change-commit ASKED + resolution ledger · STUDIO DIRECTOR → multi-platform pack + handoff line · MAKER DESK → fidelity loop + master v3 + workspace-temporary pairing · BRAND CHECK → loop steps + "two regenerations · $0.10 each" · LEGAL CHECK → compliance-cleared + no-channel-keys identity · ENVOY LEAD → warm-prospect context + qualifying line · RESEARCH DESK → scout/watcher + 3-cafés outcome · MESSAGE DESK → outreach pipe + @0.8 · CHANNEL DESK → BOTH live gate cards (SHARED STATE — same data-gate wiring) + channels×scopes mini.

### Desk-flow strips (structural truth from DESKDATA order; THIS DESK highlighted w/ quadrant tint):
manas: granted sources → SOURCE READERS → MIND KEEPER → MEMORY CURATOR → buckets → FOUNDER VOICE answers
arivu: MEETING CALLER → ADVISOR COUNCIL → VERDICT BENCH → ORDER DISPATCHER → your tap
kalai: STUDIO DIRECTOR → MAKER DESK → BRAND CHECK → LEGAL CHECK → handoff → kural
kural: ENVOY LEAD → RESEARCH DESK → MESSAGE DESK → CHANNEL DESK → the world (your gates)

## 1 · FRONT A — DESK-DRILL DOSSIERS (the biggest gap: all 16 drills starved)
Today `drillDesk` = bare seat cards floating in a void (a 1-seat desk shows ONE tiny card in an empty stage). Rebuild the drill as a full-stage **dossier spread**, same recipe all 16, derived 100% from existing data:

- **Header row**: backchip · desk name (quadrant hue, Georgia 22px) · italic subtitle · `n seats · n on Claude` pills.
- **Desk-flow strip** (constrip DNA, full width): where this desk sits in its quadrant's pipeline — `upstream → THIS DESK → downstream` with icons + the quadrant's verb. Derivable: manas SOURCE READERS → MIND KEEPER → MEMORY CURATOR → buckets → FOUNDER VOICE; arivu MEETING CALLER → ADVISOR COUNCIL → VERDICT BENCH → ORDER DISPATCHER; kalai STUDIO DIRECTOR → MAKER DESK → BRAND CHECK → LEGAL CHECK → handoff → kural; kural ENVOY LEAD → RESEARCH DESK → MESSAGE DESK → CHANNEL DESK → the world. THIS DESK highlighted (accent ring / tint wash).
- **Main panel (~62%) — seat dossiers**: one card per seat (grid, minmax(0,1fr) tracks). Each dossier:
  - status dot + TWO-WORD name (mono) + model mark (ring = Claude·Vertex / dot = Gemini)
  - italic three-word subtitle
  - **today / standing block**: working seats quote their canonical activity VERBATIM from the file (Document Reader "parsing brand deck, page 14 of 22"; Churn Hunter "caught the retention cliff at $39 — curve breaks past ~$36"; Outreach Writer "3 tailored emails drafted, fact-checked @0.8"…). Idle seats get a STANDING ROLE line (derived from threeWord + noscript copy, no activity claim) + a quiet "idle — wakes when …" line ONLY where the trigger is already stated in-file (e.g. Email Envoy "awaiting send clearance", Channel Mouth "holding publish gate").
  - **reads/feeds provenance line** where stated in-file: Revenue Lens ← Stripe·RevenueCat; readers ← their granted source (CONNS); Channel Mouth → X+Instagram; Founder Voice "answers with citations ← buckets".
- **Side panel (~38%) — the desk in today's story**: reuse existing canonical blocks, matched per desk: ADVISOR COUNCIL → the five-lenses pipe; VERDICT BENCH → verdict + 0.84/0.88 metrics + dissent; SOURCE READERS → imbibe pipe; MEMORY CURATOR → citations + Pack v14→v15; MAKER DESK → fidelity loop + master v3; CHANNEL DESK → the two live gate cards (shared state!); MESSAGE DESK → outreach pipe steps; RESEARCH DESK → scout/watcher lines + 3-cafés outcome; MIND KEEPER → buckets mini + 12-fragments line; FOUNDER VOICE → "answers as the founder, only from stored knowledge" + citation line; ORDER DISPATCHER → resolution path + A2A dispatch line; MEETING CALLER → docket question line; BRAND CHECK/LEGAL CHECK → their loop/clearance lines + handoff. Bottom of side panel: "where it goes next" line (margin-top:auto).
- **Fill contract**: every desk drill ≥70% stage fill at all three viewports (1-seat desks fill via the two-panel spread). Distributed-ink (space-between, margin-top:auto footers), never stretch-bloat.

### BASELINE (v9 harness, measured 2026-06-07): ALL drills fail fill today —
desk drills 23.3% · manas/memory 30.1% · arivu/docket 43.6% · connections 31.9–57.5%. So **connections drills + memory + docket are in scope too**: distribute permlist rows (space-between), enrich side panels to full height (same allow-list discipline), pull their fill ≥70%. Everything else measured CLEAN at baseline (0 overlap / 0 clip / 0 edge-band / 0 orphan / 0 JS errors) — keep it that way.

## 2 · FRONT A½ — SYMMETRY DRILLS (kalai + kural work panels currently dead-end)
manas→`memory` and arivu→`docket` exist; add:
- **kalai/studio**: full loop story (6.8→8.4→9.1 with what changed between regens — ONLY if stated in file/factbank; else the loop + scores), master v3 + multi-platform pack output, workspace-temporary card + manas permanent-log pairing, backends choice row. All existing content, recomposed at full-stage depth.
- **kural/outreach**: outreach pipeline + channels×scopes matrix + BOTH gate cards (shared state) + posted-reply output + held-reply detail. Existing content.
Register in router (`#kalai/studio`, `#kural/outreach`), work panels get the drill affordance (backchip-style link like manas/arivu have), Esc/back work, harness NAMED_DRILLS updated.

## 3 · FRONT B — ACTIVITY VIEW (rows stretched over voids)
Keep the 12 canonical events EXACTLY. Recompose as **the day in phases** (mono eyebrow phase bands): NOW WORKING (now/2m/9m imbibe) · THE VERDICT (18m·22m) · THE MAKING (34m·41m·44m) · THE ENGAGING (52m·58m) · THE COMMIT (1h). Rows become click-targets → their quadrant (router). Each row: time · quadrant dot · event · cost (where stated) · chevron. Add a compact day-summary header strip (12 events · 2 gates · $4.18 / $40 · Pack v15 — all canon). 2-column phase layout to fit 1512×860 with zero scroll; fr-distributed so it FILLS at 1090.

## 4 · FRONT C — CHAT DEEPENING (right rail gets more power) — auditor-verified package
Keep: structured renderer, 4 existing replies + SEED verbatim, the 4 existing quick chips, QDATA.chatScript untouched (noscript reading).
1. **`qans:` chipAct branch (P0)** — chat can now make the held-reply decision: `if(act.indexOf('qans:')===0){ var pp=act.slice(5).split('|'); answerQuestion(pp[0], pp[1]); syncChatChips(); return; }` — question text + option VERBATIM from QDATA. R_WAITING's "go to the held reply" gains siblings: "reply publicly — own it" / "move to DM" qans: chips (answering kural Q1 clears gate 2 + ALL mirrors via the existing answerQuestion path).
2. **Trigger order (P0)** — respond() tests SPECIFIC before BROAD, exact order: help/what is saakshe → R_HELP · memory/pack/imbibe → R_MEMORY · banner/brand/fidelity/master → R_BANNER · dissent/growth/29 → R_DISSENT · reporter/reply/held → R_REPLY · outreach/cafe/wholesale/meeting → R_OUTREACH · channel/linkedin/instagram/dm/key → R_CHANNELS · question/decide → R_QUESTIONS · THEN the broad four (waiting → cost → why → status) · fallback. Every `ask:` chip label must contain its own trigger keyword.
3. **New structured replies** (leads from the auditor's audited copy — every number canon; chips through existing dispatch): R_MEMORY (Pack v14→v15, 8 buckets, p14/22, 38 comments, 6 cited·1 conflict → chips: open memory `nav:manas/memory`, → manas) · R_BANNER (6.8→8.4→9.1, $0.10 each, master v3, compliance-cleared, at gate → chips: → kalai, full studio story `nav:kalai/studio`, approve & publish) · R_DISSENT (kept-$29 tier, on the record, cliff at $39/~$36, 0.84/0.88 → chips: open the docket) · R_REPLY (held · sensitive, reporter, your call → qans: both options + open in kural) · R_OUTREACH (3 cafés, 1 booked, @0.8 → chips: → kural, full outreach story `nav:kural/outreach`) · R_CHANNELS (X posts·replies·listen, DMs off, IG listen-only, LinkedIn off, email 3 sent/1 booked → chips: channels×scopes `nav:kural/connections`) · R_QUESTIONS (**built at submit-time** — live STATE.openQ + gateOpen() → chips: questions view, taps tab) · R_HELP (witness identity, four quadrant pills, capability chips).
4. **`prov` field on replies** — optional provenance string rendered as a muted .rprov line between pills and chips (provenance-on-surface): R_WHY → "grounds: live numbers ← Stripe · RevenueCat + Context Pack v15" · R_COST → "on your keys · sums to $4.18 = 1.92 + 2.06 + 0.20" · R_BANNER → "compliance-cleared by Legal Check (Claude)". Verbatim sources only.
5. **State-aware**: R_WAITING/R_STATUS built at submit-time reflecting STATE.gates (both cleared → "nothing waiting — the day is yours" variant; publish done → past-tense). Conditional TEXT only; canon numbers unchanged. syncChatChips extends to `qans:` chips (REPLY_Q answered → those chips flip done) AND renders already-resolved state correctly for NEW bubbles (check STATE at render).
6. **2 new quick chips** (keeping the 4): "what's in memory?" → R_MEMORY · "what is saakshe?" → R_HELP.
7. **Taps tab**: provenance line under each gate (publish → "master v3 · brand-fidelity 6.8 → 8.4 → 9.1 · compliance-cleared"; reply → "resolution /resolutions/sundara-pro-pricing-2026-06 · grandfather clause"); post-approve the line swaps to past-tense confirmation; both-cleared → quiet all-clear line. **Today tab**: add $4.18-of-$40 meterbar + per-quadrant proportional mini-bars (meterrow CSS exists), quadrant rows clickable → quadrant view; provtag stays.

## 5 · FRONT D — MISC UI UPGRADES (audit-accepted, all light-touch)
- **Quadrant identity in drills**: the desk-flow strip (and drill anchor headers) carry the quadrant --tint-* wash, same move as overview ovcards (verified safe in dark — tints are warm-dark). Wash on SURFACE only, never an edge.
- **Georgia display anchor per drill**: one display-face focal point per drill stage (desk name ~26px, or the canonical headline: docket "Raise to $34", memory "v14 → v15"). Matches loved vtitle treatment.
- **Seat dossier model-foot**: recessed well at card foot carrying model mark + whyClaude (Claude pair visually distinct via existing .ring); inset-shadow recess (light surface-2≈bg, so use inset shadow + hairline for depth), contrast-walked both themes.
- **Drop the duplicated status word** in seat .smeta (dot carries it); reclaim the line for today/role/prov content. Desk drill header echoes the desk card's at-a-glance meta (status dot · n seats · rings) to kill the density cliff.
- **Activity**: .frow flex:0 0 auto (stop equal-stretch); phase grouping via mono eyebrow bands (NOW WORKING / THE VERDICT / THE MAKING / THE ENGAGING / THE COMMIT); fill the empty .fc gutter with canonical per-row provenance (verdict → "def 0.84 · conf 0.88", commit → "v14 → v15", outreach → "@0.8", regen rows keep $0.10); rows clickable → their quadrant; day-summary strip (12 events · 2 taps · $4.18 / $40 · Pack v15). 12 events VERBATIM.
- **Connections drills**: distribute permrows (space-between to panel bottom); balance right panels — manas gains the read-only-no-write-back recessed footer; kalai gains the no-channel-keys provenance block + example-connected/2-empty-slots state. Fill ≥70%.
- **constrip provenance symmetry** (loved surface, additive only): short CSPROV labels — manas "six grants → six buckets" · kalai "memory ← manas · master → kural" · kural "X + IG listen · email sender". Verify fit at 1280 wide.
- **Overview, one string**: OVSTATUS kalai three → "master handed off" (keep 3-word discipline). NOTHING else on overview changes.
- **MEASURED contrast fix**: `.nav.active .nq` red = 4.05:1 on active wash (light) — scoped darker red (along terracotta's own hue) to ≥4.5; dark re-checked.
- **Harness exemption (already patched)**: `.navini` initials skipped in contrast walk (sibling-dot false positive; user-approved at 11px). Do NOT redesign the initials.
- **MEASURED contrast fix**: sidebar `?n` red (`.nav.active .nq`) = 4.05:1 on the active wash (light) — darken `--sig-red` usage there along its own hue to ≥4.5 (the v4 contrast-nudge pattern). Verify with the harness, both themes.
- **Harness exemption (documented)**: `.navini` collapsed-rail initials are white-on-quadrant-dot (the dot is a SIBLING, so bg-walk composites against the sidebar — false positive). User-approved at 11px (v7 verification). Probe: skip `.navini` in the contrast walk with an inline comment; do NOT redesign the initials.

## 6 · VERIFY CONTRACT (the v9 harness — already written, /tmp/cockpit_v9_perception.mjs)
- Phase 0 SELF-VALIDATION: planted-bad nodes; EVERY assertion class (contrast/overlap/clip/edge-band/orphan/void/chat-contrast/chat-clip) must fire, then clean after removal. New assertion classes added later get their own planted-bad.
- Phase 1 matrix: 1512×860 · 1736×1090 · 1920×1080 × light/dark × sidebar expanded/collapsed × every view + ALL 16 desk drills + memory/docket/studio/outreach + 4 connections + rail tabs. Route-miss guard (router silently falls back — a drill that lands on a top view is a FAILURE not a pass). Fill: top ≥75%, drills ≥70%. Zero JS errors.
- Behaviors script (separate): question commit (badges 8→7 everywhere), gate approve sync (chat chip + pills + taps + kural + overview), EVERY new chat trigger fires, every chip navigates/commits + mirrors sync, new drills back/Esc, theme persist, re-imbibe ack, noscript intact, reduced-motion.
- Boot-guard: page boots 0-errors BEFORE critics run.
- Screenshots → `.cockpit_shots/v9_*`; gallery to user.

## 6.5 · MF1 FIX (post-critique, 2026-06-08) — drill stretch-bloat
Perception critic mustFix MF1: 1–2-seat desk drills showed a tiny card floating at top of the seat panel + bare void below + footer floating at bottom. ROOT: span-based fill (maxBottom−minTop) read 95% because the footer pins to the bottom — the metric couldn't see the mid void. FIX:
- Seat dossier cards STRETCH to fill their column (`.sdwrap` flex-col + `.sdgrid` align-content:stretch + grid-auto-rows:minmax(min-content,1fr)); `.sdoss` body wrapped in `.sdbody` (flex:1, justify-content:center) so a tall single card reads header-top / detail-centered / model-foot-bottom — a composed dossier, not a hole.
- Story side panels (`.sidebody`) CENTER their content group (justify-content:center) so leftover height splits evenly top+bottom (max bare = half) instead of pooling into one bottom void. SOURCE READERS gained a canonical grant→bucket krows block.
- NEW HARNESS ASSERTION (density): per-drill-panel SURFACE coverage — slice pbody into 20px bands, a band is covered by a content-box OR text; seat panels must have max-bare-band < 140px, any drill panel < 420px. SELF-VALIDATED (planted a top-pinned seat card → fires). This is the metric that catches what span-based fill missed. Re-run: Phase-0 9/9 classes fire, Phase-1 384 states 0 findings.
- Re-critic (fresh eyes): MF1 RESOLVED across all 18 drills, no regression, dark clean. Residual: 1-seat cards stay airy (thin canonical content) — NOT a must-fix (zero-invention limit); SURFACED to user as a tighten-or-leave choice.
- **Harness scope (transparent):** the density gate is scoped to the 16 DESK drills (.drillspread) where MF1 lived and the metric is calibrated. The 6 named drills (memory/docket/connections/studio/outreach) anchor content at BOTH top and a margin-top:auto bottom element, so their mid-gap is breathing room, not a tail void — the band metric over-flags that "content-both-ends" layout (the advisor's predicted false-positive); they rest on the span-fill check + the re-critic's eye (verified "full, no void"). 22 drills total: 16 machine-gated, 6 eye-verified.
- Hard-rules shouldFix: `.nq` red unified to one contrast-darkened `--nq-red` everywhere (dead `--sig-red` dup deleted). FLOW end-label got right padding.

## 7 · NOSCRIPT + META
noscript paragraphs updated to mention the dossier depth + new drills + chat powers (same plain-words voice, same canon). Title/meta unchanged.

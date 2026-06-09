# saakshe — Agentic Depth + the arivu-primitive (design spec)

**Date:** 2026-06-09 · **Status:** APPROVED shape — ready for `brainstorming → writing-plans → ultracode workflows + TDD.**
**This is the SECOND build phase.** The first (credit/auth/multi-tenancy) is DONE + pushed; this phase makes the
agents actually *think*. Build ultracode (workflows) + TDD. saakshe must stay **ZERO-aikizi** (study aikizi only).

---

## 0 · Current state (READ FIRST)

**What saakshe is:** one FastAPI service (`service/app.py`) serving a Brut/Obsidian website (`web/*.html`: landing `/`,
cockpit `/cockpit.html`, faculty pages) + JSON APIs + `/ws/voice`, over four real-ADK quadrants (**manas** knows ·
**arivu** decides · **kalai** makes · **kural** engages) + the **witness** (saakshe), driven by a resumable **2-gate
flywheel** (`orchestrator.py`).

**Repo:** `~/Desktop/Working/saakshe` — git, pushed to **`Bashocodes/saakshe`** (private, SSH remote, in sync,
clean tree, 15 commits, no secrets tracked). Run locally: `PYTHONPATH=. ./.venv/bin/uvicorn service.app:app --port 8000`.

**Tests (all green, KEEP THEM green):** root `PYTHONPATH=. ./.venv/bin/pytest` · quadrants
`pytest manas/tests kalai/tests kural/tests` · arivu `cd arivu && PYTHONPATH=. ../.venv/bin/pytest tests/`.
Total **213** (135 original demo/file-store baseline that must stay byte-identical + 78 from phase 1).

**Phase 1 — DONE (do not rebuild):** Supabase Google auth (ES256 JWKS, `common/auth.py`), per-user multi-tenancy via a
request-scoped `contextvars` store (`common/project.current_store()`), production credit system (`common/credits.py` +
live migrations on Supabase ref `mttlgjztpkzcklbiqkxj`: `accounts`/`transactions`/`pending_changes`, idempotent
`saakshe_spend`/`saakshe_refund`/`saakshe_grant_signup`), `SupabaseEventStream`, manas-edit → `pending_changes`, cockpit
sign-in + balance. Spec: `docs/superpowers/specs/2026-06-09-saakshe-credit-auth-multitenancy-design.md`; plan:
`docs/superpowers/plans/2026-06-09-saakshe-credit-auth-multitenancy.md`. Deploy is gated on the founder's console steps
(`DEPLOY_CHECKLIST.html`) — NOT this phase's concern.

**The companion docs to read for context:** `~/Desktop/Working/saakshe_future_scope.html` (the founder's vision +
the exact Brut/Obsidian design system) and `~/Desktop/Working/saakshe_status.html` (the honest depth board this spec
operationalizes). Both are OUTSIDE the repo (analysis docs).

---

## 1 · The honest assessment (why this phase exists)

Scaffold + infra ≈ **80%** (real flywheel, real ADK orchestration, model split, the live credit/auth layer). Agentic
**depth ≈ 30%.** Net product ≈ **40%.** The structure is real; the depth is the work. **Only manas's repo→company
extraction reaches the depth bar** (real imbibers git-clone the repo + fetch the site → cited facts). Every other
faculty has the right skeleton and **one shallow pass.** Closing that — plus one role fix — is this phase.

**The depth bar (the aikizi /decode principle, the founder's canon):** ONE source → ~10 staggered parallel specialized
calls (150ms apart, allSettled → latency = slowest call) → ~8 attribute classes → one reassembled, cited whole. NEVER
one shallow pass. Every faculty must imbibe/decide this way.

---

## 2 · Audit findings (code-grounded, 2026-06-09 — concrete, do not re-derive; verify if unsure)

**manas (KNOWS) — depth 3/5 — role CLEAN — NOT launch-critical to deepen.** Real seats: `mind_keeper`,
`imbiber_repo/web/docs` (real AI over real cloned/fetched sources), `memory_curator` (Claude verify-before-commit).
Gaps: (a) **social imbiber is a STUB** — `runner._read_one(kind='social')` returns `"Primary social presence: {ref}."`,
no real scrape; (b) **no brand-asset VAULT** — `brand_rules` is `list[str]` text only; (c) **one generalist call per
source**, not the decode fan-out; (d) the default A2A `_ask_founder_voice` is a 4-char-stem keyword match + template,
NOT the real Claude `founder_voice_agent` (which exists but only on `ask_founder_voice_live()`, off the critical path);
(e) the real `ingest_connected` path computes groundedness once (round_=2 hardcoded), the curate LoopAgent mostly runs in
demo.

**arivu (DECIDES) — depth 2/5 — role PERFECT — LAUNCH-CRITICAL.** 9 real LLM seats (`chair_frame`, 5 mantris on Gemini,
`debate_moderator`, `chair_synthesizer` Claude·Vertex, `prosecutor` Claude·Vertex). Right orchestration
(Parallel+Loop+HITL+Executor), right model split, clean separation. BUT each seat is **one shallow pass**: mantris are
solo single-turn (no sub-agents); grounding is **static fixtures fed once at frame time**; debate re-runs from unchanged
state; the **prosecutor does a crude full re-synthesis** on fail (not a graduated "strengthen reason #2" loop). arivu IS
the decision engine — depth here is the centerpiece.

**kalai (CREATES) — depth 2/5 — role in-lane but ECOSYSTEM-split — LAUNCH-CRITICAL.** Seats: `creative_director`
(Claude), `producer_designer` (Gemini), `producer_copy` (Gemini), `brand_fidelity_scorer`, `compliance_gate` (Claude,
fail-closed). Gaps: (a) **designer outputs JSON specs, NOT pixels** even in live — the "Imagen" stream label is
cosmetic, `sub_agents.py` has no `tools=`; (b) **hardcoded demo fidelity climb 6.8→8.4→9.1** over one canned campaign;
(c) **no claim citations** in the creative; (d) single-pass per concern. kalai stays in lane, but copy is authored in
TWO places (see kural).

**kural (ENGAGES) — depth 2/5 — role VIOLATION CONFIRMED — LAUNCH-CRITICAL.** Seats: `envoy_lead` (Claude),
`research_prospect`/`research_market` (Gemini scouts, call local math tools), `outreach_writer` (Gemini),
`claim_judge` (Claude LLM-as-judge), + deterministic `claim_check`/`gate`. **VIOLATION:** `outreach_writer`
(`kural/sub_agents.py` ~153-160, `prompts.py` WRITER, `demo_fixtures.py` `_DRAFT.channel_variants`) authors per-channel
copy (x/ig/linkedin) — that is **kalai's exclusive lane**. Also: grounding is **fixture-bound even in live mode**
(`grounding.fetch_grounding()` always starts from `DEMO_GROUNDING`, only swaps the pack version label); writer/judge have
**no MCP read-tools**; scouts apply local formulas to fixture numbers, don't read live sources; 2 "channel desk seats"
are narration-only (oversells the agent count). Correct: tap-2 HITL, channel keys held, dry-run by default.

**saakshe (WITNESSES) — depth ~2.5/5 — role CLEAN.** Real 5 telemetry readers + refuse-by-default + Gemini-Live voice.
Vision wants ~12 readers/tick + full voice parity. Casts nothing. Fine for now.

---

## 3 · The architecture: arivu is a PRIMITIVE, not a place (the founder's correction — central to this phase)

Each faculty already has its OWN arivu — a decision gate — just shallow + unnamed. **The deciding factor differs**, so a
single shared chamber is wrong; instead, build the chamber ONCE and instantiate it per faculty:

| faculty | its arivu (today, shallow) | deciding factor | gate |
|---|---|---|---|
| manas | curator · groundedness check | is it **true/cited** enough to commit? | ≥0.80 grounded |
| kalai | brand-fidelity loop + compliance | is it **on-brand + cleared**? | fidelity ≥8.5 · fail-closed |
| kural | claim-judge + send-eligibility | is it **supported + safe to send**? | claim ≥0.80 · tap-2 |
| company | 5-mantri chamber (deep, green) | is it **defensible**? | ≥0.80 · tap-1 |

**The `chamber` primitive:** `frame → fan out a domain panel (parallel specialist advisors, cited) → Claude verdict →
adversarial prosecutor (graduated loop until it survives the threshold) → gate`. Signature shape:
`chamber(panel, deciding_factor, threshold, human_tap=False)`. The company instance sets `human_tap=True` (tap-1); the
per-faculty instances are automated, fail-closed (no tap). **Same primitive, the tap is one flag.** Extract it from the
existing (deep, green) company arivu so it's a recognition + generalization, NOT a rewrite.

**Why separation (fix #1) must come first:** an arivu can only hold ONE clean deciding factor if the faculties are
cleanly separated. While kural authors copy, its gate judges two things at once (is the copy good? + is it safe to
send?). Fix #1 → each faculty's arivu gets exactly one question.

**The separation contract (the vision, non-negotiable):** manas KNOWS (creates/ships/decides nothing) · kalai CREATES
(authors ALL creative incl. caption + every channel variant, holds no channel keys, ships nothing) · kural ENGAGES
(carries/schedules/replies, AUTHORS NOTHING, holds channel keys, publishes at tap-2) · arivu DECIDES (the chamber
primitive) · saakshe WITNESSES (telemetry only, refuses beyond, casts nothing). Two human taps only: tap-1 (arivu
verdict), tap-2 (kural publish). Fail-closed compliance. BYOK (founder holds Gemini · Claude-Vertex · channel keys).
The flywheel LEARNS each turn (kural results → manas's next Context Pack → arivu/kalai's next cycle).

---

## 4 · Build order (each step independently shippable + demoable; TDD; keep all 213 tests green)

### Track A — make it think (hackathon-critical)
1. **Separation fix (START HERE — pure refactor).** kalai authors the full `CreativeMaster` (caption + every channel
   variant, fact-checked in kalai's OWN fidelity loop). **Retire kural's `outreach_writer` + `claim_judge`**; kural reads
   the cleared master, schedules, and publishes it UNTOUCHED. One authoring lane. Update the `CreativeMaster` a2a
   contract + kalai/kural runners + demo fixtures + tests. This gives every arivu one clean deciding factor.
2. **Extract the `chamber` primitive + deepen the company arivu.** Pull `chamber(panel, factor, threshold, human_tap)`
   out of the company arivu. Deepen the company instance: each mantri → a small parallel ensemble (e.g. economist →
   margin · retention · competitor-bench, each a specialized grounded call); wire live grounding; make the prosecutor
   graduated (gaps → chair revises that reason → re-prosecute, not a full reset).
3. **kalai real media.** Wire the designer to **Vertex Imagen / Veo** so a brief yields real pixels + video, not a JSON
   spec. Decompose the single fidelity score into specialized scorers (brand-consistency · voice-tone · platform-fit ·
   compliance-edge) — i.e. kalai-arivu's panel. Source the fidelity climb from real scored runs, not the hardcode.
4. **kural live grounding.** Stop starting from `DEMO_GROUNDING`; fetch the real manas Context Pack + give the
   scouts/judge read-tools over live funnel/audience/feed. Refactor scouts into parallel-deep readers
   (consent · reach · topic-fit · timing) = kural-arivu's panel.
5. **manas's senses.** Replace the social STUB with a real handle read; route founder-voice through Claude on the default
   path; split each imbiber into 3–4 specialized sub-calls (claims · voice-semantics · brand-visual · contradiction
   pre-check) so a single source yields depth = manas-arivu's panel made real.

### Track B — make it a company (the SaaS moat)
6. **The brand-asset VAULT** — real logos/palettes/fonts/model-refs/prior-creatives, indexed + versioned + queryable
   (Supabase Storage or R2). kalai consumes it; manas PROACTIVELY serves it before the ask. The most product-defining
   piece in the vision.
7. **The learning flywheel** — kural's results (reach·reply·convert) feed manas's next Context Pack → grounds arivu's
   next verdict + kalai's next brief. Smarter every cycle.
8. **arivu precedent reuse + prosecution panel** — index sealed verdicts as reusable precedent; replace the lone
   prosecutor with a panel arguing the null case. (Open call: does reusing a precedent skip prosecution?)
9. **witness parity + BYOK + token budgets** — voice parity with the cockpit; founder holds all keys; every faculty
   declares a token budget as a hard gate (the 10-call fan-outs and best-of-N cost real money).

Implement the chamber primitive ONCE (step 2) and reuse it in steps 3/4/5 — that is what makes every faculty deep without
five rewrites.

---

## 5 · Constraints (MUST)
1. **ZERO-aikizi** in the saakshe tree. Study aikizi (`/Users/cyberyogi/Projects/aikizi`) only as a reference for the
   decode fan-out PATTERN; rebuild clean with neutral names. (Real-media: prefer Vertex Imagen/Veo over any aikizi
   coupling.)
2. **TDD + production-grade.** Keep the 135 file-store/demo baseline byte-identical and all 213 tests green. Demo mode
   (no creds, file store) must keep running creds-free and free.
3. **Respect the separation contract** (§3) and the **two-tap** flywheel. Fail-closed compliance.
4. **Match the Brut/Obsidian design system** for any UI (tokens in `saakshe_future_scope.html`; per-faculty colors:
   manas amber `#E3A52B` · kalai red `#CC4632` · kural green `#3E8F5E` · arivu blue `#3551C8`).
5. **Token budgets:** deep fan-outs are expensive. Make each faculty's chamber declare + respect a budget. Use Gemini
   Flash for the panel advisors, Claude·Vertex for the verdict/prosecutor (the existing model split).
6. **Use workflows for the build phases; verify (run the suite) before moving on.** Demo tests can't catch live-only
   bugs — write at least one real-path test per chargeable/agentic change.

---

## 6 · Key facts
- Repo `~/Desktop/Working/saakshe` · GitHub `Bashocodes/saakshe` (private, SSH, in sync).
- Supabase project `saakshe` ref `mttlgjztpkzcklbiqkxj` (us-west-1) · service key `~/.saakshe_supabase_key`.
- GCP `gen-lang-client-0937789625` · gcloud `hello@aikizi.com` · Vertex (Imagen/Veo/Gemini/Claude) available; Claude·
  Vertex quota was pending → hybrid mode (`SAAKSHE_MODE=live` + `SAAKSHE_CLAUDE_MODE=demo`).
- Modes: `demo` (default, creds-free, scripted) · `hybrid` · `live`. Billing tracks `SAAKSHE_STORE=supabase` + a real
  non-owner (NOT model-mode) — so the file-store demo is free + billing is testable in scripted mode.
- Memory: `project_saakshe_credit_build` (phase 1 done), `project_saakshe_future_scope` (the vision separation-of-
  concerns), `reference_saakshe_supabase`, `feedback_aikizi_error_handling`, `feedback_saakshe_dark_theme`.

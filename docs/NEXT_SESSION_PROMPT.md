# Paste this into a fresh Claude Code session (run from `~/Desktop/Working/saakshe`)

---

ultracode

Build saakshe's **agentic-depth phase** — make every faculty actually *think*, not just orchestrate. The full,
self-contained, approved-shape spec is committed at:
**`docs/superpowers/specs/2026-06-09-saakshe-agentic-depth.md`** — read it FIRST; it has the current state, the
code-grounded audit of each faculty, the architecture, the build order, and the constraints. Also read the two
companion docs `~/Desktop/Working/saakshe_status.html` (the depth board) and `~/Desktop/Working/saakshe_future_scope.html`
(the vision + the exact Brut/Obsidian design system), and recall the memory entry **"saakshe credit/auth build"**
(phase 1 is DONE — do not rebuild it).

**The big idea (read the spec §3):** `arivu` is a **primitive, not a place.** Each faculty already has its own decision
chamber with a *different deciding factor* — manas decides *is this true enough to commit*, kalai *is this on-brand +
cleared*, kural *is this supported + safe to send*, the company arivu *is this defensible*. Build the chamber **once**
— `chamber(panel, deciding_factor, threshold, human_tap)` — extracted from the existing deep/green company arivu, then
**instantiate it per faculty** with a different panel + threshold. The company instance has `human_tap=True` (tap-1);
the per-faculty instances are automated, fail-closed. This one primitive is how every faculty reaches manas-grade depth
without five rewrites.

**Rules:**
- saakshe must stay **ZERO-aikizi** (study aikizi `/Users/cyberyogi/Projects/aikizi` only as a reference for the
  decode fan-out PATTERN; rebuild clean with neutral names; for real media prefer Vertex Imagen/Veo, not aikizi).
- **TDD + production-grade.** Keep ALL **213 existing tests green** (the 135 file-store/demo baseline must stay
  byte-identical; demo mode stays creds-free + free). Write at least one real-path test per agentic change — demo
  tests can't catch live-only bugs.
- Respect the **separation contract** + the **two-tap** flywheel + **fail-closed compliance** (spec §3). Honor the
  per-faculty **token budgets** (deep fan-outs are expensive: Gemini Flash for panel advisors, Claude·Vertex for
  verdict/prosecutor).
- Match the **Brut/Obsidian** design system for any UI (manas amber `#E3A52B` · kalai red `#CC4632` · kural green
  `#3E8F5E` · arivu blue `#3551C8`).
- Use **workflows** for the build phases; **verify (run the full suite) before moving on**; commit per step.

**Flow:**
1. Read the spec + companions + recall the memory.
2. If any design choice is genuinely open (the exact `chamber` API shape, the real-media provider, the per-faculty
   panel rosters), invoke **superpowers:brainstorming** (or a quick AskUserQuestion) to settle it with me first.
3. Invoke **superpowers:writing-plans** to turn the spec's build order (§4) into a phased, TDD plan.
4. Execute it with ultracode workflows + TDD, in the spec's order:
   **#1 SEPARATION** (retire kural's `outreach_writer` + `claim_judge`; kalai authors the full `CreativeMaster` —
   caption + every channel variant — fact-checked in kalai's own loop; kural reads + publishes it untouched) →
   **#2 extract the `chamber` primitive + deepen the company arivu** (mantris → parallel ensembles, live grounding,
   graduated prosecutor) → **#3 kalai real media** (Vertex Imagen/Veo + specialized fidelity scorers) →
   **#4 kural live grounding** (real Context Pack + read-tools + parallel-deep scouts) →
   **#5 manas senses** (real social signal, founder-voice through Claude, multi-call depth per source).
   Each step is independently shippable + demoable; verify the suite green before the next.
5. Track B (vault, learning flywheel, precedent reuse, witness parity, BYOK, budgets) follows — surface it but gate
   it behind Track A.

**Key facts:** repo `~/Desktop/Working/saakshe` (GitHub `Bashocodes/saakshe`, private, in sync) · Supabase ref
`mttlgjztpkzcklbiqkxj` (service key `~/.saakshe_supabase_key`) · GCP `gen-lang-client-0937789625` / `hello@aikizi.com`
(Vertex Imagen/Veo/Gemini/Claude available; hybrid = `SAAKSHE_MODE=live` + `SAAKSHE_CLAUDE_MODE=demo`) · run locally
`PYTHONPATH=. ./.venv/bin/uvicorn service.app:app --port 8000`. Don't worry about the deadline — the order holds either
way; every step is a real, demoable jump for the hackathon and the SaaS underneath it.

ultracode

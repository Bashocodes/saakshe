# saakshe — Agentic Depth: settled decisions + the chamber interface

**Date:** 2026-06-09 · **Status:** APPROVED (addendum to `2026-06-09-saakshe-agentic-depth.md`).
This records the four open design choices the parent spec deferred, plus the concrete
`common/chamber.py` interface, the demo-baseline contract, and the TDD cut for the build.
It does **not** restate the parent spec — read that first for current state, the audit, and §4 build order.

---

## A · The four settled choices (decided 2026-06-09)

1. **Chamber API — `common/chamber.py` factory.** Generalize arivu's proven 6-stage pipeline
   (frame → Parallel(panel) → debate Loop → Claude verdict → prosecutor Loop → gate) into ONE
   reusable **skeleton**. arivu refactors to call it; the three new faculty chambers instantiate it.
2. **kalai real media — Vertex Imagen (stills) + Veo (video), demo pixel-free.** Wired to
   live/hybrid only. Demo returns the JSON spec + a deterministic placeholder asset ref, so the
   demo baseline stays byte-identical and creds-free. ZERO-aikizi (study only). One real-path test
   exercises the Vertex client (recorded/mocked — not a live call in CI).
3. **Per-faculty panels — the `saakshe_future_scope.html` rosters as-is** (see §C).
4. **Demo baseline — "byte-identical" = published OUTPUT, tests may evolve.** The demo flywheel's
   user-visible result stays the same; faculty **unit tests that encode the OLD architecture**
   (kural `claim_judge`, writer-in-transcript) are legitimately rewritten/retired and replaced with
   new-contract tests. Net suite stays green; count may shift slightly. See §D for the precise line.

---

## B · The chamber primitive (`common/chamber.py`)

**Key constraint that shapes the signature (advisor-confirmed):** arivu's demo replay
(`arivu/arivu/models.py` → `from .demo_fixtures import scripted_payload`) and the faculties' replay
(`common.models._RESOLVERS[namespace]` via `register_demo`) are **separate registries**. Therefore
**`build_chamber` must NOT call any model factory.** It owns the deterministic skeleton; the caller
builds the LLM seats with its own factory/prompts/schemas/tools and passes them in. arivu passes
seats wired to arivu's replay → its 4 tests stay byte-identical. Faculties pass seats wired to
`common.models` → their replay routes through `_RESOLVERS`.

What `build_chamber` owns (the genuinely-reusable, fiddly ADK part): the topology, the three
control agents lifted out of `arivu/arivu/agent.py` (`DebateCheckAgent` / `ProsecutionCheckAgent` /
`GateAgent`), the loop wiring, **PROSECUTION_HISTORY / DEBATE_HISTORY accumulation**, the
escalate/rollback semantics, and the gate. All thresholds + the stop/rollback **predicate** are
injectable so arivu reproduces its exact `prosecution_should_stop` rollback and faculties take the
generic default.

```python
# common/chamber.py  — skeleton only; NO model factory call inside.
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from google.adk.agents import BaseAgent

@dataclass
class ChamberSpec:
    namespace: str                         # "arivu"|"kalai"|"kural"|"manas" — labels/stream only
    # ── caller-built seats (each side wires its own model + demo replay) ──
    panel: list[BaseAgent]                 # the parallel advisors (may be ensembles, see §C)
    verdict: BaseAgent                     # the synthesizer (a Claude seat)
    prosecutor: BaseAgent                  # the adversary (a Claude seat; graduated prompt)
    reviser: Optional[BaseAgent] = None    # graduated step: revises ONE reason between rounds
    frame: Optional[BaseAgent] = None      # chair/frame (or None)
    debate: Optional[BaseAgent] = None     # debate moderator (or None to skip the convergence loop)
    # ── deciding factor (the one question this chamber answers) ──
    score_key: str = ""                    # state key the prosecutor writes its [0,1] score to
    survived_key: str = ""                 # state key for the survived bool
    threshold: float = 0.80
    max_prosecution_rounds: int = 3
    # ── optional debate/convergence stage ──
    convergence_fn: Optional[Callable[[dict, int], float]] = None
    convergence_key: str = ""
    convergence_threshold: float = 0.0
    max_debate_rounds: int = 0
    # ── injectable control predicates (arivu passes its own; faculties take default) ──
    prosecution_should_stop: Callable[[float, int], tuple[bool, bool, str]] = _default_should_stop
    # ── frame-time grounding (live) ──
    grounding_callback: Optional[Callable[[Any], None]] = None  # before_agent_callback on `frame`
    # ── gate ──
    human_tap: bool = False                # True = halt for the founder (ONLY company arivu, tap-1)
    gate_status_key: str = ""
    gate_condition: Optional[Callable[[dict], bool]] = None      # default: survived_key is True
    # ── token budget (constraint #5 — RESERVED now, enforced Track B step 9) ──
    budget: Optional["TokenBudget"] = None # default None = no-op passthrough

def build_chamber(spec: ChamberSpec) -> BaseAgent:
    """SequentialAgent([frame?, ParallelAgent(panel), debate_loop?, verdict,
    graduated_prosecution_loop(prosecutor[, reviser]), gate]) — assembled from the
    caller's seats. The prosecution loop accumulates history and escalates on
    spec.prosecution_should_stop(score, round); the gate halts for a human iff
    spec.human_tap, else sets gate_status fail-closed from gate_condition."""
```

The `budget` field is reserved on the spec **now** even though enforcement is Track B — constraint
#5 makes it a MUST, and bolting it on later churns every call site (advisor flag).

---

## C · The four chamber instances (panels from `saakshe_future_scope.html`)

Each faculty's "arivu" answers exactly ONE deciding question (the separation fix #1 is what lets it).
Panels are caller-built seats passed to the same `build_chamber`. `human_tap=True` **only** for the
company arivu (tap-1); every per-faculty chamber is `human_tap=False`, fail-closed. The two human
taps stay exactly where they are: **tap-1** = company-arivu chamber gate; **tap-2** = kural's
publish gate (orchestrator-level, after kural's chamber).

| chamber | deciding question | panel (the fan-out) | verdict seat | adversary / fail-closed | threshold · gate |
|---|---|---|---|---|---|
| **company arivu** | is it **defensible**? | 5 mantris, each → a 3-advisor ensemble (e.g. economist → margin · retention · competitor-bench) | `chair_synthesizer` (Claude) | graduated `prosecutor` + `reviser` (Claude) | defensibility ≥ 0.80 · **tap-1** |
| **kalai** | is it **on-brand + cleared**? | brand-consistency · voice-tone · platform-fit · compliance-edge scorers (Gemini Flash) | `creative_director` aggregate (Claude) | `compliance_gate` fail-closed (Claude) | fidelity ≥ 8.5 · fail-closed |
| **kural** | is it **safe to send**? | consent · reach · topic-fit · timing deep readers (Gemini Flash) | `delivery_planner` (Claude) — picks variant×segment×window, **authors no words** | `send_eligibility` fail-closed (consent + value cap) | eligible · fail-closed (then tap-2 publish) |
| **manas** (per source) | is it **true / cited** enough to commit? | claims · voice-semantics · brand-visual · contradiction-precheck sub-readers (Gemini Flash) | `memory_curator` (Claude) | contradiction-gate fail-closed (groundedness → 0.0) | groundedness ≥ 0.80 · fail-closed |

Notes:
- **kalai** and **manas** already have a verify-loop shaped like the chamber; this *names* it and
  swaps the single scorer for the 4-advisor panel. The aggregate fidelity/groundedness must still
  reproduce the demo arcs (`[6.8,8.4,9.1]` → 9.1 ; round-1 under-grounded → round-2 commit).
- **kural** loses `claim_judge` entirely (separation fix). Its chamber decides DELIVERY, not copy:
  the 4 scouts → a delivery plan → `send_eligibility`. It never authors. The old `claim_support`
  threshold is retired with the writer/judge.
- **company arivu** is the only chamber that may halt for the founder.

---

## D · Demo-baseline contract (what "byte-identical" means here)

**Frozen byte-identical:** the credit/auth/file-store baseline; the demo flywheel's user-visible
**published output text** (after the separation fix, kural publishes kalai's exact `formats` — the
caption text the founder sees is unchanged); arivu's four tests through 2a.

**Legitimately evolves (replaced with new-contract tests):**
- kural `tests/test_claim_judge.py` → **retired** (judge removed).
- kural `tests/test_engage.py` → ~5 assertions that key on `CLAIM_VERIFIED`/`CLAIM_SUPPORT`/
  "Outreach Writer"/"Claim Judge" in transcript → rewritten to assert kural publishes kalai's
  `formats` untouched + the new scout/delivery transcript.
- kalai `tests/test_make.py:38` (`set(out["formats"]) == {"x","ig","linkedin"}`) → updated when the
  master gains a top-level `caption` field; the `[6.8,8.4,9.1]`/9.1 climb pins stay green.
- manas `tests/test_founder_voice.py` → contract (refuse-out-of-corpus, sync↔agent agreement) stays
  green; the default path now routes through Claude, and the demo resolver already returns the
  corpus-grounded answer so the contract holds.

Every chargeable/agentic change adds **one real-path test** (hybrid/live or recorded client), per
constraint #6 — demo tests can't catch live-only bugs.

---

## E · The TDD cut for step 2 (advisor-confirmed split)

- **2a — pure extraction.** Lift `DebateCheckAgent`/`ProsecutionCheckAgent`/`GateAgent` + loop
  wiring out of `arivu/arivu/agent.py` into `common/chamber.py`; rebuild arivu's `root_agent` on
  `build_chamber` with its **existing** seats/fixtures/predicates. Nothing observable changes.
  **Proof = arivu `test_chamber` + `test_rollback` + `test_threshold` + `test_executor` stay
  byte-identical green** (the existing suite IS the extraction harness). Keep
  `arivu.runner.deliberate/execute_decision/build_transcript` as the public surface so the
  orchestrator + `tests/test_flywheel.py` are untouched.
- **2b — deepen.** mantri → 3-advisor ensemble; live grounding at frame time; graduated prosecutor
  (`reviser` revises the one failing reason, re-prosecute — not a full reset), preserving the demo
  fixture's `PROSECUTION_ROUND::N` request-text keying so the 0.71→0.84 replay arc stays
  byte-identical. New tests for the depth.

**Verify-checks before locking the chamber signature:** (1) `test_rollback` + `test_threshold` are
in the 2a green set (they catch a generic stop predicate that doesn't reproduce arivu's
max-rounds-below-threshold → `VERDICT_SURVIVED=False` rollback); (2) graduated prosecutor keeps the
`PROSECUTION_ROUND::N` marker; (3) arivu's public runner surface is unchanged.

**Import structure (code-verified 2026-06-09 — no cycle).** 2a makes `arivu/arivu/agent.py` import
`common.chamber`. Safe: `common/__init__.py` (lines 14–19) only *adds* arivu's root to `sys.path` and
imports `a2a/config/models/stream` — it never imports arivu. So `import arivu` → `import
common.chamber` → `import common` (`__init__` runs: path-add + those four, no arivu) → no cycle. The
hard rule that keeps it acyclic: **`common/chamber.py` must never import arivu** (skeleton only). The
three lifted control agents parameterize precisely three things: the `SK.*` **state-key bindings**,
the **injectable predicates** (`convergence_fn`, `prosecution_should_stop`), and the **gate**
(`gate_status_key` / `gate_condition` / `human_tap`) — arivu passes its own `analyst.*` predicates +
its `StateKeys`, so 2a reproduces today's behavior exactly.

---

## F · Build order (unchanged from parent §4; with the 2a/2b split)

Track A (gate Track B behind it): **1 separation → 2a extract chamber → 2b deepen company arivu →
3 kalai real media → 4 kural live grounding → 5 manas senses.** Verify the full suite green before
each next step; commit per step; one real-path test per chargeable/agentic change.

At step 3, **verify live Vertex Imagen/Veo model IDs against current Vertex docs** before wiring
(`common/config.py` has no media model id yet; honor the check-model-versions rule). Add
`MODEL_IMAGEN`/`MODEL_VEO` to config.

Track B (6 vault · 7 learning flywheel · 8 precedent/prosecution-panel · 9 witness parity + BYOK +
**budget enforcement**) follows — surfaced, gated behind Track A.

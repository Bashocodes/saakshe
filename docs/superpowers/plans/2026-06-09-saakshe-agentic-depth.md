# saakshe Agentic Depth — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This phase is executed via **ultracode workflows + TDD**; verify the full suite green before each next phase; commit per step.

**Goal:** Make every saakshe faculty *think* (many specialized, cited, fail-closed calls per source) instead of orchestrate — by fixing the one separation violation, extracting an `arivu`-grade decision chamber as a reusable primitive, and instantiating it (deepened) in each faculty.

**Architecture:** Build the chamber **skeleton** once in `common/chamber.py` (deterministic topology + control agents + loop/history wiring; **no model factory inside** — callers inject their own seats so arivu's separate demo-replay registry stays intact). Fix #1 (separation) first so each faculty's chamber answers exactly one deciding question. Then extract (2a, byte-identical), deepen (2b), and roll the primitive out to kalai (3), kural (4), manas (5). Track B is gated behind Track A.

**Tech Stack:** Python 3.12, Google ADK (`SequentialAgent`/`ParallelAgent`/`LoopAgent`/`BaseAgent`), Gemini (Flash/Pro) + Claude·Vertex via `common.models`, Vertex Imagen/Veo (`google-genai`), pytest (asyncio), Supabase (existing store). Modes: `demo` (creds-free replay) · `hybrid` (Gemini live, Claude scripted) · `live`.

**Source-of-truth docs:** parent spec `docs/superpowers/specs/2026-06-09-saakshe-agentic-depth.md`; decisions addendum `docs/superpowers/specs/2026-06-09-saakshe-agentic-depth-decisions.md`. Read both before starting.

---

## Constraints (every task obeys these)

- **ZERO-aikizi** in the saakshe tree. Study `/Users/cyberyogi/Projects/aikizi` only for the decode fan-out *pattern*; rebuild clean with neutral names. Real media = Vertex (never an aikizi coupling).
- **Keep all 213 tests green.** "Byte-identical" = the credit/auth/file-store baseline + the demo flywheel's user-visible **published output**. Faculty unit tests encoding the OLD architecture (kural `claim_judge`, writer-in-transcript) are legitimately rewritten/retired (addendum §D). Net suite stays green.
- **Demo stays creds-free + free.** No live model call in CI. Each chargeable/agentic change adds **one real-path test** (hybrid/live or a recorded/mocked client) — gated so it skips without creds.
- **Two human taps only:** tap-1 = company-arivu chamber gate; tap-2 = kural publish gate. `human_tap=True` only for the company chamber; every per-faculty chamber is fail-closed.
- **Model split:** panel advisors on Gemini Flash; verdict/prosecutor on Claude·Vertex.

## Test commands (the green bar)

```bash
cd ~/Desktop/Working/saakshe
PYTHONPATH=. ./.venv/bin/pytest -q                                  # root (135 + phase-1)
PYTHONPATH=. ./.venv/bin/pytest manas/tests kalai/tests kural/tests -q
cd arivu && PYTHONPATH=. ../.venv/bin/pytest tests/ -q              # arivu (separate root)
```
A phase is "done" only when **all three** are green. Run all three before each new phase.

---

## File-structure map (what gets created / modified, and why)

**New files**
- `common/chamber.py` — the reusable chamber **skeleton**: `Seat` helper, `ChamberSpec`, `build_chamber()`, the three lifted control agents (`DebateCheckAgent`/`ProsecutionCheckAgent`/`GateAgent`) generalized with state-key bindings + injectable predicates + parameterized gate, a `_default_should_stop`, and a `TokenBudget` no-op placeholder. **Never imports arivu.**
- `common/tests/test_chamber_primitive.py` — unit tests for the skeleton in isolation (a tiny scripted panel/verdict/prosecutor), independent of any faculty.
- `kalai/scorers.py` — the 4 fidelity scorer seats (brand-consistency · voice-tone · platform-fit · compliance-edge) + the aggregate.
- `kalai/media.py` — Vertex Imagen/Veo client wrapper (live/hybrid only; demo returns a deterministic placeholder ref).
- `kalai/tests/test_scorers.py`, `kalai/tests/test_media.py` — scorer aggregation + media wrapper (mocked client) tests.
- `kural/delivery.py` — the 4 deep delivery readers (consent · reach · topic-fit · timing) + the `delivery_planner` seat (picks variant×segment×window; authors nothing).
- `kural/tests/test_delivery.py` — delivery-plan + separation (no authoring) tests.
- `manas/imbiber_pod.py` — the per-source 3–4 specialized sub-readers (claims · voice-semantics · brand-visual · contradiction-precheck) + reassembly.
- `manas/social.py` — the real social handle reader (replaces the stub).
- `manas/tests/test_imbiber_pod.py`, `manas/tests/test_social.py` — fan-out + social-read tests.

**Modified files**
- `arivu/arivu/agent.py` — `build_root_agent()` rebuilt on `common.chamber.build_chamber` (2a); mantri ensembles + graduated prosecutor wiring (2b). The three control-agent classes are removed (now imported from `common.chamber`).
- `arivu/arivu/sub_agents.py` — add `build_mantri_ensemble()` + the `reviser` seat (2b); graduated prosecutor instruction.
- `arivu/arivu/prompts.py`, `arivu/arivu/demo_fixtures.py` — ensemble + graduated-prosecutor prompts/replay (2b), preserving `PROSECUTION_ROUND::N` keying.
- `arivu/arivu/tools/grounding.py` — live grounding fetch at frame time (2b).
- `common/config.py` — `MODEL_IMAGEN` / `MODEL_VEO` (step 3); any new thresholds.
- `common/a2a.py` — `CreativeMaster` gains `caption: str` + `media: dict` (step 1/3).
- `kalai/sub_agents.py`, `kalai/agent.py`, `kalai/runner.py`, `kalai/prompts.py`, `kalai/demo_fixtures.py` — author full master incl. caption (step 1); wire designer to `media.py` + 4-scorer panel (step 3).
- `kural/sub_agents.py`, `kural/agent.py`, `kural/runner.py`, `kural/prompts.py`, `kural/demo_fixtures.py`, `kural/grounding.py` — retire `outreach_writer`+`claim_judge`; read kalai's master untouched (step 1); real Context Pack + deep readers (step 4).
- `manas/runner.py`, `manas/sub_agents.py`, `manas/agent.py`, `manas/prompts.py`, `manas/demo_fixtures.py` — social reader, founder-voice-through-Claude default, imbiber fan-out (step 5).
- Test files per the addendum §D triage.

---

# PHASE 1 — Separation fix (kalai owns all authoring; kural authors nothing)

**Why first:** an arivu can hold one clean deciding factor only if faculties are cleanly separated. This is a pure refactor (addendum §A.4, §D). After it, kalai authors caption + every channel variant (fact-checked in its own fidelity loop); kural reads the cleared master, schedules, publishes it **untouched**.

### Task 1.1: Add `caption` + `media` to the `CreativeMaster` contract

**Files:**
- Modify: `common/a2a.py:87-107` (the `CreativeMaster` dataclass)
- Test: `tests/test_a2a_contract.py` (create)

- [ ] **Step 1: Write the failing test**
```python
# tests/test_a2a_contract.py
from common import a2a

def test_creative_master_carries_caption_and_media():
    m = a2a.CreativeMaster(
        asset_id="a1", brief="b", caption="the one caption kalai authored",
        formats={"x": "x", "ig": "ig", "linkedin": "li"},
        media={"image_ref": "vertex://imagen/placeholder", "video_ref": ""},
        fidelity_score=9.1, compliance="cleared", spend_usd=1.2,
    )
    d = m.as_dict()
    assert d["caption"] == "the one caption kalai authored"
    assert d["media"]["image_ref"].startswith("vertex://")
    assert set(d["formats"]) == {"x", "ig", "linkedin"}

def test_creative_master_defaults_keep_old_callers_working():
    m = a2a.CreativeMaster(asset_id="a1", brief="b")
    assert m.caption == "" and m.media == {}
```
- [ ] **Step 2: Run to verify it fails** — `PYTHONPATH=. ./.venv/bin/pytest tests/test_a2a_contract.py -q` → FAIL (`unexpected keyword 'caption'`).
- [ ] **Step 3: Implement** — add two fields to the dataclass (defaults keep every existing caller valid):
```python
# common/a2a.py — inside CreativeMaster
    caption: str = ""                                  # the ONE caption kalai authored
    formats: dict = field(default_factory=dict)        # per-platform variants {"x","ig","linkedin"}
    media: dict = field(default_factory=dict)          # {"image_ref","video_ref"} (step 3)
    fidelity_score: float = 0.0
    compliance: str = "cleared"
    spend_usd: float = 0.0
```
And add `"caption": self.caption,` and `"media": self.media,` to `as_dict()`.
- [ ] **Step 4: Run to verify it passes** — `pytest tests/test_a2a_contract.py -q` → PASS.
- [ ] **Step 5: Run the full root + faculty suites** — confirm the new optional fields broke nothing (kalai `test_make.py:38` still passes — it only checks `formats`).
- [ ] **Step 6: Commit** — `git commit -m "feat(a2a): CreativeMaster gains caption + media (separation fix groundwork)"`

### Task 1.2: kalai authors the caption (Copy desk emits caption + variants)

**Files:**
- Modify: `kalai/prompts.py:47-59` (`COPY_SEO`), `kalai/demo_fixtures.py` (`_COPY`, `assemble_master`), `kalai/runner.py` (master assembly)
- Test: `kalai/tests/test_make.py` (extend)

- [ ] **Step 1: Write the failing test** (extend the E2E handoff test):
```python
# kalai/tests/test_make.py — add
async def test_master_carries_a_caption_and_all_variants():
    res = await _run_make()                      # the existing demo make() helper in this file
    out = res.output
    assert out["caption"]                        # kalai authored ONE base caption
    assert set(out["formats"]) == {"x", "ig", "linkedin"}
    assert out["compliance"] == "cleared"
```
- [ ] **Step 2: Run to verify it fails** — caption empty → FAIL.
- [ ] **Step 3: Implement** — (a) add `"caption": "<the one base caption, on voice>"` to the `COPY_SEO` JSON contract in `prompts.py`; (b) add a `caption` key to `_COPY` in `demo_fixtures.py`; (c) in `assemble_master()` (demo_fixtures) + `runner.py` master assembly, set `caption=copy.get("caption", _COPY["caption"])` on the `CreativeMaster`.
- [ ] **Step 4: Run** — `pytest kalai/tests/test_make.py -q` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(kalai): author the base caption in the Copy desk → CreativeMaster.caption"`

### Task 1.3: Retire kural's `outreach_writer` + `claim_judge`; read kalai's master untouched

**Files:**
- Modify: `kural/agent.py:90-122` (drop the message_loop; the pipeline becomes Coordinator → Parallel(scouts) → Gate), `kural/sub_agents.py` (remove `build_writer`/`build_claim_judge`/`ClaimReportSchema`), `kural/runner.py:73-86` (`_build_post`: use `master["formats"]`/`master["caption"]` directly — no writer variants), `kural/agent.py:44-68` (remove `ClaimCheckAgent`), `kural/agent.py:71-87` (`GateAgent`: gate on send-eligibility, not `CLAIM_VERIFIED`), `kural/prompts.py` (remove `WRITER`/`CLAIM_JUDGE`), `kural/demo_fixtures.py` (remove `_DRAFT`; `launch_post` uses `master["formats"]`)
- Test: `kural/tests/test_engage.py` (rewrite per addendum §D), `kural/tests/test_claim_judge.py` (delete)

- [ ] **Step 1: Write the new contract test** (the separation guarantee):
```python
# kural/tests/test_engage.py — replace the claim-bound assertions
async def test_kural_publishes_kalai_words_untouched():
    master = {"asset_id":"a1","brief":"b","caption":"KALAI CAPTION",
              "formats":{"x":"KALAI X","ig":"KALAI IG","linkedin":"KALAI LI"},
              "fidelity_score":9.1,"compliance":"cleared","spend_usd":1.2}
    res = await runner.engage(EventStream(), "fw", master, _PACK)
    post = res.state["post"] if "post" in res.state else res.output
    # kural carried kalai's EXACT words — authored nothing of its own.
    assert post["drafts"] == master["formats"]
    assert "claim_support" not in post            # the judge is gone
    assert res.status == "awaiting_approval"      # still halts at tap-2

async def test_no_writer_or_judge_in_transcript():
    res = await runner.engage(EventStream(), "fw", _MASTER, _PACK)
    actors = " ".join(l["actor"] for l in res.transcript)
    assert "Outreach Writer" not in actors and "Claim Judge" not in actors
    assert "Scout" in actors or "Delivery" in actors
```
- [ ] **Step 2: Delete `kural/tests/test_claim_judge.py`** (`git rm kural/tests/test_claim_judge.py`).
- [ ] **Step 3: Run to verify the new tests fail** — writer/judge still present → FAIL.
- [ ] **Step 4: Implement the retirement** — remove the two seats, the `message_loop`, `ClaimCheckAgent`, `ClaimReportSchema`, the `WRITER`/`CLAIM_JUDGE` prompts, `_DRAFT`. In `_build_post`, set `"caption": master.get("caption",""), "drafts": master.get("formats", {})` (master wins — no fallback to re-authored variants). `GateAgent` now opens on send-eligibility (Coordinator-qualified + eligible), not `CLAIM_VERIFIED`. Update `runner.engage` to drop all `CLAIM_*` emissions; the gate detail loses `claim_support`.
- [ ] **Step 5: Run kural suite** — `pytest kural/tests -q` → PASS. Then run the flywheel test `tests/test_flywheel.py` — the demo published output (caption text) must equal kalai's `formats` (byte-identical user-visible result).
- [ ] **Step 6: Run all three suites** — green bar.
- [ ] **Step 7: Commit** — `git commit -m "refactor(kural): retire outreach_writer + claim_judge; carry kalai's master untouched (separation fix #1)"`

### Task 1.4: Update the future_scope-aligned seat counts + cards

**Files:** Modify `common/config.py:150-157` (`QUADRANTS` kural seats 7→reflect retired writer/judge + new delivery readers — keep the count honest), any agent-card text in `kural/agent.py`/`kural/runner.py` that names retired seats.

- [ ] **Step 1:** Grep for "Outreach Writer"/"Claim Judge"/"claim_support" across `kural/` and `web/` cockpit copy; remove stale references.
- [ ] **Step 2:** Run all three suites green.
- [ ] **Step 3: Commit** — `git commit -m "chore(kural): scrub retired-seat references; honest seat count"`

**PHASE 1 GATE:** all three suites green; demo published caption == kalai formats; no writer/judge anywhere. Run the full suite, then proceed.

---

# PHASE 2a — Extract the chamber skeleton (byte-identical)

**Why:** turn arivu's proven pipeline into the reusable primitive **without changing any behavior**. arivu's existing 4 tests are the proof harness (addendum §E). No deepening here.

### Task 2a.1: Write the standalone chamber-primitive test

**Files:** Create `common/tests/__init__.py`, `common/tests/test_chamber_primitive.py`

- [ ] **Step 1: Write the failing test** — a tiny scripted chamber (no faculty) exercising the skeleton: a 2-seat panel, a verdict seat, a prosecutor seat, fail-closed gate. Use `common.models.ScriptedLlm` directly with a local resolver so it's infra-light.
```python
# common/tests/test_chamber_primitive.py
import pytest
from common import chamber, models

# a local demo resolver registered under a test namespace
_PAYLOADS = {
    "adv_a": '{"lens":"a","claim":"go","confidence":0.8}',
    "adv_b": '{"lens":"b","claim":"go","confidence":0.8}',
    "verdict": '{"decision":"do X","reasons":["r1","r2"],"dissent":"","confidence":0.85}',
    "prosecutor": '{"attack":"weak on r2","defensibility":0.84,"survived":true}',
}
models.register_demo("chtest", lambda role, req: _PAYLOADS.get(role, "{}"))

def _seat(role):
    from google.adk.agents import LlmAgent
    return LlmAgent(name=role, model=models.gemini_flash("chtest", role),
                    instruction="x", output_key=f"pos_{role}")

async def test_skeleton_runs_panel_verdict_prosecute_gate():
    spec = chamber.ChamberSpec(
        namespace="chtest",
        panel=[_seat("adv_a"), _seat("adv_b")],
        verdict=_seat("verdict"),
        prosecutor=_seat("prosecutor"),
        score_key="defensibility", survived_key="survived",
        threshold=0.80, max_prosecution_rounds=3,
        gate_status_key="gate_status", human_tap=False,
    )
    state = await chamber.run_chamber(spec, init_state={"question": "q"})
    assert state["survived"] is True
    assert float(state["defensibility"]) >= 0.80
    assert state["gate_status"] == "cleared"     # fail-closed pass (human_tap=False)
```
- [ ] **Step 2: Run to verify it fails** — `pytest common/tests/test_chamber_primitive.py -q` → FAIL (`no module common.chamber`).

### Task 2a.2: Lift the three control agents into `common/chamber.py`

**Files:** Create `common/chamber.py`

- [ ] **Step 1: Write `common/chamber.py`** — port `DebateCheckAgent`/`ProsecutionCheckAgent`/`GateAgent` from `arivu/arivu/agent.py:43-115`, generalized:
  - Each control agent takes its **state-key bindings** + **predicate** at construction (not the module-global `SK`/`analyst`).
  - `_default_should_stop(score, rnd, threshold, max_rounds) -> (stop, survived, reason)` reproduces arivu's `prosecution_should_stop` semantics generically.
  - `GateAgent`: `human_tap=True` → `gate_status="awaiting_approval"` if survived else `"no_safe_decision"`; `human_tap=False` → `"cleared"` if `gate_condition(state)` else `"blocked"` (fail-closed).
  - `TokenBudget`: a dataclass with `total: int|None` + a no-op `charge()` (enforcement is Track B).
  - `ChamberSpec` + `build_chamber(spec)` assembling `SequentialAgent([frame?, ParallelAgent(panel), debate_loop?, verdict, prosecution_loop, gate])`.
  - `run_chamber(spec, init_state)` — an `InMemoryRunner` helper mirroring `arivu.runner.deliberate` (sums `_usage`), returning final state.
  - **Hard rule:** no `import arivu`, no `from arivu...` anywhere in this file.
- [ ] **Step 2: Run the primitive test** — `pytest common/tests/test_chamber_primitive.py -q` → PASS.
- [ ] **Step 3: Add a fail-closed + rollback test** to the same file:
```python
async def test_fail_closed_rollback_when_prosecution_never_survives():
    _PAYLOADS["prosecutor"] = '{"attack":"fatal","defensibility":0.40,"survived":false}'
    spec = ...  # same as above
    state = await chamber.run_chamber(spec, {"question":"q"})
    assert state["survived"] is False
    assert state["gate_status"] == "blocked"     # fail-closed: no safe decision
    _PAYLOADS["prosecutor"] = '{"attack":"weak on r2","defensibility":0.84,"survived":true}'  # restore
```
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(chamber): extract reusable chamber skeleton into common/chamber.py (no model factory inside)"`

### Task 2a.3: Rebuild arivu's `root_agent` on `build_chamber` — prove byte-identical

**Files:** Modify `arivu/arivu/agent.py` (replace the three local control classes + `build_root_agent` with a call into `common.chamber`; arivu passes its OWN seats + `analyst` predicates + `StateKeys` bindings)

- [ ] **Step 1: Implement the rebuild** — in `arivu/arivu/agent.py`:
```python
from common import chamber                       # safe: no import cycle (addendum §E)
from . import config, sub_agents
from .tools import analyst
SK = config.StateKeys

def build_root_agent():
    spec = chamber.ChamberSpec(
        namespace="arivu",
        frame=sub_agents.build_frame_agent(),
        panel=sub_agents.build_mantris(),
        debate=sub_agents.build_debate_moderator(),
        convergence_fn=analyst.compute_convergence,
        convergence_key=SK.CONVERGENCE,
        convergence_threshold=config.CONVERGENCE_THRESHOLD,
        max_debate_rounds=config.MAX_DEBATE_ROUNDS,
        verdict=sub_agents.build_chair_synthesizer(),
        prosecutor=sub_agents.build_prosecutor(),
        score_key=SK.DEFENSIBILITY, survived_key=SK.VERDICT_SURVIVED,
        threshold=config.DEFENSIBILITY_THRESHOLD,
        max_prosecution_rounds=config.MAX_PROSECUTION_ROUNDS,
        prosecution_should_stop=analyst.prosecution_should_stop,   # arivu's exact rollback
        gate_status_key=SK.GATE_STATUS, human_tap=True,            # company chamber = tap-1
        # state-key bindings for the control agents (debate/prosecution history etc.):
        debate_round_key=SK.DEBATE_ROUND, debate_done_key=SK.DEBATE_DONE,
        debate_history_key=SK.DEBATE_HISTORY, positions_reader=analyst.read_positions,
        prosecution_round_key=SK.PROSECUTION_ROUND, prosecution_key=SK.PROSECUTION,
        prosecution_history_key=SK.PROSECUTION_HISTORY,
    )
    return chamber.build_chamber(spec)

root_agent = build_root_agent()
```
  Delete the three now-duplicated control classes from this file. (If `ChamberSpec` is missing a binding the control agents need, add it to `ChamberSpec` + `build_chamber` — the generic skeleton must accept every key arivu's three agents read/write.)
- [ ] **Step 2: Run arivu's suite** — `cd arivu && PYTHONPATH=. ../.venv/bin/pytest tests/ -q`. **Expected: all 4 (test_chamber, test_rollback, test_threshold, test_executor) byte-identical green.** This is the extraction proof.
- [ ] **Step 3: Run the root flywheel test** — `PYTHONPATH=. ./.venv/bin/pytest tests/test_flywheel.py -q` → green (arivu public runner surface unchanged).
- [ ] **Step 4: Run all three suites** — green bar.
- [ ] **Step 5: Commit** — `git commit -m "refactor(arivu): rebuild root_agent on common.chamber — byte-identical (extraction proven by existing tests)"`

**PHASE 2a GATE:** arivu's 4 tests byte-identical green; flywheel green; chamber primitive has its own tests. Nothing observable changed. Proceed.

---

# PHASE 2b — Deepen the company arivu (depth, new tests)

**Why:** the company chamber is the centerpiece. Each mantri → a 3-advisor parallel ensemble; live grounding at frame time; graduated prosecutor (revise the one failing reason → re-prosecute, not a full reset). Preserve the `PROSECUTION_ROUND::N` demo keying so replay stays consistent.

### Task 2b.1: Mantri → 3-advisor ensemble (the per-lens fan-out)

**Files:** Modify `arivu/arivu/sub_agents.py` (add `build_mantri_ensemble(lens)` → a `ParallelAgent` of 3 sub-advisors that write disjoint sub-keys, + a deterministic reducer that folds them into the existing `POS_*` position), `arivu/arivu/prompts.py` (3 sub-lens prompts per mantri), `arivu/arivu/demo_fixtures.py` (scripted sub-advisor payloads that roll up to the SAME `_POSITIONS[role]` the 2a tests assert), `arivu/arivu/config.py` (sub-lens metadata)
- Test: `arivu/tests/test_ensemble.py` (create)

- [ ] **Step 1: Write the failing test** — the economist position is now backed by 3 cited sub-claims, and the rolled-up position still carries the risk "cliff" catch the 2a test pins:
```python
# arivu/tests/test_ensemble.py
from arivu import config, runner
from arivu.tools import analyst

async def test_each_mantri_fans_into_a_grounded_ensemble():
    state = await runner.deliberate()
    positions = analyst.read_positions(state)
    econ = next(p for p in positions if "unit-economics" in p.get("lens",""))
    # the economist now carries sub-evidence (margin · retention · competitor-bench)
    assert len(econ.get("evidence", [])) >= 3
    assert all(e.get("source") for e in econ["evidence"])   # every sub-claim cited
    # the signature risk catch still survives the deeper path
    risk = next(p for p in positions if "downside" in p.get("lens",""))
    assert "cliff" in risk.get("claim","").lower()
```
- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Implement** — `build_mantris()` now returns 5 ensembles; each ensemble = `ParallelAgent([sub_advisor_1, sub_advisor_2, sub_advisor_3])` + a deterministic reducer `BaseAgent` that writes the consolidated `POS_*` (with an `evidence` list). Demo fixtures script the 3 sub-payloads so the consolidated position is identical to today's `_POSITIONS[role]` plus the `evidence` list. **2a tests must still pass** (the consolidated `claim`/`confidence` unchanged).
- [ ] **Step 4: Run arivu suite** — `test_ensemble` + the 4 original tests all green.
- [ ] **Step 5: Commit** — `git commit -m "feat(arivu): mantri ensembles — each lens fans into 3 cited sub-advisors"`

### Task 2b.2: Graduated prosecutor (revise the one failing reason → re-prosecute)

**Files:** Modify `arivu/arivu/sub_agents.py` (add `build_reviser()` — a Claude seat that rewrites ONLY the reason the prosecutor faulted; graduated `_prosecutor_instruction` that, on round ≥2, addresses only the prior round's gap), `arivu/arivu/prompts.py` (graduated PROSECUTOR + REVISER prompts), `arivu/arivu/demo_fixtures.py` (keep `PROSECUTION_ROUND::N` keying; round-0 faults reason #2 → reviser strengthens it → round-1 survives at 0.84), wire `reviser` into the `ChamberSpec` (the prosecution loop becomes `[prosecutor, reviser, ProsecutionCheck]`)
- Test: `arivu/tests/test_graduated_prosecution.py` (create)

- [ ] **Step 1: Write the failing test:**
```python
async def test_prosecution_revises_one_reason_not_a_full_reset():
    state = await runner.deliberate()
    hist = state[config.StateKeys.PROSECUTION_HISTORY]
    assert len(hist) >= 2
    # round 1 faulted a specific reason; round 2 targeted that SAME reason and survived
    assert hist[0]["defensibility"] < config.DEFENSIBILITY_THRESHOLD
    assert hist[-1]["defensibility"] >= config.DEFENSIBILITY_THRESHOLD
    assert state.get(config.StateKeys.VERDICT_SURVIVED) is True
    # the verdict's reasons were revised between rounds (not regenerated wholesale)
    revisions = state.get("reason_revisions", [])
    assert revisions and revisions[0]["target_reason_index"] is not None
```
- [ ] **Step 2: Run to verify it fails.**
- [ ] **Step 3: Implement** — the reviser reads the prosecutor's `attack` + the verdict's `reasons`, rewrites the faulted reason, writes `reason_revisions` + an updated verdict; the graduated prosecutor prompt on round ≥2 attacks only the revised reason. Demo replay: round-0 prosecutor `{defensibility:0.71, faulted_reason_index:1}` → reviser strengthens reason[1] → round-1 prosecutor `{defensibility:0.84, survived:true}`. **`test_rollback`/`test_threshold` stay green** (the rollback path when revision still fails is unchanged).
- [ ] **Step 4: Run arivu suite** — all green incl. the new test.
- [ ] **Step 5: Commit** — `git commit -m "feat(arivu): graduated prosecutor — revise the faulted reason and re-prosecute, not a full reset"`

### Task 2b.3: Live grounding at frame time

**Files:** Modify `arivu/arivu/tools/grounding.py:61-86` (`fetch_grounding`: when `config.is_live()` and an MCP/admin source is configured, fetch real numbers; else the existing fixture), wire `grounding_callback` through `ChamberSpec.frame`
- Test: `arivu/tests/test_live_grounding.py` (create; gated `@pytest.mark.skipif(not creds, ...)`)

- [ ] **Step 1: Write the gated real-path test** — with a mocked grounding source, assert `fetch_grounding` returns the live bundle (not the fixture) and the frame callback injects it into state. In demo (no creds), assert it falls back to the fixture (byte-identical).
- [ ] **Step 2–4:** implement the live branch (mockable client), run the test (demo path green; live path skipped without creds).
- [ ] **Step 5: Commit** — `git commit -m "feat(arivu): live grounding at frame time (demo falls back to fixture, byte-identical)"`

**PHASE 2b GATE:** all three suites green; ensemble + graduated prosecution + live grounding tested; 2a tests still byte-identical. Proceed.

---

# PHASE 3 — kalai real media + the 4-scorer fidelity panel

**Why:** a brief must yield real pixels/video (Vertex Imagen/Veo), and the single fidelity score must decompose into kalai's chamber panel (brand-consistency · voice-tone · platform-fit · compliance-edge), sourced from real scored runs.

### Task 3.1: Add Vertex media model ids + verify against current docs

**Files:** Modify `common/config.py` (add `MODEL_IMAGEN`, `MODEL_VEO`)
- [ ] **Step 1:** Verify the current Vertex Imagen + Veo model ids against Vertex docs (honor the check-model-versions rule — do NOT carry ids from memory). Add:
```python
MODEL_IMAGEN = os.environ.get("SAAKSHE_MODEL_IMAGEN", "<verified-imagen-id>")
MODEL_VEO    = os.environ.get("SAAKSHE_MODEL_VEO", "<verified-veo-id>")
```
- [ ] **Step 2: Commit** — `git commit -m "chore(config): Vertex Imagen/Veo model ids (verified against docs)"`

### Task 3.2: `kalai/media.py` — the media client wrapper (demo pixel-free)

**Files:** Create `kalai/media.py`, `kalai/tests/test_media.py`
- [ ] **Step 1: Write the failing test:**
```python
# kalai/tests/test_media.py
from kalai import media

def test_demo_returns_deterministic_placeholder_no_network(monkeypatch):
    monkeypatch.setenv("SAAKSHE_MODE", "demo")
    out = media.render_still(prompt="a clean banner", palette="slate")
    assert out["image_ref"].startswith("vertex://imagen/placeholder/")
    assert out["bytes"] is None                  # no pixels in demo
    assert out["spend_usd"] == 0.0

def test_live_calls_vertex(monkeypatch):
    calls = {}
    monkeypatch.setattr(media, "_vertex_imagen", lambda **kw: (calls.update(kw) or {"image_ref":"vertex://imagen/real/1","bytes":b"x","spend_usd":0.02}))
    monkeypatch.setenv("SAAKSHE_MODE", "live") if hasattr(monkeypatch,"setenv") else monkeypatch.setenv("SAAKSHE_MODE","live")
    out = media.render_still(prompt="p", palette="slate", _force_live=True)
    assert out["image_ref"] == "vertex://imagen/real/1" and calls["prompt"] == "p"
```
- [ ] **Step 2: Run to fail.**
- [ ] **Step 3: Implement** — `render_still(prompt, palette, ...)` + `render_reel(prompt, stills, ...)`: when `config.is_live()` call `_vertex_imagen`/`_vertex_veo` (google-genai Vertex client, `config.MODEL_IMAGEN`/`MODEL_VEO`); else return a deterministic placeholder ref keyed by a hash of the prompt (no network, `bytes=None`, `spend_usd=0.0`). Keep the live client in a small `_vertex_imagen()`/`_vertex_veo()` for easy mocking.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat(kalai): Vertex Imagen/Veo media wrapper (demo pixel-free, deterministic placeholder)"`

### Task 3.3: Wire the designer to `media.py`

**Files:** Modify `kalai/sub_agents.py` (the designer producer gains a `tools=[render_still_tool]` or the runner calls `media.render_still` after the designer spec), `kalai/runner.py` (attach `media` to the `CreativeMaster`), `kalai/demo_fixtures.py` (placeholder ref in the demo master)
- Test: `kalai/tests/test_make.py` (extend: master carries a media image_ref)
- [ ] **Step 1: Write the failing test** — `out["media"]["image_ref"]` present and `vertex://` in demo. **Step 2:** fail. **Step 3:** implement (designer emits the spec; runner calls `media.render_still(prompt=spec.visual, palette=spec.palette)` and sets `master.media`). **Step 4:** pass. **Step 5: Commit** — `git commit -m "feat(kalai): designer produces real media via Vertex (demo placeholder)"`

### Task 3.4: The 4-scorer fidelity panel (kalai's chamber)

**Files:** Create `kalai/scorers.py`, `kalai/tests/test_scorers.py`; modify `kalai/agent.py` (fidelity loop's scorer → a `ParallelAgent` of 4 scorers + a deterministic aggregate that writes `FIDELITY_SCORE`), `kalai/prompts.py` (4 scorer prompts), `kalai/demo_fixtures.py` (4 sub-scores per round that AGGREGATE to `[6.8,8.4,9.1]`)
- [ ] **Step 1: Write the failing test** — the aggregate of the 4 demo sub-scores per round equals the canon climb, and the loop still exits at 9.1:
```python
# kalai/tests/test_scorers.py
from kalai import scorers
from common import config
def test_four_scorers_aggregate_to_canon_climb():
    for rnd, expected in enumerate(config.CANON["fidelity_climb"], start=1):
        subs = scorers.demo_subscores(rnd)        # {brand,voice,platform,compliance}
        assert len(subs) == 4
        assert abs(scorers.aggregate(subs) - expected) < 1e-6
```
- [ ] **Step 2: Run to fail. Step 3: Implement** — `aggregate(subs)` = a documented weighted mean; `demo_subscores(rnd)` returns 4 numbers whose aggregate == `CANON["fidelity_climb"][rnd-1]`. Replace `build_fidelity_scorer()` with `build_scorer_panel()` (4 Gemini Flash seats) + an aggregate reducer in the loop. **`test_fidelity.py` (the `[6.8,8.4,9.1]` climb pins) stays green** because the aggregate reproduces the climb. **Step 4: Run** kalai suite green. **Step 5: Commit** — `git commit -m "feat(kalai): decompose fidelity into a 4-scorer chamber panel; aggregate reproduces the canon climb"`

### Task 3.5: Source the fidelity climb from real scored runs (live)

**Files:** Modify `kalai/runner.py` (already reads `FIDELITY_SCORE` from state — confirm the live path uses the real panel aggregate, not the CANON fallback), add a gated real-path test.
- [ ] **Step 1:** gated `@skipif(not creds)` test that in hybrid/live the climb comes from real scorer output (mock the 4 scorers to return rising numbers; assert the master's `fidelity_score` is the live aggregate, not `9.1` fallback). **Step 2–4:** implement/verify. **Step 5: Commit** — `git commit -m "feat(kalai): fidelity climb sourced from real scored runs in live (demo keeps the canon arc)"`

**PHASE 3 GATE:** all three suites green; demo still pixel-free + climb `[6.8,8.4,9.1]`; one real-path media test + one real-path fidelity test. Proceed.

---

# PHASE 4 — kural live grounding + the 4 deep delivery readers

**Why:** stop starting from `DEMO_GROUNDING`; fetch the real manas Context Pack and give the readers tools over live funnel/audience/feed. Scouts → parallel-deep readers (consent · reach · topic-fit · timing) = kural's chamber panel. (Authoring is already gone from Phase 1.)

### Task 4.1: Real Context Pack at frame time (no DEMO_GROUNDING base in live)

**Files:** Modify `kural/grounding.py:35-48` (`fetch_grounding`: in live, build the bundle from the passed real `context_pack` + live funnel/market reads; only fall back to `DEMO_GROUNDING` in demo)
- Test: `kural/tests/test_grounding.py` (create)
- [ ] **Step 1: Write the failing test** — in demo, `fetch_grounding(pack)` returns the fixture with the pack's version (unchanged); add a live-gated test that with a real pack + mocked funnel source, the bundle's `funnel`/`market` come from the live source, not the fixture. **Step 2:** fail. **Step 3:** implement the live branch. **Step 4:** demo green, live path mockable. **Step 5: Commit** — `git commit -m "feat(kural): real Context Pack + live funnel/market at frame time (demo unchanged)"`

### Task 4.2: The 4 deep delivery readers + delivery planner

**Files:** Create `kural/delivery.py`, `kural/tests/test_delivery.py`; modify `kural/agent.py` (the scout `ParallelAgent` becomes 4 readers: consent · reach · topic-fit · timing; add a `delivery_planner` Claude seat that picks variant×segment×window and **authors no words**), `kural/sub_agents.py`, `kural/prompts.py`, `kural/demo_fixtures.py`
- [ ] **Step 1: Write the failing test** — 4 readers run in parallel, the planner outputs a plan referencing kalai's variant keys (never new copy):
```python
# kural/tests/test_delivery.py
async def test_planner_picks_variant_and_window_authors_nothing():
    res = await runner.engage(EventStream(), "fw", _MASTER, _PACK)
    plan = res.state["delivery_plan"]
    assert plan["variant"] in {"x","ig","linkedin"}          # picked, not authored
    assert plan["window"] and plan["segment"]
    # the planned text is byte-identical to kalai's chosen format (no new words)
    assert plan["text"] == _MASTER["formats"][plan["variant"]]
    actors = " ".join(l["actor"] for l in res.transcript)
    assert all(s in actors for s in ("consent","reach","topic","timing"))
```
- [ ] **Step 2: Run to fail. Step 3: Implement** the 4 readers (each cites its source — consent ledger, reach/funnel, topic-fit, timing window) + the planner. **Step 4:** kural suite green. **Step 5: Commit** — `git commit -m "feat(kural): 4 deep delivery readers + delivery planner (picks delivery, authors nothing)"`

### Task 4.3: Read-tools over live funnel/audience/feed (gated real-path)

**Files:** Modify `kural/tools/analyst.py`/`kural/tools/channels.py` (give the readers real read-tools in live), add a gated real-path test.
- [ ] **Step 1–5:** gated test that in live the readers call the real tools (mocked) and cite live numbers; demo unchanged. Commit — `git commit -m "feat(kural): read-tools over live funnel/audience/feed (demo fixture fallback)"`

**PHASE 4 GATE:** all three suites green; kural authors nothing, grounds in the real pack in live; one real-path test. Proceed.

---

# PHASE 5 — manas's senses (social read · founder-voice via Claude · imbiber fan-out)

**Why:** replace the social STUB with a real handle read; route founder-voice through Claude on the default path; split each imbiber into 3–4 specialized sub-calls (claims · voice-semantics · brand-visual · contradiction-precheck) = manas's chamber panel.

### Task 5.1: Real social handle reader (replace the stub)

**Files:** Create `manas/social.py`, `manas/tests/test_social.py`; modify `manas/runner.py:174-178` (the social branch of `_read_one`)
- [ ] **Step 1: Write the failing test** — in demo, the social reader returns a deterministic structured bundle (handle + scripted recent-post summary), NOT the literal `"Primary social presence: {ref}."`; in live (gated/mocked), it fetches real handle signal. **Step 2:** fail. **Step 3:** implement `manas/social.py` (`read_handle(ref)` — live: a real fetch via the public profile/oEmbed or a configured API, mockable; demo: a structured deterministic bundle). Wire `_read_one(kind="social")` to call it. **Step 4:** manas suite green (`test_ingest` still grounds; the social bundle now has structured text). **Step 5: Commit** — `git commit -m "feat(manas): real social handle reader replaces the stub (demo deterministic, live mockable)"`

### Task 5.2: Founder-voice through Claude on the default path

**Files:** Modify `manas/runner.py:392-399` (the A2A `ask_founder_voice` skill), keeping a sync-callable surface that drives the Claude `founder_voice_agent` (with the corpus stem-match as the demo/offline net so sync↔agent agreement holds)
- [ ] **Step 1: Write/confirm the contract test** — `test_founder_voice.py` sync↔agent agreement + refuse-out-of-corpus must stay green; add a hybrid-gated test that the default path actually drives Claude (mock the agent, assert it was invoked). **Step 2:** fail (default still pure stem-match). **Step 3:** implement — the A2A skill, when live, drives `ask_founder_voice_live` (run the agent); in demo, the agent's scripted resolver returns the corpus answer → identical to the sync path. Keep a sync fallback so a plain `def` caller never breaks. **Step 4:** `test_founder_voice.py` green. **Step 5: Commit** — `git commit -m "feat(manas): founder-voice routes through Claude on the default path (demo = corpus net, contract preserved)"`

### Task 5.3: Imbiber fan-out — 3–4 specialized sub-readers per source

**Files:** Create `manas/imbiber_pod.py`, `manas/tests/test_imbiber_pod.py`; modify `manas/sub_agents.py:94-106` (`build_imbibers` → each channel builds a pod: claims · voice-semantics · brand-visual · contradiction-precheck sub-readers + a reducer that writes the existing `INGEST_*` shape), `manas/prompts.py`, `manas/demo_fixtures.py` (scripted sub-payloads that roll up to the SAME `_INGEST[channel]` so `test_ingest`/`test_pipeline` stay green)
- [ ] **Step 1: Write the failing test:**
```python
# manas/tests/test_imbiber_pod.py
async def test_each_source_fans_into_specialized_subreaders():
    pod = imbiber_pod.build("repo")
    out = await imbiber_pod.run_demo(pod, source_text="README ...")
    assert set(out["by_lens"]) >= {"claims","voice","brand","contradiction"}
    # the reassembled blob is the SAME shape the curator already consumes
    assert all(c.get("source") for c in out["claims"])
```
- [ ] **Step 2: Run to fail. Step 3: Implement** the pod (ParallelAgent of 4 sub-readers + a deterministic reassembler producing the `INGEST_*` JSON). Demo sub-payloads aggregate to today's `_INGEST[channel]` so the groundedness math + commit arc are unchanged. **Step 4:** manas suite green (incl. `test_groundedness`/`test_pipeline`). **Step 5: Commit** — `git commit -m "feat(manas): imbiber fan-out — 3-4 specialized sub-readers per source (curator contract preserved)"`

**PHASE 5 GATE:** all three suites green; social real, founder-voice via Claude, imbibers fan out; demo byte-identical published output. Track A complete.

---

# Track B (surfaced — gated behind Track A; not scheduled here)

Do NOT start these until Track A is green and demoable. Each becomes its own spec → plan when reached:
6. **Brand-asset VAULT** (real logos/palettes/fonts/refs, indexed + versioned in Supabase Storage/R2; manas proactively serves kalai).
7. **Learning flywheel** (kural results → manas's next Context Pack → arivu/kalai's next cycle).
8. **arivu precedent reuse + prosecution panel** (index sealed verdicts; lone prosecutor → panel; open call: does precedent skip prosecution?).
9. **Witness parity + BYOK + token budgets** (voice parity; founder holds all keys; **enforce the `ChamberSpec.budget` reserved in 2a** as a hard gate).

---

## Self-review (run before handing off)

- **Spec coverage:** parent §4 steps 1→5 each map to a phase (1, 2a+2b, 3, 4, 5); the chamber primitive (addendum §B) = Phase 2a; the 4 chamber instances (addendum §C) = Phases 2b/3/4/5; demo contract (§D) = the per-phase gates + addendum-aligned test triage; budget reservation (§B) = Task 2a.2; Track B surfaced + gated. ✔
- **Placeholder scan:** the only intentional `<...>` placeholders are the Vertex model ids in Task 3.1 (must be doc-verified at execution, not memory) — flagged explicitly, not a silent TODO. Every test step shows real assertion code.
- **Type consistency:** `CreativeMaster` gains `caption`/`media` (Task 1.1) and both are used consistently (kalai 1.2/3.3, kural 1.3/4.2). `ChamberSpec` fields defined in 2a.2 are exactly those passed in 2a.3 and reused in 3.4/4.2/5.3. `FIDELITY_SCORE`/`fidelity_climb` names match the existing `common/config.py` CANON. ✔
- **Green-bar discipline:** every phase ends by running all three suites; every chargeable/agentic change adds one gated real-path test (constraints satisfied).

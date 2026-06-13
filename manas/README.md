# manas — the company's mind (KNOWS)

> _manas — the mind that perceives, holds, and recalls; the faculty that takes in the world and keeps it._

**manas is a company's MEMORY faculty made operational.** It imbibes the founder's
vision, voice, and history together with the world's pulse into ONE versioned,
source-cited memory — a Context Pack the rest of the company is bound by. It
**knows; it never acts, posts, or decides.** When it cannot ground a claim it
**refuses rather than fabricate** — the guardrail that keeps the company from ever
being bound by a hallucinated founder opinion. In faculty-v2 manas is also the
**custodian of the company's keys to the world** — it holds every channel and
provider credential and lends a scoped use to the faculty that acts, wielding none
itself; still it never acts, posts, or decides.

Built on the **Google Agent Development Kit (ADK)**, on the shared saakshe
substrate (`common/`). Part of the saakshe agentic company:
**manas** (knows) · **arivu** (decides) · **kalai** (makes) · **kural** (engages).

---

## What it is for

Sundara Coffee Co. is four people. Its memory lives in a founder's head, a Notion
page, a Stripe export, a folder of brand assets, and a voice-note from launch day.
When arivu deliberates a pricing call, when kalai writes a banner, when kural posts
to the world — each of them needs the SAME grounded facts and the SAME founder
voice, or the company contradicts itself. manas is that one memory: every other
quadrant grounds on its Context Pack, and the day's decision is remembered back
into it so the company learns.

A chatbot answers from model memory — confident, ungrounded, and happy to invent a
founder opinion that was never held. manas does the opposite: every fact it serves
carries a source, and an out-of-corpus question comes back **refused with empty
citations**, never an invented answer.

---

## Architecture — two real ADK agents

### `root_agent` — the ingestion → curate → commit pipeline

A `SequentialAgent` named **manas**. ADK's `ParallelAgent` and `LoopAgent` are
**earned** here, and nowhere else in the module:

```
            the day's outcome to remember
                          │
                          ▼
            ┌───────────────────────────────┐
            │  Mind Keeper · Gemini 2.5 Pro  │  routes ingestion across modalities
            │  (coordinator / router)        │  (knows, never decides)
            └───────────────────────────────┘
                          │
                          ▼
   ┌──────────────────  ParallelAgent  ──────────────────┐
   │  4 imbibers · Gemini 2.5 Flash · disjoint modalities │  batch fan-out:
   │  PDF · Image · Voice · Social                        │  disjoint sources, no ordering,
   │  (each one modality, each its own source)            │  no shared state → genuinely parallel
   └─────────────────────────────────────────────────────┘
                          │
                          ▼
   ┌──────────────────  LoopAgent  ──────────────────────┐
   │  Memory Curator · CLAUDE via Vertex                  │  synthesise → verify EVERY claim
   │     ↕                                                │  cites a source & is non-contradictory
   │  CuratorCheckAgent (deterministic, no model)         │  → revise. EXIT on groundedness
   │  groundedness >= 0.80  OR  max 3 rounds → rollback   │  >= 0.80 or a no-safe-commit rollback
   └─────────────────────────────────────────────────────┘
                          │
                          ▼
            ┌───────────────────────────────┐
            │  commit (deterministic)        │  Context Pack v14 → v15
            │  no human gate — manas KNOWS   │  (or rollback: no safe commit)
            └───────────────────────────────┘
```

- **ParallelAgent is earned:** the four modalities (documents, images, founder
  voice, the world's pulse) are disjoint inputs with no ordering and no shared
  state — exactly the batch fan-out ParallelAgent exists for.
- **LoopAgent is earned:** verify-before-commit is a genuine refinement loop —
  synthesise, verify every claim cites a source and the set is non-contradictory,
  revise, repeat. It **exits on a deterministic numeric groundedness score**
  (`>= GROUNDING_THRESHOLD`, 0.80) **or a `MAX_CURATE_ROUNDS` (3) rollback** —
  NEVER on "the claims look grounded." The math is in pure functions
  (`tools/curator.py`) so tests pin it; the `CuratorCheckAgent` (no model) calls
  them. A **contradiction gates groundedness to 0.0**, so the Curator can never
  commit a self-contradicting memory no matter how many rounds it runs.

### `founder_voice_agent` — the query path

A single Claude-via-Vertex `LlmAgent`, `output_schema`-forced, that answers AS the
founder grounded ONLY in corpus and **REFUSES out-of-corpus** (`refused=True`,
empty citations). The refusal is the contract — an eval fails otherwise.

---

## The two Claude-via-Vertex seats

Routine intelligence (the Mind-Keeper router, the four imbibers) runs on **Gemini**.
The two highest-stakes seats run on **Claude via Vertex AI Model Garden** — the
challenge's third-party-LLM-via-Vertex path, deliberately a stronger model for the
two places a mistake is unrecoverable:

1. **Memory Curator** — the WRITE step: a wrong commit poisons every downstream
   decision, so the verify-before-commit synthesis is forced into a strict
   `CuratorSchema` (claims-with-sources, contradictions, groundedness, version_to).
2. **Founder Voice** — the REFUSAL: a fabricated founder opinion binds the company,
   so the answer is forced into a strict `FounderVoiceSchema` whose `refused` flag
   can never be lost.

Both schemas mirror arivu's `VerdictSchema` / `ProsecutionSchema`: forcing the
output shape means a live Claude reply can never collapse to prose and silently
break the deterministic check that reads it.

---

## The locked interface

`runner.py` keeps the exact orchestrator-facing + A2A interface:

| call | kind | returns | note |
| --- | --- | --- | --- |
| `ground(stream, run_id, topic)` | async | `ContextPack` | read-side grounding for arivu/kalai/kural; lean (served from corpus) |
| `learn(stream, run_id, outcome)` | async | `QuadrantResult` | drives the REAL pipeline; Context Pack **v14 → v15** |
| `manas.get_founder_context(topic)` | A2A · **sync** | `dict` | versioned Context Pack; ungrounded out-of-corpus |
| `manas.ask_founder_voice(question)` | A2A · **sync** | `dict` | refuses out-of-corpus |

The A2A skills are **synchronous and pure-corpus-backed** (they never drive the
async agent), and the agent path and the sync handler read the **same corpus**
(`tools/corpus.py`) so "real" and "fixture" can never disagree. The final Context
Pack tick is pinned to the sealed canon so a live hiccup can never turn the company
flywheel red — live is the engine, the canon is the net.

---

## Run it

```bash
# from the saakshe root, venv at ./.venv, PYTHONPATH=.
SAAKSHE_MODE=demo PYTHONPATH=. ./.venv/bin/python -m pytest manas/tests -q      # the quadrant
SAAKSHE_MODE=demo PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_flywheel.py -q  # stays green

# the eval re-runs the real Gemini + Claude-on-Vertex pipeline (creds-gated):
SAAKSHE_MODE=live GOOGLE_CLOUD_PROJECT=... PYTHONPATH=. \
  ./.venv/bin/python -m pytest manas/eval/test_eval.py -s
```

---

## Tests — the safety property

- `tests/test_groundedness.py` — pins the deterministic curator math: the
  groundedness formula, the citation fraction, the **contradiction gate to 0.0**,
  and the commit / continue / rollback thresholds (exact literals).
- `tests/test_pipeline.py` — the full ADK pipeline (parallel imbibers + curate
  loop) commits when grounded, **exits on the threshold not max-rounds**, ticks
  v14 → v15, and **never commits a planted contradiction** (it rolls back).
- `tests/test_founder_voice.py` — the **out-of-corpus refusal contract** proven
  against the REAL `founder_voice_agent` AND the sync A2A handler, plus Context
  Pack grounding and canon hygiene (no forbidden values/names).
- `eval/` — the ADK `AgentEvaluator` groundedness-with-refusal rubric track @0.80
  (creds-gated, like arivu).

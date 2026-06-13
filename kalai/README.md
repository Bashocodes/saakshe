# kalai — the studio (MAKES)

> A brief enters; a finished, **on-brand, compliance-cleared** multi-platform
> master exits and is handed to **kural** over A2A. kalai's only world-facing
> irreversible act is **token spend**. It holds **no channel keys** and **never
> publishes** — the single creative gate is at the mouth (kural, tap 2).

kalai is one quadrant of **saakshe**, the agentic company. It is a real
[ADK](https://google.github.io/adk-docs/) agent-starter-pack module built at the
same quality bar as the `arivu` reference module, and it shares the company
substrate (`common/`): one run-mode, one model factory, one event stream, one set
of A2A contracts, one sealed canon.

## The pipeline (the ONE earned production loop)

```
creative_director  (Claude · Vertex · frames concept + brand guardrails)
  → Designer/Producer  (composes the visual master spec — kalai is media-only;
                         kural authors the words)
  → LoopAgent:      Brand-Fidelity scorer + deterministic checker  (climb to threshold)
  → compliance_gate (Claude · Vertex · FAIL-CLOSED — blocks unless explicitly cleared)
  → compliance_check (deterministic default-deny — the boolean the handoff is gated on)
```

`runner.make()` drives the assembled `kalai.agent.root_agent` and assembles the
`CreativeMaster` handoff from the **final pipeline state** — exactly the way
`arivu.runner.deliberate` drives `arivu`'s `root_agent`.

### Why Parallel and Loop are *earned*

- **MEDIA-ONLY (faculty-v2)** — kalai composes the visual master spec; the words
  are authored by **kural** (the word faculty). The Copy & SEO desk that once ran
  in parallel here moved to kural, so kalai is now a single production lane feeding
  the brand-fidelity loop.
- **LoopAgent** — the Brand-Fidelity loop is a *real numeric climb* to a bar:
  `6.8 → 8.4 → 9.1` against `FIDELITY_THRESHOLD = 8.5`. **8.4 fails** (under the
  bar, regenerate); **9.1 passes** (on brand, ship). The exit is owned by a
  deterministic checker (`tools/analyst.fidelity_should_stop`), **never** by
  "looks good" — the model only *reports* the score; the math decides the loop.
  A max-round rollback escalates as "not on brand" rather than a false pass.

### Fail-closed compliance (safe by construction)

The compliance gate is a Claude-via-Vertex seat whose output is forced into a
pydantic `output_schema`, and a deterministic check reads it **default-deny**:
the master is **blocked** unless the verdict is *exactly* `"cleared"`. A
missing / malformed / ambiguous reply is read as blocked. A deterministic
sentinel screen (`compliance_screen`) is a hard floor underneath the model, so a
planted-unsafe brief is blocked even if a live gate were ever fooled — and on a
block there is **no master, no spend disclosure, and no A2A to kural**.

## Seats (media-only — the Copy & SEO desk + Voice lens moved to kural in faculty-v2)

| Desk | Seat | Model |
|---|---|---|
| Decision | Creative Director (coordinator + taste) | **Claude · Vertex** |
| Production | Designer / Producer (example media) | Gemini |
| Production | Copy & SEO | Gemini |
| Scoring | Brand-Fidelity scorer (in-loop) | Gemini |
| Gate | Compliance check (fail-closed) | **Claude · Vertex** |

The two Claude seats are the highest-stakes ones — the taste call at the top and
the fail-closed gate at the bottom — and the only ones forced with an
`output_schema`. Everything else is Gemini. (ADK disallows `tools` alongside
`output_schema`, so both Claude seats carry a schema and no tools.)

## Locked interface

```python
async def make(stream, run_id, brief, context_pack: dict) -> common.a2a.QuadrantResult
    # status "handoff", output = CreativeMaster.as_dict()
    # status "no_safe_decision" if compliance blocks
# A2A skill:
kalai.render_asset(brief, context_pack) -> dict   # cleared master dict, or blocked marker
```

The orchestrator and `tests/test_flywheel.py` call these; the bodies drive the
real ADK `root_agent`, but the signatures, the `QuadrantResult` / stream events,
and the A2A registrations are unchanged.

## Run the tests (demo mode — no creds)

```sh
cd path/to/saakshe
SAAKSHE_MODE=demo PYTHONPATH=. ./.venv/bin/python -m pytest kalai/tests -q
SAAKSHE_MODE=demo PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_flywheel.py -q
```

The deterministic suite pins the studio's **safety property**: the fidelity loop
exits exactly on the threshold (`8.4` fails, `9.1` passes), compliance is
fail-closed (a planted-unsafe brief is blocked with no handoff), the happy-path
master carries `compliance == "cleared"` at fidelity `9.1`, and kalai **never
returns channel keys / never publishes**.

## eval (creds-gated · rubric @ 0.80)

`eval/evalset.json` + `eval/test_eval.py` grade the studio with ADK's
`AgentEvaluator` on two rubric tracks — **brand fidelity** and **compliance
clearance** — at threshold **0.80** (the LLM-judge bar, distinct from the in-loop
`FIDELITY_THRESHOLD = 8.5`). The eval re-runs the full Claude + Gemini studio, so
it runs only with live creds:

```sh
SAAKSHE_MODE=live GOOGLE_CLOUD_PROJECT=... \
  PYTHONPATH=. ./.venv/bin/python -m pytest kalai/eval/test_eval.py -s
```

## Demo vs live

In **demo** mode the full ADK orchestration runs — Parallel / Loop / escalate /
fail-closed gate / A2A — and only token generation is replayed by a deterministic
resolver registered at import (`models.register_demo("kalai", …)`), reproducing
the sealed canon (fidelity climb `6.8 → 8.4 → 9.1`; compliance `cleared`). In
**live** mode the same pipeline runs against Gemini and Claude-via-Vertex. Live is
the product; the replay is the net that lets the whole flywheel demo creds-free
and survive a 429 mid-demo.

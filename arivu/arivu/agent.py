"""arivu — the assembled chamber. Exports `root_agent`.

The ONE earned convergence pipeline:

    chair_frame (Gemini Pro · frames + grounds)
      → ParallelAgent: 5 mantris (Gemini Flash · disjoint lenses, in parallel)
      → LoopAgent: debate (moderator + deterministic convergence check)
      → chair_synthesizer (Claude · Vertex · the verdict)
      → LoopAgent: prosecution (prosecutor + defensibility ≥ 0.80 check / rollback)
      → gate (halts at the single HITL approval)

Parallel and Loop are *earned* here: multi-lens deliberation genuinely needs
Parallel; the debate and the prosecution genuinely need Loop. Every loop exits on
a numeric threshold or a max-iteration rollback — never on "the advisors agreed."

The executor (real, irreversible action) is deliberately NOT part of root_agent:
the pipeline halts at the gate, and execution fires only after a human approval —
see runner.execute_decision / tools.executor.
"""

from __future__ import annotations

import sys
from pathlib import Path

# arivu now builds its chamber on the shared `common.chamber` skeleton. When the
# arivu suite runs standalone (`cd arivu && PYTHONPATH=. pytest`), only arivu's
# root is on sys.path, so make the saakshe root importable too. Symmetric with
# `common/__init__.py`, which adds arivu's root to sys.path; no cycle, because
# `common.chamber` never imports arivu (skeleton only).
_SAAKSHE_ROOT = Path(__file__).resolve().parent.parent.parent
if (_SAAKSHE_ROOT / "common").is_dir() and str(_SAAKSHE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SAAKSHE_ROOT))

from common import chamber  # noqa: E402

from . import config, models, sub_agents  # noqa: E402
from .tools import analyst  # noqa: E402

models.configure_runtime()
SK = config.StateKeys


# ─── Assemble the chamber ────────────────────────────────────────────────────
# The three deterministic control agents (DebateCheckAgent / ProsecutionCheckAgent
# / GateAgent) + the loop/history wiring now live in `common.chamber` as the
# reusable skeleton. arivu rebuilds its root_agent on that skeleton, passing its
# OWN seats, its `analyst` predicates, and its `StateKeys` bindings — so the
# skeleton reproduces today's behaviour byte-for-bit (the existing 4 tests are the
# proof). `human_tap=True` makes this the one chamber that halts for the founder.
def build_root_agent() -> chamber.BaseAgent:
    spec = chamber.ChamberSpec(
        namespace="arivu",
        frame=sub_agents.build_frame_agent(),
        panel=sub_agents.build_mantris(),
        debate=sub_agents.build_debate_moderator(),
        convergence_fn=analyst.compute_convergence,
        convergence_key=SK.CONVERGENCE,
        convergence_threshold=config.CONVERGENCE_THRESHOLD,
        max_debate_rounds=config.MAX_DEBATE_ROUNDS,
        debate_should_stop=analyst.debate_should_stop,
        positions_reader=analyst.read_positions,
        debate_round_key=SK.DEBATE_ROUND,
        debate_done_key=SK.DEBATE_DONE,
        debate_history_key=SK.DEBATE_HISTORY,
        verdict=sub_agents.build_chair_synthesizer(),
        prosecutor=sub_agents.build_prosecutor(),
        reviser=sub_agents.build_reviser(),  # graduated repair between rounds (2b.2)
        score_key=SK.DEFENSIBILITY,
        survived_key=SK.VERDICT_SURVIVED,
        threshold=config.DEFENSIBILITY_THRESHOLD,
        max_prosecution_rounds=config.MAX_PROSECUTION_ROUNDS,
        prosecution_should_stop=analyst.prosecution_should_stop,  # arivu's exact rollback
        prosecution_key=SK.PROSECUTION,
        prosecution_round_key=SK.PROSECUTION_ROUND,
        prosecution_history_key=SK.PROSECUTION_HISTORY,
        gate_status_key=SK.GATE_STATUS,
        human_tap=True,  # company chamber = the single HITL gate (tap-1)
        deliberation_name="sabha_deliberation",  # preserve arivu's exact ADK node name
    )
    return chamber.build_chamber(spec)


root_agent = build_root_agent()

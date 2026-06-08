"""ADK AgentEvaluator regression test for the arivu chamber.

WHAT THIS GRADES
----------------
This points `google.adk.evaluation.AgentEvaluator` at `eval/evalset.json` — a
checked-in set of PAST Sundara Coffee Co. founder decisions (the hero case is
the $39 Pro question) encoded in the google-adk `EvalSet` schema. Each case
carries a `final_response` reference (the grounded, dissent-preserving,
prosecuted verdict a reasonable board would defend) and per-case `rubrics` for
the two intended grading tracks:

  1. Verdict quality — is the verdict grounded in the org's own live numbers
     (margin, retention/churn cliff, funnel conversion), and is the minority
     position preserved as recorded dissent rather than erased into a false
     consensus?

  2. Prosecution soundness — did the verdict survive the adversarial
     do-nothing/steelman prosecutor at defensibility >= 0.80 (the chamber's
     HARD GATE)? Anything below 0.80 must roll back to "no safe decision" and
     must NOT reach the human approval gate.

  Both tracks are ACTIVE in `test_config.json`, which is rubric-aware: the
  verdict-quality rubrics run under `rubric_based_final_response_quality_v1`
  and the prosecution-soundness rubric runs under
  `rubric_based_tool_use_quality_v1`, both at threshold 0.80 — so 0.80 is a
  real graded threshold, not just prose. (Each case in `evalset.json` also
  carries its own per-case rubrics, filtered into the matching track by their
  `type`.) The 0.80 bar is deliberately NOT encoded as a ROUGE
  `response_match_score`: free-form verdict prose cannot pass an 0.80 ROUGE
  match, so the textual floor is set to a realistic 0.4 as a coarse drift
  guard alongside the rubric tracks. NOTE: ADK's rubric metrics require the
  optional eval extra (`pip install google-adk[eval]`, which pulls in pandas /
  tabulate); the LLM-judge defaults to `gemini-2.5-pro` and needs the same
  live creds as the chamber itself.

REQUIRES LIVE CREDENTIALS TO ACTUALLY RUN
-----------------------------------------
`AgentEvaluator.evaluate` re-runs the FULL chamber (Gemini frame + 5 Gemini
mantris in parallel + debate loop + Claude-on-Vertex verdict + Claude
prosecution loop) for every case, then grades. That needs live LLM creds:

    ARIVU_MODE=live  and  Vertex ADC (gcloud application-default login)
    + GOOGLE_CLOUD_PROJECT set.

Without creds this test is skipped (see the autouse fixture) so the suite stays
green in CI / offline. Run it for real with, e.g.:

    cd path/to/saakshe/arivu
    ARIVU_MODE=live GOOGLE_CLOUD_PROJECT=... \\
      path/to/saakshe/.venv/bin/python -m pytest eval/test_eval.py -s

The rubric tracks above are graded by ADK's rubric-based evaluators when run
against a rubric-aware eval config; the bundled `test_config.json` additionally
applies a lightweight textual `response_match_score` floor so the test fails
loudly if a verdict drifts far from the reference shape.
"""

from __future__ import annotations

import pathlib

import pytest

from arivu import config

pytest_plugins = ("pytest_asyncio",)

# The evalset.json must be passed by explicit file path, NOT as the eval/
# directory: AgentEvaluator's directory branch only discovers files with a
# `.test.json` suffix, so handing it the folder would silently find zero cases.
_EVALSET = str(pathlib.Path(__file__).parent / "evalset.json")
# Module that exposes `root_agent` (the assembled arivu SequentialAgent).
_AGENT_MODULE = "arivu.agent"


@pytest.fixture(scope="session", autouse=True)
def require_live_creds():
    """Skip unless live LLM creds are resolvable.

    The eval re-runs the real Gemini + Claude-on-Vertex chamber, so it is a
    no-op without credentials. Set ARIVU_MODE=live + Vertex ADC to run it.
    """
    if not config.is_live():
        pytest.skip(
            "arivu eval requires live creds (ARIVU_MODE=live + Vertex ADC); "
            "skipping — set them to grade verdict quality + prosecution "
            "soundness (defensibility >= 0.80)."
        )


@pytest.mark.asyncio
async def test_arivu_board_decisions():
    """Grade the arivu chamber on the checked-in board-decision eval set.

    Two rubric tracks (see module docstring): verdict quality and prosecution
    soundness (defensibility >= 0.80 hard gate). `num_runs` is kept low because
    each run fires the full multi-agent chamber.
    """
    from google.adk.evaluation import AgentEvaluator

    await AgentEvaluator.evaluate(
        agent_module=_AGENT_MODULE,
        eval_dataset_file_path_or_dir=_EVALSET,
        num_runs=1,
    )

"""ADK AgentEvaluator regression test for the manas memory pipeline.

WHAT THIS GRADES
----------------
This points ``google.adk.evaluation.AgentEvaluator`` at ``eval/evalset.json`` — a
checked-in set of memory-grounding cases encoded in the google-adk ``EvalSet``
schema. Each case carries a ``final_response`` reference (the grounded, source-
cited, non-contradictory memory the Curator commits, or the out-of-corpus refusal)
and per-case ``rubrics`` for the grounding-with-refusal track:

  Groundedness-with-refusal — does the curated memory cite a source for EVERY
  committed claim and stay non-contradictory, and is an out-of-corpus claim
  REFUSED (no committed claim, no fabricated figure) rather than invented? This is
  manas's safety property: the Curator gates a contradictory set to groundedness
  0.0 (it can never commit), and the Context Pack ticks v14 -> v15 only when
  groundedness clears the 0.80 bar.

The rubrics run under ``rubric_based_final_response_quality_v1`` at threshold 0.80
(see ``test_config.json``), so 0.80 is a real graded threshold, not just prose.
The 0.80 bar is deliberately NOT encoded as a ROUGE ``response_match_score`` (free-
form memory prose cannot pass an 0.80 ROUGE match); a realistic 0.4 textual floor
sits alongside the rubric track as a coarse drift guard. NOTE: ADK's rubric metrics
require the optional eval extra (``pip install google-adk[eval]``) and the LLM judge
defaults to ``gemini-2.5-pro`` (same live creds as the pipeline).

REQUIRES LIVE CREDENTIALS TO ACTUALLY RUN
-----------------------------------------
``AgentEvaluator.evaluate`` re-runs the FULL pipeline (Gemini Mind-Keeper + four
Gemini imbibers in parallel + the Claude-on-Vertex Curator verify loop) for every
case, then grades. That needs live LLM creds:

    SAAKSHE_MODE=live  and  Vertex ADC (gcloud application-default login)
    + GOOGLE_CLOUD_PROJECT set.

Without creds this test is skipped (autouse fixture) so the suite stays green in
CI / offline. Run it for real with, e.g.:

    cd path/to/saakshe
    SAAKSHE_MODE=live GOOGLE_CLOUD_PROJECT=... PYTHONPATH=. \\
      ./.venv/bin/python -m pytest manas/eval/test_eval.py -s
"""

from __future__ import annotations

import pathlib

import pytest

from common import config

pytest_plugins = ("pytest_asyncio",)

# Pass the evalset by explicit file path, NOT the eval/ directory: AgentEvaluator's
# directory branch only discovers files with a `.test.json` suffix, so handing it
# the folder would silently find zero cases.
_EVALSET = str(pathlib.Path(__file__).parent / "evalset.json")
# Module that exposes `root_agent` (the assembled manas ingestion pipeline).
_AGENT_MODULE = "manas.agent"


@pytest.fixture(scope="session", autouse=True)
def require_live_creds():
    """Skip unless live LLM creds are resolvable.

    The eval re-runs the real Gemini + Claude-on-Vertex pipeline, so it is a no-op
    without credentials. Set SAAKSHE_MODE=live + Vertex ADC to run it.
    """
    if not config.is_live():
        pytest.skip(
            "manas eval requires live creds (SAAKSHE_MODE=live + Vertex ADC); "
            "skipping — set them to grade groundedness-with-refusal (every claim "
            "cited & non-contradictory; out-of-corpus refused) at >= 0.80."
        )


@pytest.mark.asyncio
async def test_manas_memory_grounding():
    """Grade the manas pipeline on the checked-in memory-grounding eval set.

    Groundedness-with-refusal rubric track (see module docstring). `num_runs` is
    kept low because each run fires the full multi-agent pipeline.
    """
    from google.adk.evaluation import AgentEvaluator

    await AgentEvaluator.evaluate(
        agent_module=_AGENT_MODULE,
        eval_dataset_file_path_or_dir=_EVALSET,
        num_runs=1,
    )

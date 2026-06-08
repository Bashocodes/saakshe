"""ADK AgentEvaluator regression test for the kural mouth.

WHAT THIS GRADES
----------------
This points ``google.adk.evaluation.AgentEvaluator`` at ``eval/evalset.json`` — a
checked-in set of outreach campaigns (the hero case is the Pro -> $34 launch)
encoded in the google-adk ``EvalSet`` schema. Each case carries a
``final_response`` reference (the grounded, founder-voice message a careful
operator would actually send) and per-case ``rubrics`` for the two grading tracks:

  1. Outreach quality — is the message in the founder's plain, candid voice,
     does it name the trade-off, and is every factual claim supportable by the
     org's own grounding rather than generic marketing copy (and is it scoped to
     the consented audience and held for the publish gate, never blasted)?

  2. Claim soundness — did every load-bearing claim survive the Claim-Judge's
     fact-check at claim_support >= 0.80 (the mouth's HARD GATE)? Anything below
     0.80 must stay shut ('no safe message') and must NOT reach the publish gate.

  Both tracks are ACTIVE in ``test_config.json``, which is rubric-aware: the
  outreach-quality rubrics run under ``rubric_based_final_response_quality_v1``
  and the claim-soundness rubric runs under ``rubric_based_tool_use_quality_v1``,
  both at threshold 0.80 — so 0.80 is a real graded threshold, not just prose.
  The 0.80 bar is deliberately NOT encoded as a ROUGE ``response_match_score``:
  free-form outreach prose cannot pass an 0.80 ROUGE match, so the textual floor
  is a realistic 0.4 coarse drift guard alongside the rubric tracks. NOTE: ADK's
  rubric metrics require the optional eval extra (``pip install google-adk[eval]``).

REQUIRES LIVE CREDENTIALS TO ACTUALLY RUN
-----------------------------------------
``AgentEvaluator.evaluate`` re-runs the FULL mouth (Claude coordinator + 2 Gemini
scouts in parallel + the Gemini writer + the Claude Claim-Judge fact-check loop)
for every case, then grades. That needs live LLM creds:

    SAAKSHE_MODE=live  and  Vertex ADC (gcloud application-default login)
    + GOOGLE_CLOUD_PROJECT set.

Without creds this test is skipped (see the autouse fixture) so the suite stays
green in CI / offline.
"""

from __future__ import annotations

import pathlib

import pytest

from common import config

pytest_plugins = ("pytest_asyncio",)

# Pass the evalset by explicit file path (AgentEvaluator's directory branch only
# discovers ``*.test.json`` files, so handing it the folder finds zero cases).
_EVALSET = str(pathlib.Path(__file__).parent / "evalset.json")
# Module that exposes ``root_agent`` (the assembled kural SequentialAgent).
_AGENT_MODULE = "kural.agent"


@pytest.fixture(scope="session", autouse=True)
def require_live_creds():
    """Skip unless live LLM creds are resolvable.

    The eval re-runs the real Gemini + Claude-on-Vertex mouth, so it is a no-op
    without credentials. Set SAAKSHE_MODE=live + Vertex ADC to run it.
    """
    if not config.is_live():
        pytest.skip(
            "kural eval requires live creds (SAAKSHE_MODE=live + Vertex ADC); "
            "skipping — set them to grade outreach quality + claim soundness "
            "(claim_support >= 0.80)."
        )


@pytest.mark.asyncio
async def test_kural_outreach_campaigns():
    """Grade the kural mouth on the checked-in outreach eval set.

    Two rubric tracks (see module docstring): outreach quality and claim
    soundness (claim_support >= 0.80 hard gate). ``num_runs`` is kept low because
    each run fires the full multi-agent mouth.
    """
    from google.adk.evaluation import AgentEvaluator

    await AgentEvaluator.evaluate(
        agent_module=_AGENT_MODULE,
        eval_dataset_file_path_or_dir=_EVALSET,
        num_runs=1,
    )

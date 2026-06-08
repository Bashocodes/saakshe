"""ADK AgentEvaluator regression test for the kalai studio.

WHAT THIS GRADES
----------------
This points `google.adk.evaluation.AgentEvaluator` at `eval/evalset.json` — a
checked-in set of PAST Sundara Coffee Co. launch briefs (the hero case is the
Pro -> $34 pricing launch) encoded in the google-adk `EvalSet` schema. Each case
carries a `final_response` reference (the on-brand, compliance-cleared master the
studio should hand to kural) and per-case `rubrics` for the two grading tracks:

  1. Brand fidelity — is the master on the company's own brand canon (voice,
     palette, the grandfathering trust promise) rather than generic launch
     creative — i.e. would it pass the studio's Brand-Fidelity bar?

  2. Compliance clearance — does the master make only claims the brief
     authorised, with no deceptive / unsubstantiated superiority claims, so the
     FAIL-CLOSED compliance gate explicitly clears it before handoff?

  Both tracks are graded under `rubric_based_final_response_quality_v1` at
  threshold 0.80. NOTE: this 0.80 is the LLM-judge rubric threshold and is
  DISTINCT from the in-loop deterministic `FIDELITY_THRESHOLD` of 8.5 (the
  Brand-Fidelity loop bar) — different numbers, different purpose. The 0.80 bar
  is deliberately NOT encoded as a ROUGE `response_match_score`: free-form master
  copy cannot pass an 0.80 ROUGE match, so the textual floor is set to a realistic
  0.4 as a coarse drift guard alongside the rubric tracks. ADK's rubric metrics
  require the optional eval extra (`pip install google-adk[eval]`); the LLM-judge
  defaults to `gemini-2.5-pro` and needs the same live creds as the studio itself.

REQUIRES LIVE CREDENTIALS TO ACTUALLY RUN
-----------------------------------------
`AgentEvaluator.evaluate` re-runs the FULL studio (Claude Creative Director +
Gemini Designer + Gemini Copy in parallel + Brand-Fidelity loop + Claude
compliance gate) for every case, then grades. That needs live LLM creds:

    SAAKSHE_MODE=live  and  Vertex ADC (gcloud application-default login)
    + GOOGLE_CLOUD_PROJECT set.

Without creds this test is skipped (see the autouse fixture) so the suite stays
green in CI / offline. Run it for real with, e.g.:

    cd path/to/saakshe
    SAAKSHE_MODE=live GOOGLE_CLOUD_PROJECT=... \\
      PYTHONPATH=. ./.venv/bin/python -m pytest kalai/eval/test_eval.py -s
"""

from __future__ import annotations

import pathlib

import pytest

from common import config

pytest_plugins = ("pytest_asyncio",)

# The evalset.json must be passed by explicit file path, NOT as the eval/
# directory: AgentEvaluator's directory branch only discovers files with a
# `.test.json` suffix, so handing it the folder would silently find zero cases.
_EVALSET = str(pathlib.Path(__file__).parent / "evalset.json")
# Module that exposes `root_agent` (the assembled kalai SequentialAgent).
_AGENT_MODULE = "kalai.agent"


@pytest.fixture(scope="session", autouse=True)
def require_live_creds():
    """Skip unless live LLM creds are resolvable.

    The eval re-runs the real Claude + Gemini studio, so it is a no-op without
    credentials. Set SAAKSHE_MODE=live + Vertex ADC to run it.
    """
    if not config.is_live():
        pytest.skip(
            "kalai eval requires live creds (SAAKSHE_MODE=live + Vertex ADC); "
            "skipping — set them to grade brand fidelity + compliance clearance "
            "(rubric threshold 0.80)."
        )


@pytest.mark.asyncio
async def test_kalai_brand_masters():
    """Grade the kalai studio on the checked-in brand-master eval set.

    Two rubric tracks (see module docstring): brand fidelity and compliance
    clearance. `num_runs` is kept low because each run fires the full multi-agent
    studio.
    """
    from google.adk.evaluation import AgentEvaluator

    await AgentEvaluator.evaluate(
        agent_module=_AGENT_MODULE,
        eval_dataset_file_path_or_dir=_EVALSET,
        num_runs=1,
    )

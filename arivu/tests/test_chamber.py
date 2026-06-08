"""End-to-end chamber test, in demo mode (full ADK orchestration, replayed LLM).

This is the integration pin: the whole SequentialAgent runs — frame, parallel
mantris, debate loop, Claude verdict, prosecution loop, gate — and HALTS at the
gate with a defensible, survived verdict. Then the separate human-approved step
fires the executor (dry) and returns a draft resolution + the flag flip.
"""

from __future__ import annotations

from arivu import config, runner
from arivu.tools import analyst

SK = config.StateKeys


async def test_chamber_deliberates_to_a_defensible_gate():
    state = await runner.deliberate()

    # Halts at the gate — awaiting a human, nothing executed yet.
    assert state[SK.GATE_STATUS] == "awaiting_approval"

    # The verdict survived adversarial prosecution at/above the bar.
    assert state[SK.VERDICT_SURVIVED] is True
    assert float(state[SK.DEFENSIBILITY]) >= config.DEFENSIBILITY_THRESHOLD

    # Debate converged on a deterministic threshold, not "they agreed".
    assert float(state[SK.CONVERGENCE]) >= config.CONVERGENCE_THRESHOLD

    # The signature catch: the Risk lens surfaces the churn cliff that the
    # lone-analyst path misses. POS_RISK is a JSON string in state; read it
    # through the analyst parser, not the raw value.
    positions = analyst.read_positions(state)
    risk = next((p for p in positions if "downside" in p.get("lens", "")), None)
    assert risk is not None, "risk lens position missing from chamber state"
    assert "cliff" in risk.get("claim", "").lower()

    # The transcript carries an ordered gate line.
    transcript = runner.build_transcript(state)
    assert any(line["actor"].startswith("gate") for line in transcript)


async def test_execute_decision_dry_run_files_a_draft_and_flips_the_flag():
    state = await runner.deliberate()

    # Gate must be awaiting approval BEFORE we fire the executor (which mutates
    # state and flips GATE_STATUS to "executed").
    assert state[SK.GATE_STATUS] == "awaiting_approval"

    result = runner.execute_decision(state, dry_run=True)

    # A draft resolution at a real-shaped example docs URL, nothing published.
    assert result["resolution"]["url"].startswith("https://example.com/docs/draft/")
    assert result["resolution"]["dry_run"] is True
    # The config commit is the pricing feature-flag flip.
    assert result["commit"]["flag"] == "pricing.pro_tier_v2"
    assert result["commit"]["committed"] is False

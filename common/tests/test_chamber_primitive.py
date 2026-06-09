"""Standalone proof for the reusable chamber skeleton (no faculty).

A tiny scripted chamber exercises the genuinely-reusable, fiddly ADK part of
``common.chamber`` in isolation: a 2-seat parallel panel → a verdict seat → a
prosecutor seat → a fail-closed gate. The LLM seats are built by THIS test with
``common.models`` (its own demo replay), then passed into ``build_chamber`` — so
this proves the skeleton owns the topology + control logic and never the model
factory. Both the survive-to-cleared path and the never-survives → blocked
fail-closed rollback are pinned.
"""

from __future__ import annotations

from common import chamber, models

# A local demo resolver registered under a throwaway test namespace. The chamber
# skeleton never touches a model factory; the seats this test builds route their
# replay through here by (namespace, role).
_PAYLOADS = {
    "adv_a": '{"lens":"a","claim":"go","confidence":0.8}',
    "adv_b": '{"lens":"b","claim":"go","confidence":0.8}',
    "verdict": '{"decision":"do X","reasons":["r1","r2"],"dissent":"","confidence":0.85}',
    "prosecutor": '{"attack":"weak on r2","defensibility":0.84,"survived":true}',
}
models.register_demo("chtest", lambda role, req: _PAYLOADS.get(role, "{}"))


def _seat(role: str):
    from google.adk.agents import LlmAgent

    return LlmAgent(
        name=role,
        model=models.gemini_flash("chtest", role),
        instruction="x",
        output_key=f"pos_{role}",
    )


def _spec() -> "chamber.ChamberSpec":
    return chamber.ChamberSpec(
        namespace="chtest",
        panel=[_seat("adv_a"), _seat("adv_b")],
        verdict=_seat("verdict"),
        prosecutor=_seat("prosecutor"),
        score_key="defensibility",
        survived_key="survived",
        threshold=0.80,
        max_prosecution_rounds=3,
        gate_status_key="gate_status",
        human_tap=False,
    )


async def test_skeleton_runs_panel_verdict_prosecute_gate():
    state = await chamber.run_chamber(_spec(), init_state={"question": "q"})
    assert state["survived"] is True
    assert float(state["defensibility"]) >= 0.80
    assert state["gate_status"] == "cleared"  # fail-closed pass (human_tap=False)


async def test_fail_closed_rollback_when_prosecution_never_survives():
    _PAYLOADS["prosecutor"] = '{"attack":"fatal","defensibility":0.40,"survived":false}'
    try:
        state = await chamber.run_chamber(_spec(), {"question": "q"})
        assert state["survived"] is False
        assert state["gate_status"] == "blocked"  # fail-closed: no safe decision
    finally:
        # Restore the surviving payload so test ordering can't leak.
        _PAYLOADS["prosecutor"] = '{"attack":"weak on r2","defensibility":0.84,"survived":true}'

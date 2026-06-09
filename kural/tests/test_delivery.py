"""Pin the delivery chamber (Phase 4) — 4 deep readers + a planner that PICKS,
authors nothing.

kural's only owned decision is HOW to carry kalai's cleared master out: the four
disjoint readers (consent · reach · topic-fit · timing) surface delivery facts, a
Claude planner selects variant × segment × window, and a deterministic assembler
copies kalai's pre-authored ``formats[variant]`` VERBATIM. The mouth never writes a
word — the planner's schema has no ``text`` field, and the carried text is kalai's,
byte-for-byte.
"""

from __future__ import annotations

from common import config
from common.stream import EventStream
from kural import runner
from kural.state import StateKeys

_MASTER = {
    "asset_id": "a1", "brief": "b", "caption": "CAP",
    "formats": {"x": "X COPY", "ig": "IG COPY", "linkedin": "LI COPY"},
    "fidelity_score": 9.1, "compliance": "cleared", "spend_usd": 1.0,
}
_PACK = {"version": config.CANON["context_pack_from"], "topic": "pricing", "grounded": True}


async def test_four_delivery_readers_run_and_planner_picks():
    state = await runner._run_engagement(_MASTER, _PACK)
    # The four disjoint readers each produced a grounded, cited finding.
    for key in (StateKeys.DELIVERY_CONSENT, StateKeys.DELIVERY_REACH,
                StateKeys.DELIVERY_TOPIC, StateKeys.DELIVERY_TIMING):
        r = state.get(key)
        r = r if isinstance(r, dict) else runner.parse_json(r)
        assert r.get("finding") and r.get("citation")
    # The planner picked a real variant × segment × window.
    plan = state.get(StateKeys.DELIVERY_PLAN)
    plan = plan if isinstance(plan, dict) else runner.parse_json(plan)
    assert plan["variant"] in {"x", "ig", "linkedin"}
    assert plan["segment"] and plan["window"]


async def test_planner_carries_kalai_words_verbatim_authors_nothing():
    state = await runner._run_engagement(_MASTER, _PACK)
    plan = state.get(StateKeys.DELIVERY_PLAN)
    plan = plan if isinstance(plan, dict) else runner.parse_json(plan)
    # The carried text is kalai's pre-authored variant, BYTE-FOR-BYTE — kural wrote nothing.
    assert plan["text"] == _MASTER["formats"][plan["variant"]]
    assert plan["carries_kalai_words"] is True


async def test_assembler_fails_closed_to_a_real_variant_never_invents_text():
    """If the planner picks a variant that isn't pre-authored, the assembler falls
    back to a REAL pre-authored variant — it never fabricates copy."""
    from kural import delivery

    class _Ctx:
        def __init__(self, state):
            self.session = type("S", (), {"state": state})()

    state = {
        StateKeys.MASTER: {"formats": {"x": "ONLY X"}},
        StateKeys.DELIVERY_PICK: {"variant": "tiktok", "segment": "s", "window": "w"},
    }
    asm = delivery.DeliveryAssembler(name="t")
    async for _ in asm._run_async_impl(_Ctx(state)):
        pass
    plan = state[StateKeys.DELIVERY_PLAN]
    assert plan["variant"] == "x"            # fell back to the one real variant
    assert plan["text"] == "ONLY X"          # kalai's words, never invented


async def test_delivery_readers_in_transcript_no_authoring():
    res = await runner.engage(EventStream(), "fw", _MASTER, _PACK)
    actors = " ".join(l["actor"] for l in res.transcript)
    for seat in ("Consent Reader", "Reach Reader", "Topic-fit Reader",
                 "Timing Reader", "Delivery Planner"):
        assert seat in actors
    assert "Outreach Writer" not in actors and "Claim Judge" not in actors
    # The post still carries kalai's full formats untouched, plus the delivery pick.
    post = res.state["post"]
    assert post["drafts"] == _MASTER["formats"]
    assert post["delivery"]["text"] == _MASTER["formats"][post["delivery"]["variant"]]

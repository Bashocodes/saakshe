"""End-to-end studio test, in demo mode (full ADK orchestration, replayed LLM).

The integration pin: the whole SequentialAgent runs — Creative Director (Claude),
ParallelAgent(Designer, Copy), the Brand-Fidelity LoopAgent, and the fail-closed
Compliance gate (Claude) — and make() returns the CreativeMaster handoff to kural.
The fidelity loop exits exactly on the threshold (canon climb passes at 9.1),
compliance fail-closed BLOCKS a planted-unsafe brief with no handoff, and kalai
NEVER returns channel keys / never publishes.
"""

from __future__ import annotations

from common import config
from common.stream import EventStream
from kalai import runner

_PACK = {
    "version": "v15",
    "brand_rules": ["grandfathering existing users is a stated trust promise"],
    "voice_rules": ["calm, candid, anti-hype"],
    "facts": [{"claim": "Pro moves to $34, grandfathered, 30-day notice", "source": "arivu verdict"}],
}
_BRIEF = ("Launch announcement for the decision: Raise Pro to $34 (not $39), "
          "grandfather all existing subscribers, give 30-day notice.")


# ─── happy path: handoff, cleared, fidelity 9.1 ──────────────────────────────
async def test_make_hands_off_a_cleared_master_at_fidelity_9_1():
    stream = EventStream()
    res = await runner.make(stream, "run-happy", _BRIEF, _PACK)

    assert res.status == "handoff"
    out = res.output
    assert out["compliance"] == "cleared"
    assert out["fidelity_score"] == config.CANON["fidelity_pass"]   # 9.1
    assert out["asset_id"]
    # multi-platform master.
    assert set(out["formats"]) == {"x", "ig", "linkedin"}


async def test_master_carries_a_caption_and_all_variants():
    """Separation fix #1: kalai authors ONE base caption + every channel variant.

    The caption is the single on-voice line kalai owns; the variants are the
    per-platform formats. kural will carry both untouched (it authors nothing)."""
    stream = EventStream()
    res = await runner.make(stream, "run-caption", _BRIEF, _PACK)
    out = res.output
    assert out["caption"]                        # kalai authored ONE base caption
    assert set(out["formats"]) == {"x", "ig", "linkedin"}
    assert out["compliance"] == "cleared"


async def test_master_carries_a_media_image_ref_in_demo():
    """Task 3.3: the designer's spec yields a media asset ref on the master.

    In demo mode the wrapper is pixel-free + creds-free, so the ref is the
    deterministic Vertex placeholder (vertex://imagen/placeholder/<hash>) — no
    network, no pixels. The caption + {x,ig,linkedin} formats + 9.1 fidelity pins
    stay green; this only adds the media handle kural will carry untouched."""
    stream = EventStream()
    res = await runner.make(stream, "run-media", _BRIEF, _PACK)
    out = res.output
    assert out["media"]["image_ref"]                       # the designer produced media
    assert out["media"]["image_ref"].startswith("vertex://")
    # the other pins are unmoved by adding media.
    assert out["caption"]
    assert set(out["formats"]) == {"x", "ig", "linkedin"}
    assert out["fidelity_score"] == config.CANON["fidelity_pass"]   # 9.1


async def test_make_loop_actually_climbs_the_canon_sequence():
    """Pin that the LIVE pipeline produced the sealed climb 6.8 -> 8.4 -> 9.1.

    This is the discriminator the unit tests can't give: it exercises the demo
    resolver's [FIDELITY_ROUND::n] marker reading, the increment-after check-agent,
    and the LoopAgent sequencing together. If round-threading regressed (e.g. the
    resolver always returned 6.8), this sequence would change and the test fails —
    where a bare 'fidelity_score == 9.1' assertion could still pass via a fallback."""
    stream = EventStream()
    await runner.make(stream, "run-climb", _BRIEF, _PACK)
    scores = [e.meta["fidelity_score"] for e in stream.all()
              if e.meta.get("fidelity_round")]
    assert scores == config.CANON["fidelity_climb"]   # [6.8, 8.4, 9.1]
    # and the loop exited because it CROSSED the bar at the top, not at the round cap.
    assert scores[-1] >= config.FIDELITY_THRESHOLD


async def test_fidelity_is_the_live_aggregate_not_the_canon_fallback(monkeypatch):
    """Task 3.5: the master's fidelity_score is the loop's REAL 4-scorer aggregate,
    never the 9.1 CANON constant stamped on.

    The demo climb ends at 9.1 — which is ALSO ``CANON["fidelity_pass"]`` — so an
    assertion of ``== 9.1`` cannot tell a runner that reads the real aggregate from
    one that hardcodes the constant. This test breaks that coincidence: it injects a
    RISING, NON-CANON per-seat sequence (7.0 fail → 8.8 pass) so the four real scorer
    seats report those numbers, they flow through the REAL ScorerReducer →
    FidelityCheckAgent → runner, and the master must carry the crossing value 8.8 —
    NOT 9.1. This is the "or inject" real-path test (creds-free, runs in CI): it
    proves the live climb is sourced from scored runs, not the fallback.

    Monkeypatching ``scorers.demo_subscores`` (not the module-level table) auto-reverts,
    so the sealed ``[6.8, 8.4, 9.1]`` climb pins stay green."""
    from kalai import scorers

    # Two rounds: round 1 → 7.0 (under 8.5, continue), round 2 → 8.8 (crosses, exits).
    # 8.8 ≥ 8.5 (so the master is produced) and 8.8 ≠ 9.1 (so it can't be the fallback).
    rising = {
        1: {lens: 7.0 for lens in scorers.WEIGHTS},   # aggregate → 7.0 (fail)
        2: {lens: 8.8 for lens in scorers.WEIGHTS},   # aggregate → 8.8 (pass, ≠ canon)
    }
    monkeypatch.setattr(
        scorers, "demo_subscores", lambda rnd: dict(rising[min(max(int(rnd), 1), 2)])
    )

    stream = EventStream()
    res = await runner.make(stream, "run-agg", _BRIEF, _PACK)

    assert res.status == "handoff"
    out = res.output
    assert out["compliance"] == "cleared"
    # The crossing aggregate the loop actually produced — sourced, not stamped.
    assert out["fidelity_score"] == 8.8
    # The discriminator: it is NOT the CANON fallback (which is also 9.1).
    assert out["fidelity_score"] != config.CANON["fidelity_pass"]
    # And it really climbed there from the injected sequence, crossing the bar.
    scores = [e.meta["fidelity_score"] for e in stream.all()
              if e.meta.get("fidelity_round")]
    assert scores == [7.0, 8.8]
    assert scores[-1] >= config.FIDELITY_THRESHOLD


async def test_make_emits_a2a_handoff_to_kural_on_happy_path():
    stream = EventStream()
    await runner.make(stream, "run-a2a", _BRIEF, _PACK)
    a2a_kural = [e for e in stream.all()
                 if e.kind == "a2a" and e.meta.get("a2a_to") == "kural"]
    assert len(a2a_kural) == 1
    assert a2a_kural[0].meta.get("a2a_state") == "completed"


async def test_make_reports_token_usage_for_the_witness_cost_view():
    """The two Claude seats carry gen_ai usage so the company cost view is non-empty."""
    stream = EventStream()
    await runner.make(stream, "run-cost", _BRIEF, _PACK)
    cost = stream.cost_today("run-cost")
    assert cost["llm_calls"] >= 1
    assert cost["input_tokens"] > 0


# ─── fail-closed: a planted-unsafe brief is BLOCKED, no handoff ──────────────
async def test_make_blocks_a_planted_unsafe_brief():
    stream = EventStream()
    unsafe = ("Launch banner: GUARANTEED 10x returns; this coffee is a miracle cure "
              "for fatigue. [unsafe]")
    res = await runner.make(stream, "run-unsafe", unsafe, _PACK)

    assert res.status == "no_safe_decision"
    assert res.output.get("compliance") == "blocked"
    # No master leaked, no spend disclosed.
    assert "asset_id" not in res.output
    assert "formats" not in res.output


async def test_blocked_brief_never_hands_off_to_kural():
    stream = EventStream()
    unsafe = "Banner with a competitor logo and a GUARANTEED #1 in the world claim."
    res = await runner.make(stream, "run-unsafe2", unsafe, _PACK)
    assert res.status == "no_safe_decision"
    a2a_kural = [e for e in stream.all()
                 if e.kind == "a2a" and e.meta.get("a2a_to") == "kural"]
    assert a2a_kural == []
    # And no spend action fired for a blocked master.
    spend = [e for e in stream.all() if e.kind == "action" and "spend" in e.meta]
    assert spend == []


# ─── kalai NEVER returns channel keys / never publishes ──────────────────────
async def test_make_output_carries_no_channel_keys():
    stream = EventStream()
    res = await runner.make(stream, "run-keys", _BRIEF, _PACK)
    blob = str(res.output).lower()
    for forbidden in ("api_key", "channel_key", "access_token", "bearer", "secret", "publish"):
        assert forbidden not in blob, f"kalai output leaked {forbidden!r}"


async def test_make_never_emits_a_publish_action():
    """kalai's only world-facing act is token spend — it must never publish."""
    stream = EventStream()
    await runner.make(stream, "run-nopublish", _BRIEF, _PACK)
    for e in stream.all():
        assert "publish" not in e.text.lower(), f"kalai emitted a publish-like event: {e.text}"
        assert e.meta.get("a2a_command", "").lower().find("publish") == -1


# ─── A2A render_asset skill: cleared dict, no keys; blocks unsafe ────────────
def test_render_asset_skill_returns_cleared_master_no_keys():
    from common import a2a
    out = a2a.dispatch("kalai", "render_asset", _BRIEF, _PACK)
    assert out["accepted"] is True
    assert out["compliance"] == "cleared"
    assert "channel_key" not in out and "api_key" not in out


def test_render_asset_skill_blocks_unsafe():
    from common import a2a
    out = a2a.dispatch("kalai", "render_asset",
                       "GUARANTEED miracle cure banner [unsafe]", _PACK)
    assert out["accepted"] is False
    assert out["compliance"] == "blocked"


# ─── the sealed canon: no forbidden values / names presented as canon ────────
async def test_no_forbidden_numbers_or_names_as_canon():
    stream = EventStream()
    res = await runner.make(stream, "run-canon", _BRIEF, _PACK)
    blob = str(res.output)
    for bad in config.FORBIDDEN["numbers"]:        # 0.62, 0.81
        assert str(bad) not in blob
    for name in config.FORBIDDEN["names"]:         # saksi / buddhi / rasa / doota / ...
        assert name not in blob.lower()
    # the master carries the sealed fidelity final, not a midpoint.
    assert res.output["fidelity_score"] == config.CANON["fidelity_pass"]


# ─── fail-closed fidelity + guarded render (audit hardening) ─────────────────
async def test_sub_threshold_fidelity_escalates_and_never_hands_off(monkeypatch):
    """A climb that maxes out below FIDELITY_THRESHOLD must escalate — no master,
    no canon 9.1 restamp, no A2A to kural, and no media render fired."""
    from kalai import scorers, media

    flat = {lens: 7.0 for lens in scorers.WEIGHTS}   # every round aggregates to 7.0
    monkeypatch.setattr(scorers, "demo_subscores", lambda rnd: dict(flat))

    fired = []
    monkeypatch.setattr(media, "render_still",
                        lambda *a, **k: fired.append(1) or {"image_ref": "x", "bytes": None, "spend_usd": 0.0})

    stream = EventStream()
    res = await runner.make(stream, "run-lowfid", _BRIEF, _PACK)

    assert res.status == "no_safe_decision"
    assert res.output["fidelity"] == "escalated"
    assert res.output["fidelity_score"] == 7.0
    assert res.output["fidelity_score"] != config.CANON["fidelity_pass"]
    assert not fired, "a sub-threshold master must never burn a Vertex render"
    assert not [e for e in stream.all() if e.kind == "a2a"], "no handoff to kural"


async def test_render_failure_ships_pixel_less_master(monkeypatch):
    """A raising render must not strand the run: the cleared master ships on a
    deterministic placeholder ref and still reaches the kural handoff."""
    from kalai import runner as r

    def _boom(*a, **k):
        raise RuntimeError("vertex unavailable")

    # Patch the name the runner actually calls (module attr on kalai.media).
    import kalai.media as media
    monkeypatch.setattr(media, "render_still", _boom)

    stream = EventStream()
    res = await r.make(stream, "run-renderfail", _BRIEF, _PACK)

    assert res.status == "handoff"
    assert res.output["media"]["image_ref"].startswith("vertex://imagen/placeholder/")
    warns = [e for e in stream.all() if e.meta.get("warning") == "render_failed"]
    assert warns, "the degradation must be visible on the stream, not silent"


def test_render_asset_skill_escalates_sub_threshold(monkeypatch):
    """The A2A skill mirrors make(): a failed climb returns accepted=False with the
    REAL score — the canon constant is never stamped over a failure."""
    from kalai import scorers

    flat = {lens: 7.0 for lens in scorers.WEIGHTS}
    monkeypatch.setattr(scorers, "demo_subscores", lambda rnd: dict(flat))

    out = runner._render_asset(_BRIEF, _PACK)
    assert out["accepted"] is False
    assert out["fidelity"] == "escalated"
    assert out["fidelity_score"] == 7.0

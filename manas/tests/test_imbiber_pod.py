"""Pin the imbiber pods — each source fans into 4 specialized sub-readers (5.3).

5.3 deepens manas's senses: every channel imbiber is no longer a lone reader but a
ParallelAgent of FOUR disjoint sub-readers (claims · voice-semantics · brand-visual ·
contradiction-precheck) whose disjoint sub-extractions a deterministic reducer folds
into the SAME INGEST_* shape the curator already consumes — mirroring arivu's mantri
ensembles (build_mantri_ensemble + MantriReducer) exactly.

The sacred invariant (the byte-identity proof): the reassembled INGEST_* blob is
byte-identical to today's _INGEST[channel] (claims + voice_rules + brand_rules), so
test_ingest / test_pipeline / test_groundedness stay green — the curator contract +
the groundedness arc are unchanged. The primary sub-reader (claims) lifts
_INGEST[channel] verbatim; the secondaries attach cited supporting sub-claims as
by_lens evidence.
"""

from __future__ import annotations

from manas import imbiber_pod, state as st
from manas.demo_fixtures import _INGEST


# ─── each source fans into the four sub-lenses ───────────────────────────────
async def test_each_source_fans_into_specialized_subreaders():
    pod = imbiber_pod.build("repo")
    out = await imbiber_pod.run_demo(pod, source_text="README — a tiny web app with a Pro tier.")
    # The four disjoint sub-lenses ran.
    assert set(out["by_lens"]) >= {"claims", "voice", "brand", "contradiction"}
    # The reassembled blob is the SAME shape the curator already consumes (claims,
    # each cited), and there is a real claim to cite (not vacuously empty).
    assert out["claims"]
    assert all(c.get("source") for c in out["claims"])


# ─── the byte-identity proof: the pod reassembles to today's _INGEST[channel] ─
async def test_reassembled_blob_is_byte_identical_to_today():
    """The deepening rolls UP to today's value: the pod's INGEST_* blob equals
    _INGEST[channel] exactly (claims + voice_rules + brand_rules), so the curator
    contract and the groundedness arc are unchanged."""
    for channel in ("repo", "web", "docs", "social"):
        pod = imbiber_pod.build(channel)
        out = await imbiber_pod.run_demo(pod, source_text="some real connected source text")
        canon = _INGEST[channel]
        assert out["claims"] == canon["claims"], f"{channel} claims drifted"
        assert out["voice_rules"] == canon["voice_rules"], f"{channel} voice_rules drifted"
        assert out["brand_rules"] == canon["brand_rules"], f"{channel} brand_rules drifted"


# ─── the secondaries attach cited supporting evidence (the fan-out is real) ───
async def test_secondaries_attach_cited_evidence():
    """The voice / brand / contradiction sub-readers each contribute a cited
    supporting sub-claim, so the fan-out is genuine (not a relabelled single read)."""
    pod = imbiber_pod.build("repo")
    out = await imbiber_pod.run_demo(pod, source_text="README ...")
    for lens in ("voice", "brand", "contradiction"):
        ev = out["by_lens"][lens]
        assert ev, f"{lens} sub-reader produced no evidence"
        assert ev.get("source"), f"{lens} sub-claim is uncited"


# ─── no-source: a channel with nothing connected reassembles empty (honest) ───
async def test_no_source_reassembles_empty():
    """A channel with no connected source extracts nothing — the pod honors the
    no-source marker across all four sub-lenses, so an unconnected channel stays
    empty (it must never fabricate)."""
    pod = imbiber_pod.build("docs")
    out = await imbiber_pod.run_demo(pod, source_text="")
    assert out["claims"] == []
    assert out["voice_rules"] == []
    assert out["brand_rules"] == []


# ─── build_imbibers still returns exactly 4 pods named imbiber_<role> ─────────
def test_build_imbibers_returns_four_named_pods():
    """The structure test_pipeline pins: build_imbibers returns exactly four
    SequentialAgents named imbiber_<role> (each a pod of 4 sub-readers + reducer),
    so the ParallelAgent fan-out and the two-Claude-seat count are unchanged."""
    from manas import sub_agents

    pods = sub_agents.build_imbibers()
    assert len(pods) == 4
    assert {p.name for p in pods} == {
        "imbiber_repo", "imbiber_web", "imbiber_docs", "imbiber_social"
    }
    # Each pod is a Sequential(parallel-of-4-subreaders, reducer).
    repo = next(p for p in pods if p.name == "imbiber_repo")
    panel = repo.sub_agents[0]
    assert len(panel.sub_agents) == 4
    sub_lenses = {a.name.split("__", 1)[1] for a in panel.sub_agents}
    assert sub_lenses == {"claims", "voice", "brand", "contradiction"}

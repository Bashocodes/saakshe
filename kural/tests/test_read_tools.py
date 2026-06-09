"""Pin the delivery readers' live read-tools (Phase 4.3).

In live, each of the four delivery readers holds a read-tool over the org's OWN
funnel/feed (audience-fit for the audience lenses, the timing window for the feed)
so it computes over real list/consent/topic-fit/timing numbers — not just the
seeded text. In demo the readers are tool-free (scripted replay cites the seed
bundle), so demo stays byte-identical. No live model/network call is made here:
building the agents only resolves model-id strings + attaches the tool objects.
"""

from __future__ import annotations

from kural import delivery
from kural.tools import analyst


def test_readers_are_tool_free_in_demo(monkeypatch):
    monkeypatch.setenv("SAAKSHE_MODE", "demo")
    for agent in delivery.build_delivery_readers():
        assert not agent.tools          # demo: no read-tools fire → byte-identical


def test_readers_hold_live_read_tools(monkeypatch):
    monkeypatch.setenv("SAAKSHE_MODE", "live")
    readers = {a.name: a for a in delivery.build_delivery_readers()}
    # The three audience lenses read the funnel via audience-fit; timing reads the feed.
    for name in ("delivery_consent", "delivery_reach", "delivery_topic_fit"):
        assert readers[name].tools, f"{name} should hold a live read-tool"
        assert readers[name].tools[0] is analyst.audience_fit_tool
    assert readers["delivery_timing"].tools[0] is analyst.timing_window_tool


def test_read_tools_compute_over_the_live_funnel_numbers():
    """The audience-fit / timing read-tools, given the org's live funnel/feed
    numbers, produce the consented topic-fit slice and the open-window call —
    the real reads the live readers make over their own data."""
    fit = analyst.audience_fit(list_size=1840, opens_30d=980, topic_match_pct=64)
    assert fit["reachable_30d"] == 980
    assert fit["fit_score"] == 0.64
    assert fit["qualified_estimate"] == int(980 * 0.64)   # the consented topic-fit slice

    window = analyst.timing_window(competitor_posts_7d=2, our_last_post_days=9)
    assert window["we_are_stale"] is True and window["crowded_feed"] is False
    assert "post now" in window["recommendation"]

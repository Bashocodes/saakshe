"""Outcome normalization — the loop's seventh step, at the kural edge.

The mouth published; the manas channel broker reads what the world reported back
(``kural.runner.measure`` → ``manas.read_outcomes``, since the channel keys are
custodied by manas). This module turns those raw, receiver-defined rows into cited
facts manas can learn from: it keeps only what it can cite — a ref (post id/url), a
channel, and numeric engagement metrics. Rows without a single number are dropped —
manas's no-citation-no-fact rule starts here, at the edge.
"""

from __future__ import annotations

# The metrics the normalizer will carry into a cited claim, in display order.
_METRIC_KEYS = ("reach", "impressions", "views", "clicks", "replies", "likes",
                "shares", "follows", "conversions")


def outcome_facts(rows: list[dict]) -> list[dict]:
    """Normalize raw outcome rows into cited facts manas can commit.

    One fact per row that carries at least one numeric metric; everything else
    is dropped (no number, no fact). The claim names the ref + channel and the
    source cites the stats surface, so the curator's citation rule holds.
    """
    facts: list[dict] = []
    for r in rows:
        metrics = {}
        for k in _METRIC_KEYS:
            v = r.get(k)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            metrics[k] = int(v) if float(v).is_integer() else v
        if not metrics:
            continue
        ref = str(r.get("ref") or r.get("url") or r.get("id") or "post").strip()
        channel = str(r.get("channel") or "channel").strip()
        kv = " · ".join(f"{k} {v}" for k, v in metrics.items())
        facts.append({
            "claim": f"Published {ref} on {channel}: {kv}.",
            "source": f"channel stats · {ref}",
        })
    return facts

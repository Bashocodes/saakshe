"""Outcome reading — the loop's seventh step, made real.

The mouth published; somebody must come back and ask the world what happened.
This module reads engagement outcomes from one founder-configured stats surface
(the same pure-configuration doctrine as the manas channel broker — saakshe holds
no platform keys and names no platform):

    SAAKSHE_CHANNEL_STATS_URL      — GET returns {"outcomes": [{...}, ...]}
    SAAKSHE_CHANNEL_WEBHOOK_TOKEN  — optional Bearer (shared with the broker)

Each outcome row is receiver-defined; the normalizer keeps only what it can
cite: a ref (post id/url), a channel, and numeric engagement metrics. Rows
without a single number are dropped — manas's no-citation-no-fact rule starts
here, at the edge.

Reads fail SOFT (an unreachable stats surface returns [] and the flywheel
grounds without yesterday's numbers) — only world-facing WRITES fail closed.
Unconfigured (demo / CI / creds-free) → always [] with zero network and zero
stream noise, so the demo stays byte-identical.
"""

from __future__ import annotations

import os

_TIMEOUT = 20.0

# The metrics the normalizer will carry into a cited claim, in display order.
_METRIC_KEYS = ("reach", "impressions", "views", "clicks", "replies", "likes",
                "shares", "follows", "conversions")


def stats_url() -> str:
    """The founder-configured stats surface ('' when unset)."""
    return (os.environ.get("SAAKSHE_CHANNEL_STATS_URL") or "").strip()


def pull_outcomes() -> list[dict]:
    """Fetch the raw outcome rows from the stats surface.

    Returns [] when unconfigured or on ANY failure — a flaky stats endpoint must
    never break a flywheel run (fail-soft read, mirroring grounding reads).
    """
    url = stats_url()
    if not url:
        return []
    token = (os.environ.get("SAAKSHE_CHANNEL_WEBHOOK_TOKEN") or "").strip()
    headers = {"accept": "application/json"}
    if token:
        headers["authorization"] = f"Bearer {token}"
    try:
        import httpx  # lazy — no client at import, mirrors the manas channel broker

        resp = httpx.get(url, headers=headers, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except Exception:  # noqa: BLE001 — reads fail soft
        return []
    rows = data.get("outcomes") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


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

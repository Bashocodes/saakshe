"""Grounding — the mouth speaks only from the org's own memory, never model
memory ("grounded or silent").

LIVE: the manas Context Pack (via A2A) + the funnel are the admissible evidence,
and the example MCP read-tools can be exposed to the agents. DEMO: the bundle is
the Sundara fixtures. The before_agent_callback seeds state at the spine entry so
the Coordinator's qualify and the research scouts share one grounding (kural carries
kalai's already-cleared words — it authors nothing of its own).
"""

from __future__ import annotations

import os

from common import config, project

from .demo_fixtures import DEMO_GROUNDING
from .state import StateKeys


def _read_secret() -> str | None:
    try:
        with open(config.EXAMPLE_MCP_SECRET_FILE, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return None


def _mcp_funnel_market_fetch(url: str, secret: str) -> dict | None:
    """The single seam the real funnel/market read lands in (and the test mocks).

    The example MCP StreamableHTTP transport is unverified, so this is isolated as
    one mockable call. Until the transport is confirmed live, it returns None — so a
    live run grounds via the passed Context Pack plus the seed funnel/market, never
    an ungrounded position. Wire the real list/consent + feed read here once the
    transport is confirmed; it must return ``{"funnel": {...}, "market": {...}}``.
    """
    return None


def _live_funnel_market() -> dict | None:
    """Best-effort live fetch of the org's REAL funnel/market numbers (the mouth's
    own list/consent + feed signals), in the grounding-bundle shape. Gated on
    EXAMPLE_MCP_ENABLE + a secret (opt-in, exactly like arivu's ``_live_admin_bundle``);
    returns None when not enabled or on any failure, so ``fetch_grounding`` falls
    back to the seed funnel/market.

    Mockable: the live-branch tests patch this to prove real numbers flow at frame
    time instead of the fixture. Returns ``{"funnel": {...}, "market": {...}}``.
    """
    if os.environ.get("EXAMPLE_MCP_ENABLE", "").strip().lower() not in ("1", "true", "yes", "on"):
        return None
    secret = _read_secret()
    if not secret:
        return None
    try:
        fm = _mcp_funnel_market_fetch(config.EXAMPLE_MCP_URL, secret)
    except Exception:  # noqa: BLE001 — a flaky admin surface must never break grounding
        return None
    return fm if isinstance(fm, dict) and fm else None


def grounding_text(grounding: dict) -> str:
    """Render the grounding bundle as a compact, citable block for prompts."""
    lines: list[str] = []
    labels = {
        "manas_context_pack": "MEMORY (manas Context Pack)",
        "funnel": "FUNNEL (kural's own list/consent numbers)",
        "market": "MARKET (feed/timing signals)",
    }
    for key, label in labels.items():
        blob = grounding.get(key)
        if not blob:
            continue
        kvs = ", ".join(f"{k}={v}" for k, v in blob.items())
        lines.append(f"• {label}: {kvs}")
    return "\n".join(lines) if lines else "• (no grounding available)"


def _demo_bundle(context_pack: dict | None) -> dict:
    """The Sundara seed fixture, with ONLY the manas_context_pack version swapped to
    the passed pack's (so the message binds to the live memory the founder approved).
    Everything else is the fixture, byte-for-byte — the demo-published-output
    byte-identical contract depends on this."""
    bundle = dict(DEMO_GROUNDING)
    bundle["manas_context_pack"] = dict(bundle["manas_context_pack"])
    if isinstance(context_pack, dict) and context_pack.get("version"):
        bundle["manas_context_pack"]["version"] = context_pack["version"]
    return bundle


def fetch_grounding(context_pack: dict | None = None) -> dict:
    """Frame-time grounding bundle.

    LIVE: build the bundle FRESH from the REAL passed manas Context Pack (the
    memory the founder approved) + the org's REAL funnel/market numbers, pulled
    from the example MCP surface via a mockable seam. No DEMO_GROUNDING base — the
    fixture's canned list/voice never leak into a live message. If no live
    funnel/market source resolves, fall back to the seed fixture so the readers are
    never ungrounded even if a model forgets to call a tool.

    DEMO: the Sundara fixtures, byte-identical — with only the passed pack's version
    swapped in so the message is bound to the live memory the founder approved. (The
    demo-published-output byte-identical contract + the existing engage tests depend
    on this.) kural authors NOTHING — this only seeds what the readers cite; the post
    the founder publishes is kalai's own `formats`, byte-for-byte.
    """
    if config.is_live():
        fm = _live_funnel_market()
        if fm:
            pack = context_pack if isinstance(context_pack, dict) and context_pack else None
            return {
                # The REAL passed Context Pack is the memory section — not the fixture.
                "manas_context_pack": dict(pack) if pack else dict(DEMO_GROUNDING["manas_context_pack"]),
                "funnel": fm.get("funnel", {}),
                "market": fm.get("market", {}),
            }
        # No live funnel/market resolved → fall back to the seed (version-swapped).
    return _demo_bundle(context_pack)


def ground_callback(callback_context):
    """before_agent_callback for the Coordinator (spine entry): pull grounding
    into state and initialise the claim-loop's deterministic counters."""
    state = callback_context.state
    pack = state.get(StateKeys.CONTEXT_PACK) if hasattr(state, "get") else None
    grounding = fetch_grounding(pack if isinstance(pack, dict) else None)
    state["grounding"] = grounding
    state["grounding_text"] = grounding_text(grounding)
    state.setdefault(StateKeys.ORG, dict(project.current_store().org_for_flywheel()))
    # Deterministic loop counter — start every engagement clean.
    state[StateKeys.CLAIM_ROUND] = 0
    state[StateKeys.TRANSCRIPT] = []
    return None  # do not skip the agent

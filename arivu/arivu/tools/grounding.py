"""Grounding — every advisor argues from the org's own live numbers, never model
memory ("grounded or silent").

LIVE: the example MCP surface (admin_stats, admin_analytics) is exposed to the
agents as ADK tools, and a frame-time bundle is fetched so positions can be
templated with real figures. DEMO: the bundle is the Sundara fixtures.
"""

from __future__ import annotations

import os

from .. import config
from ..demo_fixtures import DEMO_GROUNDING
from ..util import grounding_text


def _read_secret() -> str | None:
    try:
        with open(config.EXAMPLE_MCP_SECRET_FILE, "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return None


def example_mcp_toolset():
    """An ADK MCPToolset bound to the example MCP server (live grounding tools).

    Returns None when the secret is missing — or when the toolset is not explicitly
    enabled. The live MCP transport is unverified, and a failing MCP server derails
    the mantris (they retry tool calls instead of returning their position JSON).
    The mantris are already grounded by the fixture bundle in their prompt, so the
    MCP tool is an *optional* enrichment: opt in with EXAMPLE_MCP_ENABLE=true once
    the transport is confirmed.
    """
    if os.environ.get("EXAMPLE_MCP_ENABLE", "").strip().lower() not in ("1", "true", "yes", "on"):
        return None
    secret = _read_secret()
    if not secret:
        return None
    try:
        from google.adk.tools.mcp_tool import (
            MCPToolset,
            StreamableHTTPConnectionParams,
        )
    except ImportError:
        return None
    return MCPToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=config.EXAMPLE_MCP_URL,
            headers={"Authorization": f"Bearer {secret}"},
        ),
        # Only the read-side grounding tools belong in the chamber's hands.
        tool_filter=[
            "admin_stats",
            "admin_analytics",
        ],
    )


def _mcp_admin_fetch(url: str, secret: str) -> dict | None:
    """The single seam the real MCP admin read lands in (and the test mocks).

    The example MCP StreamableHTTP transport is unverified, so this is isolated as
    one mockable call. Until the transport is confirmed live, it returns None — so
    a live run grounds via the agent-held MCP tools plus the seed bundle, never an
    ungrounded position. Wire the real admin_stats/admin_analytics read here once
    the transport is confirmed; it must return the DEMO_GROUNDING bundle shape.
    """
    return None


def _live_admin_bundle() -> dict | None:
    """Best-effort live fetch of the org's REAL numbers from the example MCP admin
    surface, in the grounding-bundle shape. Gated on EXAMPLE_MCP_ENABLE + a secret
    (opt-in, exactly like ``example_mcp_toolset``); returns None when not enabled
    or on any failure, so ``fetch_grounding`` falls back to the seed bundle.

    Mockable: the live-branch tests patch this to prove real numbers flow at frame
    time instead of the fixture.
    """
    if os.environ.get("EXAMPLE_MCP_ENABLE", "").strip().lower() not in ("1", "true", "yes", "on"):
        return None
    secret = _read_secret()
    if not secret:
        return None
    try:
        bundle = _mcp_admin_fetch(config.EXAMPLE_MCP_URL, secret)
    except Exception:  # noqa: BLE001 — a flaky admin surface must never break grounding
        return None
    return bundle if isinstance(bundle, dict) and bundle else None


def _real_memory_section() -> dict | None:
    """The org's REAL brand/voice canon via manas's A2A skill, in the bundle's
    ``manas_a2a`` shape. None when manas isn't reachable (standalone arivu) or the
    corpus is ungrounded / has no rules — the seed section stays in that case."""
    try:
        from common import a2a

        if not a2a.has_skill("manas", "get_founder_context"):
            return None
        pack = a2a.dispatch("manas", "get_founder_context", "company")
    except Exception:  # noqa: BLE001 — an unreachable manas must never break grounding
        return None
    if not (isinstance(pack, dict) and pack.get("grounded")):
        return None
    voice = "; ".join(pack.get("voice_rules") or [])
    brand = "; ".join(pack.get("brand_rules") or [])
    if not (voice or brand):
        return None
    return {"brand_canon": brand, "voice": voice}


def fetch_grounding() -> dict:
    """Frame-time grounding bundle.

    LIVE: pull the org's REAL numbers from the example MCP admin surface; if no
    live source resolves, fall back to the seed bundle so a position is never
    ungrounded even if a model forgets to call a tool — but the ``manas_a2a``
    memory section is rebuilt from the REAL corpus (via manas's A2A skill) whenever
    one is reachable and grounded, so the fixture's canned brand/voice never
    replace what the founder actually imbibed. DEMO: always the seed fixtures,
    byte-identical (the four original chamber tests depend on this).
    """
    if config.is_live():
        live = _live_admin_bundle()
        if live:
            return live
        real_mem = _real_memory_section()
        if real_mem:
            bundle = dict(DEMO_GROUNDING)
            bundle["manas_a2a"] = real_mem
            return bundle
    return dict(DEMO_GROUNDING)


def ground_callback(callback_context):
    """before_agent_callback for the chair/frame agent: pull grounding into state
    and initialise the chamber's deterministic counters."""
    state = callback_context.state
    live_bundle = _live_admin_bundle() if config.is_live() else None
    # The fallback routes through fetch_grounding so the REAL corpus memory section
    # (when reachable) reaches the chamber, not the fixture's canned brand/voice.
    state[config.StateKeys.GROUNDING] = live_bundle or fetch_grounding()
    # Honest provenance: prompts label the block "live numbers" ONLY when a live
    # source actually resolved; the seed fallback is labeled as the baseline it is.
    state["grounding_live"] = bool(live_bundle)
    state["grounding_text"] = grounding_text(state[config.StateKeys.GROUNDING])
    state.setdefault(config.StateKeys.ORG, dict(config.DEFAULT_ORG))
    state.setdefault(config.StateKeys.QUESTION, config.DEFAULT_QUESTION)
    # Deterministic loop counters — start every chamber clean.
    state[config.StateKeys.DEBATE_ROUND] = 0
    state[config.StateKeys.PROSECUTION_ROUND] = 0
    state[config.StateKeys.TRANSCRIPT] = []
    return None  # do not skip the agent

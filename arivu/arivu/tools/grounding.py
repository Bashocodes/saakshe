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


def fetch_grounding() -> dict:
    """Frame-time grounding bundle.

    In demo mode this is the Sundara fixtures. In live mode the agents also hold
    the MCP tools and cite figures directly; this bundle seeds the prompts so a
    position is never ungrounded even if a model forgets to call a tool.
    """
    # NOTE(live): a direct MCP fetch can be wired here once transport/auth is
    # confirmed; until then live runs ground via the agent-held MCP tools plus
    # this seed bundle. The reasoning over these numbers is fully live.
    return dict(DEMO_GROUNDING)


def ground_callback(callback_context):
    """before_agent_callback for the chair/frame agent: pull grounding into state
    and initialise the chamber's deterministic counters."""
    state = callback_context.state
    state[config.StateKeys.GROUNDING] = fetch_grounding()
    state["grounding_text"] = grounding_text(state[config.StateKeys.GROUNDING])
    state.setdefault(config.StateKeys.ORG, dict(config.DEFAULT_ORG))
    state.setdefault(config.StateKeys.QUESTION, config.DEFAULT_QUESTION)
    # Deterministic loop counters — start every chamber clean.
    state[config.StateKeys.DEBATE_ROUND] = 0
    state[config.StateKeys.PROSECUTION_ROUND] = 0
    state[config.StateKeys.TRANSCRIPT] = []
    return None  # do not skip the agent

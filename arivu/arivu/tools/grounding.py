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


def _jsonrpc_from_response(resp) -> dict | None:
    """Parse one streamable-HTTP MCP response — plain JSON or a one-shot SSE body."""
    import json

    ctype = (resp.headers.get("content-type") or "").lower()
    if "text/event-stream" in ctype:
        for line in resp.text.splitlines():
            if not line.startswith("data:"):
                continue
            try:
                obj = json.loads(line[5:].strip())
            except ValueError:
                continue
            if isinstance(obj, dict) and ("result" in obj or "error" in obj):
                return obj
        return None
    try:
        obj = resp.json()
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _tool_result_dict(rpc: dict | None) -> dict | None:
    """Unwrap an MCP tools/call result into a plain dict — structuredContent
    first, else the first JSON text block. isError / non-dict / empty → None."""
    import json

    if not isinstance(rpc, dict):
        return None
    result = rpc.get("result")
    if not isinstance(result, dict) or result.get("isError"):
        return None
    sc = result.get("structuredContent")
    if isinstance(sc, dict) and sc:
        return sc
    for block in result.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text":
            try:
                obj = json.loads(block.get("text") or "")
            except ValueError:
                continue
            if isinstance(obj, dict) and obj:
                return obj
    return None


# tool calls → bundle keys (the DEMO_GROUNDING shape the chamber prompts expect)
_ADMIN_CALLS: tuple[tuple[str, str, dict], ...] = (
    ("admin_stats", "admin_stats", {}),
    ("admin_analytics_user_growth", "admin_analytics", {"report": "user_growth"}),
    ("admin_analytics_activity", "admin_analytics", {"report": "activity"}),
)


def _mcp_admin_fetch(url: str, secret: str) -> dict | None:
    """The real MCP admin read — a minimal streamable-HTTP JSON-RPC client.

    initialize → tools/call admin_stats / admin_analytics(report=…), normalized
    into the DEMO_GROUNDING bundle shape. Every step fails SOFT — a flaky admin
    surface yields a partial bundle or None, never an exception (the callers
    treat None as "no live source resolved" and fall back to the real corpus).
    """
    import httpx

    headers = {
        "authorization": f"Bearer {secret}",
        "content-type": "application/json",
        "accept": "application/json, text/event-stream",
    }

    def _post(client, payload):
        resp = client.post(url, json=payload, headers=headers, timeout=15.0)
        resp.raise_for_status()
        sid = resp.headers.get("mcp-session-id")
        if sid:
            headers["mcp-session-id"] = sid   # streamable-HTTP session, if served
        return _jsonrpc_from_response(resp)

    bundle: dict = {}
    try:
        with httpx.Client() as client:
            _post(client, {
                "jsonrpc": "2.0", "id": 0, "method": "initialize",
                "params": {"protocolVersion": "2025-03-26",
                           "clientInfo": {"name": "saakshe-arivu", "version": "1"},
                           "capabilities": {}},
            })
            try:   # some servers require the initialized notification, some 4xx it
                client.post(url, json={"jsonrpc": "2.0",
                                       "method": "notifications/initialized"},
                            headers=headers, timeout=15.0)
            except Exception:  # noqa: BLE001
                pass
            for ident, (key, tool, args) in enumerate(_ADMIN_CALLS, start=1):
                rpc = _post(client, {"jsonrpc": "2.0", "id": ident,
                                     "method": "tools/call",
                                     "params": {"name": tool, "arguments": args}})
                out = _tool_result_dict(rpc)
                if out:
                    bundle[key] = out
    except Exception:  # noqa: BLE001 — partial is fine; reads fail soft
        pass
    return bundle or None


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
    """The org's REAL canon via manas's A2A skill, in the bundle's ``manas_a2a``
    shape — brand/voice rules plus the top cited facts from the live corpus, so
    advisors have something REAL to cite when no admin surface resolves. None when
    manas isn't reachable (standalone arivu) or the corpus is ungrounded/empty."""
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
    fact_rows = [f for f in (pack.get("facts") or []) if isinstance(f, dict)]
    # smriti: the evidence seats are recency-weighted (fresh outcomes first) and
    # CURRENT rulings ride a dedicated precedents line — a superseded decision
    # can never be cited as current. Fail-soft to the plain top-8 slice.
    precedents = ""
    try:
        from common import smriti

        chosen = smriti.select_facts(fact_rows, limit=8)
        precedents = smriti.precedents_text(fact_rows)
    except Exception:  # noqa: BLE001 — smriti must never break a grounding fetch
        chosen = fact_rows[:8]
    facts = "; ".join(f.get("claim", "") for f in chosen if f.get("claim"))
    if not (voice or brand or facts or precedents):
        return None
    section = {"brand_canon": brand, "voice": voice}
    if facts:
        section["facts"] = facts
    if precedents:
        section["precedents"] = precedents
    return section


def fetch_grounding() -> dict:
    """Frame-time grounding bundle.

    LIVE: pull the org's REAL numbers from the example MCP admin surface; if no
    live source resolves, the bundle carries ONLY what is real — the ``manas_a2a``
    section rebuilt from the live corpus (brand/voice rules + top cited facts via
    manas's A2A skill). Fixture numbers NEVER reach a live chamber: an advisor
    with nothing real to cite must qualify or stay silent ("grounded or silent"),
    not argue from a canned 412-user company. DEMO: always the seed fixtures,
    byte-identical (the four original chamber tests depend on this).
    """
    if config.is_live():
        live = _live_admin_bundle()
        if live:
            # The real numbers AND the real canon: the corpus memory section rides
            # along (setdefault — never overwrites a server-provided section).
            real_mem = _real_memory_section()
            if real_mem:
                live.setdefault("manas_a2a", real_mem)
            return live
        bundle: dict = {}
        real_mem = _real_memory_section()
        if real_mem:
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

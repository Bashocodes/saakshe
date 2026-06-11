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


def _jsonrpc_from_response(resp) -> dict | None:
    """Parse one streamable-HTTP MCP response — plain JSON or a one-shot SSE body.
    (Same shape as arivu's grounding client — the two surfaces speak one dialect.)"""
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


# tool calls → bundle keys: the mouth's own list/consent numbers ride "funnel",
# the feed/timing signals ride "market".
_FUNNEL_MARKET_CALLS: tuple[tuple[str, str, dict], ...] = (
    ("funnel", "admin_stats", {}),
    ("market", "admin_analytics", {"report": "activity"}),
)


def _mcp_funnel_market_fetch(url: str, secret: str) -> dict | None:
    """The real funnel/market read — a minimal streamable-HTTP JSON-RPC client
    (initialize → tools/call), normalized into ``{"funnel": {...}, "market": {...}}``.

    Every step fails SOFT: a flaky or unreachable surface yields a partial bundle
    or None, never an exception — and ``fetch_grounding``'s live branch simply
    omits the funnel/market sections rather than quoting a canned number
    ("grounded or silent"). Still the single mockable seam the tests patch.
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
                           "clientInfo": {"name": "saakshe-kural", "version": "1"},
                           "capabilities": {}},
            })
            try:   # some servers require the initialized notification, some 4xx it
                client.post(url, json={"jsonrpc": "2.0",
                                       "method": "notifications/initialized"},
                            headers=headers, timeout=15.0)
            except Exception:  # noqa: BLE001
                pass
            for ident, (key, tool, args) in enumerate(_FUNNEL_MARKET_CALLS, start=1):
                rpc = _post(client, {"jsonrpc": "2.0", "id": ident,
                                     "method": "tools/call",
                                     "params": {"name": tool, "arguments": args}})
                out = _tool_result_dict(rpc)
                if out:
                    bundle[key] = out
    except Exception:  # noqa: BLE001 — partial is fine; reads fail soft
        pass
    return bundle or None


def _live_funnel_market() -> dict | None:
    """Best-effort live fetch of the org's REAL funnel/market numbers (the mouth's
    own list/consent + feed signals), in the grounding-bundle shape. Gated on
    EXAMPLE_MCP_ENABLE + a secret (opt-in, exactly like arivu's ``_live_admin_bundle``);
    returns None when not enabled or on any failure, in which case the live bundle
    simply OMITS funnel/market — readers with nothing real to cite say so
    ("grounded or silent"), they never quote the demo seed.

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
    fixture's canned list/consent/market numbers NEVER reach a live engagement: a
    reader with no real funnel to cite must say so ("grounded or silent"), not
    quote a canned 1,840-person list.

    DEMO: the Sundara fixtures, byte-identical — with only the passed pack's version
    swapped in so the message is bound to the live memory the founder approved. (The
    demo-published-output byte-identical contract + the existing engage tests depend
    on this.) kural authors NOTHING — this only seeds what the readers cite; the post
    the founder publishes is kalai's own `formats`, byte-for-byte.
    """
    if config.is_live():
        pack = context_pack if isinstance(context_pack, dict) and context_pack else None
        fm = _live_funnel_market()
        bundle: dict = {}
        if pack:
            # The REAL passed Context Pack is the memory section — not the fixture.
            bundle["manas_context_pack"] = dict(pack)
        if fm:
            bundle["funnel"] = fm.get("funnel", {})
            bundle["market"] = fm.get("market", {})
        return bundle
    return _demo_bundle(context_pack)


def ground_callback(callback_context):
    """before_agent_callback for the Coordinator (spine entry): pull grounding
    into state and reset the per-engagement transcript."""
    state = callback_context.state
    pack = state.get(StateKeys.CONTEXT_PACK) if hasattr(state, "get") else None
    grounding = fetch_grounding(pack if isinstance(pack, dict) else None)
    state["grounding"] = grounding
    state["grounding_text"] = grounding_text(grounding)
    state.setdefault(StateKeys.ORG, dict(project.current_store().org_for_flywheel()))
    state[StateKeys.TRANSCRIPT] = []
    return None  # do not skip the agent

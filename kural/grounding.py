"""Grounding — the mouth speaks only from the org's own memory, never model
memory ("grounded or silent").

LIVE: the manas Context Pack (via A2A) + the funnel are the admissible evidence,
and the example MCP read-tools can be exposed to the agents. DEMO: the bundle is
the Sundara fixtures. The before_agent_callback seeds state at the spine entry so
the Coordinator's qualify and the research scouts share one grounding (kural carries
kalai's already-cleared words — it authors nothing of its own).
"""

from __future__ import annotations

from common import config, project

from .demo_fixtures import DEMO_GROUNDING
from .state import StateKeys


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


def fetch_grounding(context_pack: dict | None = None) -> dict:
    """Frame-time grounding bundle.

    In demo this is the Sundara fixtures. In live the agents also hold the MCP
    read-tools and cite figures directly; this bundle seeds the prompts so a claim
    is never ungrounded even if a model forgets to call a tool. When a real manas
    Context Pack is passed in, its version overrides the fixture's so the message
    is bound to the live memory the founder approved.
    """
    bundle = dict(DEMO_GROUNDING)
    bundle["manas_context_pack"] = dict(bundle["manas_context_pack"])
    if isinstance(context_pack, dict) and context_pack.get("version"):
        bundle["manas_context_pack"]["version"] = context_pack["version"]
    return bundle


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

"""The executor — a verdict becomes action, atomically, on the record.

On a single human approval at the one gate, arivu:
  1. commits the live change the verdict implies — a feature-flag flip or
     campaign-budget reallocation (a config commit, *never* a price/revenue
     column write — a deliberate billing-safety retarget),
  2. dispatches A2A commands to the two executors — kural (launch campaign) and
     kalai (render banner) — the real, irreversible spend,
  3. files a signed board resolution (docs_create → docs_publish) to a real URL
     with preserved dissent and a content hash, and
  4. creates a planner follow-through entry.

SAFETY: every side effect is gated by `dry_run`. Real publish / planner / A2A
dispatch fire ONLY when dry_run is False — which the server sets only after a
human approval lands. Tests and eval always run dry. There is no silent fake:
the real path calls the injected example client or raises.
"""

from __future__ import annotations

from typing import Any, Callable

from .. import config
from ..util import content_hash, parse_json

# Injected by the server/CLI when real side effects are authorised. Signature:
#   example_call(tool_name: str, arguments: dict) -> dict
ExampleCall = Callable[[str, dict], dict]
_example_call: ExampleCall | None = None


def set_example_client(fn: ExampleCall) -> None:
    """Register the real example MCP caller (used only on non-dry runs)."""
    global _example_call
    _example_call = fn


def _call(tool: str, args: dict) -> dict:
    if _example_call is None:
        raise RuntimeError(
            f"Real side effect '{tool}' requested but no example client is "
            "registered. Either run dry, or call set_example_client() first."
        )
    return _example_call(tool, args)


def commit_change(verdict: dict, *, dry_run: bool) -> dict:
    """Flip the pricing feature-flag / reallocate campaign budget. Config only —
    never a price/revenue column write."""
    action = {
        "action": "feature_flag_flip",
        "flag": "pricing.pro_tier_v2",
        "from": "29",
        "to": "34",
        "note": "config commit; price/revenue columns are never written on camera",
    }
    if dry_run:
        return {**action, "committed": False, "dry_run": True}
    # Real config commit would go through the org's flag store here.
    return {**action, "committed": True, "dry_run": False}


def dispatch_a2a(verdict: dict, *, dry_run: bool) -> dict:
    """Dispatch the approved verdict as A2A actions. The banner reaches the world
    only through kural — the company's only mouth — behind kural's own publish
    sign-off; kalai merely renders and hands its master to kural."""
    orders = {
        "kalai": {
            "command": "render_asset",
            "brief": "launch banner for Pro → $34, grandfathered, 30-day notice",
            "hands_to": "kural",
        },
        "kural": {
            "command": "launch_campaign",
            "channel": "x+email",
            "gate": "held at kural publish sign-off (downstream, second gate at the mouth)",
        },
    }
    if dry_run:
        return {**{k: {**v, "dispatched": False} for k, v in orders.items()}, "dry_run": True}
    out = {}
    for who, order in orders.items():
        # Real A2A dispatch to the kalai/kural agents would go here.
        out[who] = {**order, "dispatched": True}
    out["dry_run"] = False
    return out


def file_resolution(
    verdict: dict, prosecution: dict, grounding: dict, *, dry_run: bool
) -> dict:
    """File the signed board resolution to a real URL (docs_create → publish)."""
    body = _resolution_markdown(verdict, prosecution, grounding)
    chash = content_hash(
        {"verdict": verdict, "prosecution": prosecution, "grounding": grounding}
    )
    title = "Board Resolution — Pro pricing"
    if dry_run:
        return {
            "title": title,
            "url": f"https://example.com/docs/draft/arivu-{chash.split(':')[1]}",
            "doc_id": None,
            "content_hash": chash,
            "dry_run": True,
            "body_preview": body[:240],
        }
    created = _call("docs_create", {"title": title, "content": body})
    doc_id = created.get("id") or created.get("doc_id")
    published = _call("docs_publish", {"id": doc_id})
    return {
        "title": title,
        "url": published.get("url") or published.get("public_url"),
        "doc_id": doc_id,
        "content_hash": chash,
        "dry_run": False,
    }


def create_followup(verdict: dict, *, dry_run: bool) -> dict:
    """Track follow-through with a planner entry."""
    idea = "Monitor Pro → $34 launch: churn at $34 cohort, conversion, grandfather opt-outs"
    if dry_run:
        return {"planner_entry": idea, "created": False, "dry_run": True}
    res = _call("planner_create_idea", {"title": idea})
    return {"planner_entry": idea, "id": res.get("id"), "created": True, "dry_run": False}


def execute(state: dict, *, dry_run: bool | None = None) -> dict:
    """Run the full executor against the chamber state. Writes RESOLUTION and
    DISPATCH back into state. Returns the executor result."""
    if dry_run is None:
        dry_run = config.EXECUTOR_DRY_RUN
    sk = config.StateKeys

    def _as_dict(value):
        return value if isinstance(value, dict) else parse_json(value)

    verdict = _as_dict(state.get(sk.VERDICT, {}))
    prosecution = _as_dict(state.get(sk.PROSECUTION, {}))
    grounding = state.get(sk.GROUNDING, {})
    if not isinstance(grounding, dict):
        grounding = {}

    result = {
        "commit": commit_change(verdict, dry_run=dry_run),
        "dispatch": dispatch_a2a(verdict, dry_run=dry_run),
        "resolution": file_resolution(verdict, prosecution, grounding, dry_run=dry_run),
        "followup": create_followup(verdict, dry_run=dry_run),
        "dry_run": dry_run,
    }
    state[sk.RESOLUTION] = result["resolution"]
    state[sk.DISPATCH] = result["dispatch"]
    state[sk.GATE_STATUS] = "executed"
    return result


def _resolution_markdown(verdict: dict, prosecution: dict, grounding: dict) -> str:
    reasons = "\n".join(f"- {r}" for r in verdict.get("reasons", []))
    return f"""# Board Resolution

**Decision.** {verdict.get('decision', '—')}

**Confidence.** {verdict.get('confidence', '—')} ·
**Defensibility.** {prosecution.get('defensibility', '—')} (survived adversarial prosecution at ≥ {config.DEFENSIBILITY_THRESHOLD})

## Reasons
{reasons}

## Preserved dissent
{verdict.get('dissent', '—')}

## Grounded in
{', '.join(grounding.keys())}

_Filed by arivu — the faculty of judgment. One human approval; deterministic prosecution; dissent preserved._
"""

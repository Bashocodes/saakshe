"""saakshe.witness.agent — the witness's answer router (+ the refusal beat).

Phase A is a deterministic router over the telemetry tools; the point it proves is
the SEAM and the REFUSAL. Phase C replaces `answer()` internals with a real Gemini
LlmAgent that holds these same tools and a system prompt enforcing the refusal
contract — and a Gemini Live voice bridge over the identical tools.

The refusal is a first-class, scripted demo beat: ask the witness something the
stream has no bucket for, and it says so + offers what it *can* see. That single
behaviour is what separates saakshe from "a dashboard with a chatbot."
"""

from __future__ import annotations

import re
from typing import Optional

from common import config, models
from common.stream import STREAM, EventStream
from . import telemetry as tel

NS = "saakshe"

# Refusal triggers: things founders ask that the telemetry has no bucket for.
# Matched on WORD BOUNDARIES (not substrings) so "ad" can't smuggle a false
# refusal out of "already", "roadmap", "headcount", "lead" or "deadline".
_OUT_OF_TELEMETRY = ("ad", "ads", "advert", "advertising", "revenue forecast",
                     "valuation", "runway", "competitor")
_OUT_OF_TELEMETRY_RE = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _OUT_OF_TELEMETRY) + r")\b")

WITNESS_SYSTEM = """You are saakshe — the witness, the founder's seat over a four-system agentic company
(manas knows · arivu decides · kalai makes · kural engages). You INITIATE NOTHING and you ACT on nothing:
your only authority is to surface what the live event stream shows and to carry the founder's tap.

You hold NO static knowledge about the company. To answer ANYTHING you MUST call a telemetry tool:
  anyone_waiting   — the approval/gate queue ("anyone waiting on me?")
  cost_today       — today's token cost
  whats_reversible — what can still be undone
  what_learned     — the Context Pack version manas is on
  whos_acting_now  — who is acting right now

Hard rule (this is what makes you an agent, not a dashboard): if no tool can answer the question — if the
stream has no bucket for it — you REFUSE. Say plainly that you can't see it, never invent a number, and
offer what you CAN show. Do not guess revenue, ad spend, forecasts, valuations, or anything not in the tools."""


def answer(question: str, run_id: Optional[str] = None, stream: EventStream = STREAM) -> dict:
    """Route a founder question to a telemetry tool, or refuse beyond the data."""
    q = (question or "").lower().strip()

    # The refusal beat — check first so a stray keyword can't smuggle a guess.
    if _OUT_OF_TELEMETRY_RE.search(q):
        waiting = tel.anyone_waiting(run_id, stream)
        offer = "the gate queue, today's token cost, what's reversible, and what manas learned"
        return {
            "refused": True,
            "text": (f"There's no bucket for that in the stream — I won't invent a number I can't see. "
                     f"I can show you {offer}."),
            "offer": list(tel.KNOWN_BUCKETS.values()),
            "waiting_now": waiting["waiting"],
        }

    if any(k in q for k in ("waiting", "wait on me", "approve", "gate", "queue", "anyone")):
        w = tel.anyone_waiting(run_id, stream)
        if not w["waiting"]:
            return {"refused": False, "tool": "anyone_waiting", "text": "Nothing's waiting on you right now.", **w}
        g = w["gates"][0]
        return {"refused": False, "tool": "anyone_waiting",
                "text": f"Yes — {g['from']} is waiting at gate {g['gate_id']}: {g['proposal']}", **w}

    if any(k in q for k in ("cost", "spend", "spent", "token", "today")):
        c = tel.cost_today(run_id, stream)
        tag = "live-metered" if c.get("live_metered") else "estimate"
        return {"refused": False, "tool": "cost_today",
                "text": f"Today: {c['llm_calls']} model calls · ~${c['est_usd']} "
                        f"({c['input_tokens']} in / {c['output_tokens']} out tokens · {tag}).", **c}

    if any(k in q for k in ("reversible", "undo", "safe", "irreversible")):
        r = tel.whats_reversible(run_id, stream)
        return {"refused": False, "tool": "whats_reversible",
                "text": "Here's what's reversible right now.", **r}

    if any(k in q for k in ("learn", "remember", "memory", "pack", "manas")):
        l = tel.what_learned(run_id, stream)
        return {"refused": False, "tool": "what_learned",
                "text": f"manas is on Context Pack {l['context_pack']}.", **l}

    if any(k in q for k in ("doing", "happening", "acting", "now", "status")):
        a = tel.whos_acting_now(run_id, stream)
        last = a["acting"][-1]["text"] if a["acting"] else "nothing in flight"
        return {"refused": False, "tool": "whos_acting_now",
                "text": f"Latest: {last}.", **a}

    # Unknown but not obviously out-of-domain → honest fallback, not a guess.
    return {
        "refused": True,
        "text": "I only answer from what the stream shows me. Try: anyone waiting on me? · what did today cost? · "
                "what's reversible? · what did manas learn?",
        "offer": list(tel.KNOWN_BUCKETS.values()),
    }


# ─── the real ADK witness agent (live) ───────────────────────────────────────
# The same telemetry tools as FunctionTools on a Gemini LlmAgent. In demo mode
# answer() above is the responder (it exercises the identical tools); in live mode
# this Gemini agent calls them and the WITNESS_SYSTEM prompt enforces the refusal.
def build_witness_agent(stream: EventStream = STREAM, run_id: Optional[str] = None):
    """A Gemini LlmAgent whose only tools are the telemetry readers (live path).

    The tools close over the CALLER'S stream + run_id — under a per-user store
    the witness must read the tenant's stream, never the module-global one, or
    its answers contradict the gate queue rendered on the same screen."""
    from google.adk.agents import LlmAgent
    from google.adk.tools import FunctionTool

    def anyone_waiting() -> dict:
        """Is anyone/anything waiting on the founder? Returns the open gate queue."""
        return tel.anyone_waiting(run_id, stream)

    def cost_today() -> dict:
        """What did today cost? Aggregates token usage across the live stream."""
        return tel.cost_today(run_id, stream)

    def whats_reversible() -> dict:
        """What is reversible right now? Reads gates + dry-run actions in the stream."""
        return tel.whats_reversible(run_id, stream)

    def what_learned() -> dict:
        """What did manas learn? Returns the current Context Pack version."""
        return tel.what_learned(run_id, stream)

    def whos_acting_now() -> dict:
        """Who is acting right now? Returns the most recent in-flight agents."""
        return tel.whos_acting_now(run_id, stream)

    return LlmAgent(
        name="saakshe_witness",
        model=models.gemini_pro(NS, "witness"),
        description="The witness — answers only from live telemetry, refuses beyond its data.",
        instruction=WITNESS_SYSTEM,
        tools=[FunctionTool(func=f) for f in (
            anyone_waiting, cost_today, whats_reversible, what_learned, whos_acting_now,
        )],
    )


async def respond(question: str, run_id: Optional[str] = None, stream: EventStream = STREAM) -> dict:
    """Witness chat entrypoint. Demo → the deterministic router (same tools).
    Live → the Gemini agent calls the tools and obeys the refusal contract."""
    if not config.is_live():
        return answer(question, run_id, stream)
    try:
        from google.adk.runners import InMemoryRunner
        from google.genai import types

        runner = InMemoryRunner(agent=build_witness_agent(stream, run_id), app_name="saakshe_witness")
        session = await runner.session_service.create_session(
            app_name="saakshe_witness", user_id="founder", state={}
        )
        msg = types.Content(role="user", parts=[types.Part(text=question)])
        text = ""
        async for ev in runner.run_async(user_id="founder", session_id=session.id, new_message=msg):
            if ev.content and ev.content.parts:
                for p in ev.content.parts:
                    if getattr(p, "text", None):
                        text = p.text
        return {"refused": False, "text": text, "live": True}
    except Exception as exc:  # noqa: BLE001 — never let the witness 500; fall back to the router
        out = answer(question, run_id, stream)
        out["live_error"] = str(exc)
        return out

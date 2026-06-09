"""manas — the imbiber pods (5.3): each source fans into 4 specialized sub-readers.

A channel imbiber is no longer a lone reader. Each is a SequentialAgent of:
  ParallelAgent([claims · voice · brand · contradiction sub-readers]) → a reducer.

The four sub-readers read the SAME channel through four disjoint sub-lenses in
parallel (anti-collapse WITHIN the channel — one prompt could never argue all
four), writing disjoint sub-keys; the reducer folds them into the SAME INGEST_*
blob the curator already consumes — now carrying a cited `by_lens` evidence map.

The consolidated claims/voice_rules/brand_rules are lifted VERBATIM from the
PRIMARY sub-reader (claims), so the rolled-up INGEST_* stays byte-identical to
today's _INGEST[channel] (the curator contract + the groundedness arc are
unchanged); the three secondaries attach as cited supporting sub-claims.

This mirrors arivu/arivu/sub_agents.py (build_mantri_ensemble + MantriReducer)
EXACTLY — the proven per-lens fan-out template — scoped to manas's channels.

Every dynamic instruction is an InstructionProvider callable so we build the
prompt from live state ourselves — no ADK brace-templating, JSON schemas safe.
"""

from __future__ import annotations

from typing import Any, AsyncGenerator

from google.adk.agents import BaseAgent, LlmAgent, ParallelAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.events import Event, EventActions

from common import models
from . import prompts
from . import state as st
from .tools.curator import parse_json

NS = "manas"


# ─── context helpers (mirror sub_agents._org_name) ───────────────────────────
def _org_name(ctx: ReadonlyContext) -> str:
    org = ctx.state.get(st.StateKeys.ORG) or {}
    if isinstance(org, dict):
        return org.get("name") or "the company"
    return str(org) or "the company"


def _sub_state_key(ingest_key: str, sub: str) -> str:
    """The disjoint sub-key a sub-reader writes (e.g. ingest_repo__claims)."""
    return f"{ingest_key}__{sub}"


# ─── one sub-reader's instruction (the channel read through ONE sub-lens) ─────
def _subreader_instruction(channel: str, sub: str, display: str, sub_display: str,
                           channel_desc: str, source_key: str):
    def provider(ctx: ReadonlyContext) -> str:
        src = ctx.state.get(source_key) or ""
        base = (
            prompts.IMBIBER_SUBREADER_BASE
            .replace("{sub_display}", sub_display)
            .replace("{display}", display)
            .replace("{org}", _org_name(ctx))
            .replace("{channel}", channel_desc)
            .replace("{source}",
                     (str(src)[:20000] if src else "(no source connected for this channel)"))
        )
        steer = prompts.IMBIBER_SUBLENS.get(sub, "")
        return base + f"\nSUB-LENS FOCUS: {steer}\n"

    return provider


class ImbiberReducer(BaseAgent):
    """Deterministically fold the four disjoint sub-reads into the channel's
    consolidated INGEST_* blob. No model — pure assembly, so the rolled-up
    claims/voice_rules/brand_rules stay byte-identical to today's _INGEST[channel]
    while the blob gains a cited `by_lens` evidence map of four sub-extractions.

    The consolidated claims + rules are lifted VERBATIM from the PRIMARY sub-reader
    (claims); the three secondaries (voice · brand · contradiction) attach only as
    cited supporting sub-claims — they never alter what the curator commits."""

    channel: str
    ingest_key: str
    primary_sub: str
    sub_keys: dict[str, str]   # sub_lens -> the disjoint state key it wrote

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        by_lens: dict[str, dict] = {}
        primary: dict = {}
        for sub, _display in st.IMBIBER_SUBLENSES:
            raw = state.get(self.sub_keys[sub])
            d = raw if isinstance(raw, dict) else parse_json(raw)
            if sub == self.primary_sub:
                primary = d
                # The primary's own evidence entry is its lead claim (if any).
                lead = (d.get("claims") or [{}])[0] if isinstance(d, dict) else {}
                by_lens[sub] = {
                    "sub_lens": "claims",
                    "claim": lead.get("claim", "") if isinstance(lead, dict) else "",
                    "source": lead.get("source", "") if isinstance(lead, dict) else "",
                }
            else:
                by_lens[sub] = {
                    "sub_lens": d.get("sub_lens", sub),
                    "claim": d.get("claim", ""),
                    "source": d.get("source", d.get("citation", "")),
                }

        # The consolidated blob: claims + voice_rules + brand_rules lifted VERBATIM
        # from the primary sub-reader (byte-identical roll-up), plus the disjoint
        # sub-reads as a cited by_lens evidence map.
        consolidated = {
            "channel": primary.get("channel", self.channel),
            "claims": list(primary.get("claims", [])),
            "voice_rules": list(primary.get("voice_rules", [])),
            "brand_rules": list(primary.get("brand_rules", [])),
            "by_lens": by_lens,
        }
        delta = {self.ingest_key: consolidated}
        state.update(delta)
        yield Event(author=self.name, actions=EventActions(state_delta=delta))


def build(channel: str) -> SequentialAgent:
    """One channel imbiber as a 4-sub-reader parallel pod + a deterministic reducer.

    Returns a SequentialAgent named `imbiber_{channel}` (the structure test_pipeline
    pins), so it drops into the ingestion ParallelAgent exactly where the lone
    imbiber used to sit."""
    display, source_key, ingest_key, channel_desc = st.channel_meta(channel)
    subs: list[LlmAgent] = []
    sub_keys: dict[str, str] = {}
    for sub, sub_display in st.IMBIBER_SUBLENSES:
        sub_role = f"{channel}__{sub}"
        sub_key = _sub_state_key(ingest_key, sub)
        sub_keys[sub] = sub_key
        subs.append(
            LlmAgent(
                name=f"subreader_{channel}__{sub}",
                model=models.gemini_flash(NS, sub_role),
                description=f"The {sub_display} sub-reader of the {display}.",
                instruction=_subreader_instruction(
                    channel, sub, display, sub_display, channel_desc, source_key),
                output_key=sub_key,
            )
        )
    panel = ParallelAgent(
        name=f"imbiber_{channel}_pod",
        description=f"The {display} — four disjoint sub-readers on the {channel} channel.",
        sub_agents=subs,
    )
    reducer = ImbiberReducer(
        name=f"imbiber_{channel}_reducer",
        channel=channel,
        ingest_key=ingest_key,
        primary_sub=st.imbiber_primary(),
        sub_keys=sub_keys,
    )
    return SequentialAgent(
        name=f"imbiber_{channel}",
        description=f"The {display} — {channel_desc} (4-sub-reader pod).",
        sub_agents=[panel, reducer],
    )


async def run_demo(pod: SequentialAgent, source_text: str = "") -> dict[str, Any]:
    """Drive ONE pod over a seeded source and return the reassembled INGEST_* blob.

    A small InMemoryRunner helper (mirrors arivu.runner.deliberate) used by the pod
    tests to prove the fan-out + byte-identity without driving the whole pipeline.
    The pod name carries the channel, so we seed the matching SOURCE_* key."""
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    channel = pod.name.removeprefix("imbiber_")
    _display, source_key, ingest_key, _desc = st.channel_meta(channel)

    runner = InMemoryRunner(agent=pod, app_name="manas_imbiber_pod")
    init_state: dict[str, Any] = {st.StateKeys.TOPIC: "company", st.StateKeys.ORG: {}}
    if source_text:
        init_state[source_key] = source_text
    session = await runner.session_service.create_session(
        app_name="manas_imbiber_pod", user_id="founder", state=init_state
    )
    msg = types.Content(role="user", parts=[types.Part(text="imbibe this channel")])
    async for _e in runner.run_async(user_id="founder", session_id=session.id, new_message=msg):
        pass
    final = await runner.session_service.get_session(
        app_name="manas_imbiber_pod", user_id="founder", session_id=session.id
    )
    raw = dict(final.state).get(ingest_key)
    return raw if isinstance(raw, dict) else parse_json(raw)

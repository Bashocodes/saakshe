"""manas — the assembled mind. Exports ``root_agent`` and ``founder_voice_agent``.

Two real ADK agents:

  root_agent (the ingestion → curate → commit pipeline):
      mind_keeper (Gemini Pro · routes ingestion)
        → ParallelAgent: 4 imbibers (Gemini Flash · disjoint modalities, in parallel)
        → LoopAgent: curate (Claude curator + deterministic groundedness check)
        → commit (ticks the Context Pack vN → vN+1, or rolls back)

  founder_voice_agent (the query path · Claude · output_schema-forced):
      a single LlmAgent that answers AS the founder grounded ONLY in corpus and
      REFUSES out-of-corpus (refused=True, empty citations).

Parallel and Loop are EARNED here: batch ingestion across four disjoint modalities
genuinely needs ParallelAgent (no shared state, no ordering), and verify-before-
commit genuinely needs Loop (synthesise → verify every claim cites a source & is
non-contradictory → revise). Every loop exits on a numeric groundedness threshold
or a max-iteration rollback — never on "the claims look grounded."

manas KNOWS: it never acts, posts, or decides — there is no executor here, no gate,
no side effect. The only write is to its own memory, and that write is gated by the
deterministic groundedness check, not a human tap.
"""

from __future__ import annotations

from typing import AsyncGenerator

from google.adk.agents import BaseAgent, LoopAgent, ParallelAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions

from common import config
from . import state as st
from . import sub_agents
from .tools import curator


# ─── Deterministic termination agent (no model — pure safety logic) ──────────
class CuratorCheckAgent(BaseAgent):
    """Computes groundedness from the Curator's proposed claims and escalates.

    Reads the claims the Claude curator proposes, runs the PURE math in
    tools.curator (every claim cites a source & the set is non-contradictory),
    and escalates the loop on a numeric threshold; a max-iteration cap triggers a
    rollback ('no safe commit'). A detected contradiction gates groundedness to
    0.0, so the Curator can never commit a self-contradicting memory.
    """

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        rnd = int(state.get(st.StateKeys.CURATE_ROUND, 0)) + 1
        claims = curator.read_claims(state)
        groundedness = curator.compute_groundedness(claims, rnd)
        stop, committed, reason = curator.curate_should_stop(groundedness, rnd)
        history = list(state.get(st.StateKeys.CURATE_HISTORY, []))
        history.append({"round": rnd, "groundedness": groundedness,
                        "committed": committed, "reason": reason})
        delta = {
            st.StateKeys.CURATE_ROUND: rnd,
            st.StateKeys.GROUNDEDNESS: groundedness,
            st.StateKeys.CURATE_DONE: stop,
            st.StateKeys.CURATE_COMMITTED: committed,
            st.StateKeys.CURATE_HISTORY: history,
        }
        state.update(delta)
        yield Event(author=self.name, actions=EventActions(state_delta=delta, escalate=stop))


class CommitAgent(BaseAgent):
    """The memory write. Ticks the Context Pack vN → vN+1 on a survived curation,
    or records a rollback — the pipeline ends here. No human gate (manas KNOWS,
    it does not ask the founder to approve remembering)."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        committed = bool(state.get(st.StateKeys.CURATE_COMMITTED, False))
        frm = config.CANON["context_pack_from"]
        to = config.CANON["context_pack_to"]
        if committed:
            delta = {
                st.StateKeys.PACK_FROM: frm,
                st.StateKeys.PACK_TO: to,
                st.StateKeys.COMMIT_STATUS: "committed",
            }
        else:
            delta = {
                st.StateKeys.PACK_FROM: frm,
                st.StateKeys.PACK_TO: frm,          # no tick — memory unchanged
                st.StateKeys.COMMIT_STATUS: "no_safe_commit",
            }
        state.update(delta)
        yield Event(author=self.name, actions=EventActions(state_delta=delta))


# ─── before-run callback: seed the deterministic counters clean ──────────────
def _seed_callback(callback_context):
    state = callback_context.state
    state.setdefault(st.StateKeys.ORG, {})            # real org seeded by the runner
    state.setdefault(st.StateKeys.TOPIC, "pricing")
    state[st.StateKeys.CURATE_ROUND] = 0
    state[st.StateKeys.CURATE_HISTORY] = []
    return None  # do not skip the agent


# ─── Assemble the mind ───────────────────────────────────────────────────────
def build_root_agent() -> SequentialAgent:
    ingestion = ParallelAgent(
        name="manas_ingestion",
        description="Four disjoint imbibers ingest in parallel — batch fan-out across modalities.",
        sub_agents=sub_agents.build_imbibers(),
    )
    curate_loop = LoopAgent(
        name="curate_loop",
        description="Synthesise ↔ verify until groundedness ≥ 0.80 or a no-safe-commit rollback.",
        sub_agents=[sub_agents.build_curator(), CuratorCheckAgent(name="curator_check")],
        max_iterations=config.MAX_CURATE_ROUNDS,
    )
    keeper = sub_agents.build_mind_keeper()
    keeper.before_agent_callback = _seed_callback
    return SequentialAgent(
        name="manas",
        description=(
            "manas — the company's one memory. Imbibes the founder + the world's pulse "
            "into a versioned, source-cited Context Pack; verifies before it commits; "
            "never acts, posts, or decides."
        ),
        sub_agents=[keeper, ingestion, curate_loop, CommitAgent(name="commit")],
    )


def build_founder_voice_agent() -> BaseAgent:
    """The query path: a single Claude LlmAgent that refuses out-of-corpus."""
    return sub_agents.build_founder_voice()


root_agent = build_root_agent()
founder_voice_agent = build_founder_voice_agent()

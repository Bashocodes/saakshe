"""manas — the company's MIND (KNOWS). Imbibes the founder + the world's pulse
into one versioned, source-cited memory; never acts, posts, or decides; refuses
out-of-corpus rather than fabricate.

A real ADK agent-starter-pack module at arivu quality:
  * root_agent          — ingestion pipeline: Mind-Keeper route → ParallelAgent
                          imbibers → Curator LoopAgent (verify-before-commit) → commit
  * founder_voice_agent — the query path (Claude · output_schema-forced) that
                          REFUSES out-of-corpus

Importing the package registers the demo payload resolver (via sub_agents) and the
A2A skills + agent card (via runner), behind the LOCKED runner interface the
orchestrator and tests/test_flywheel.py call. The root agents are exported lazily
so importing for config/tools/tests does not require the full ADK runtime.
"""

from . import sub_agents  # noqa: F401  (registers the demo resolver at import)
from . import runner      # noqa: F401  (registers A2A skills + agent card at import)

__all__ = ["runner", "root_agent", "founder_voice_agent"]


def __getattr__(name):
    if name in ("root_agent", "founder_voice_agent"):
        from . import agent

        return getattr(agent, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

"""kural — the only mouth (ENGAGES). Discovers, researches in parallel, writes
outreach worth reading, fact-checks every claim, sends as the buyer, and publishes
kalai's approved creative behind the founder's publish sign-off (tap 2). Holds the
channel keys; never edits creative; never says unverified things; never blasts;
never publishes without the gate.

The real ADK pipeline lives in ``kural.agent`` (root_agent: Coordinator →
ParallelAgent research → Writer → Claim-Judge gate, halting before publish).
``kural.runner`` drives it behind the LOCKED orchestrator-facing interface and is
where the company's A2A skill + agent card are registered. ``root_agent`` is
exported lazily so importing the package for config/tools/tests does not require
the full ADK runtime or live credentials.

Importing this package registers kural's demo payload resolver with the shared
model factory (so the scripted-replay net is armed) and the kural A2A skill/card.
"""

from . import demo_fixtures  # noqa: F401  (registers the demo resolver at import)
from . import runner  # noqa: F401  (registers the A2A skill + agent card)

__all__ = ["runner", "root_agent"]


def __getattr__(name):
    if name == "root_agent":
        from .agent import root_agent

        return root_agent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

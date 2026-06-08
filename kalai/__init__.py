"""kalai — the studio (MAKES). Turns an approved brief into a finished, on-brand,
compliance-cleared multi-platform master and hands it to kural. Holds no channel
keys, never publishes; its only world-facing act is token spend.

The real ADK studio: Creative Director (Claude · Vertex) → Parallel(Designer +
Copy) → Brand-Fidelity LoopAgent → fail-closed Compliance gate (Claude · Vertex).
Exactly two Claude-via-Vertex seats; everything else Gemini.

At import we register kalai's deterministic demo resolver with the shared model
factory, so ScriptedLlm can replay the studio creds-free; ``root_agent`` is
exported lazily so importing for config/tools/tests doesn't require the ADK runtime.
"""

from common import models as _models
from . import demo_fixtures as _demo
from . import runner  # noqa: F401  (registers the kalai.render_asset A2A skill + card)

# Wire #1: the shared ScriptedLlm dispatches by (namespace, role) → this resolver.
# Without this, every scripted call returns "{}" and the loop misbehaves silently.
_models.register_demo("kalai", _demo.scripted_payload)

__all__ = ["runner", "root_agent"]


def __getattr__(name):
    if name == "root_agent":
        from .agent import root_agent

        return root_agent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

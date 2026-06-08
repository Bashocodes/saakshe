"""arivu — the faculty of judgment.

A multi-agent deliberation chamber on the Google Agent Development Kit. The root
agent is exported lazily so importing the package for config/tools/tests does not
require the full ADK runtime or live credentials.
"""

__all__ = ["root_agent"]


def __getattr__(name):
    if name == "root_agent":
        from .agent import root_agent

        return root_agent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

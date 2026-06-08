"""saakshe — the witness (the founder's seat). Initiates nothing; answers only
from the live stream; refuses beyond its data. That refusal is what makes the
witness itself an agent, not a dashboard.

Phase A: the telemetry tools + a deterministic answer router (the refusal is a
first-class, scripted beat). Phase C wraps these exact tools as a real Gemini
LlmAgent (text) + a Gemini Live voice bridge.
"""
from . import telemetry  # noqa: F401

__all__ = ["telemetry", "agent"]

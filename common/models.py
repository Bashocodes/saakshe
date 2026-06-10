"""saakshe.common — the shared model factory.

Routine intelligence (coordinators, fan-out specialists, in-loop scorers) runs on
**Gemini**. The two highest-stakes seats in every quadrant run on **Claude via
Vertex AI Model Garden** — a separate, stronger model than the one that produced
the work it must now judge, and the challenge's third-party-LLM-via-Vertex path.

If live credentials don't resolve, the factory returns a deterministic offline
model so the *orchestration* (Parallel / Loop / escalate / HITL / executor / A2A)
still runs end-to-end — only token generation is replayed. Live is the product;
the replay is the net that lets the whole flywheel demo creds-free and survive a
429 mid-demo. This mirrors arivu's model.py exactly so the company is one piece.
"""

from __future__ import annotations

import os
from functools import cached_property
from typing import AsyncGenerator, Callable

from google.adk.models.anthropic_llm import Claude
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from . import config


# ─── Claude on Vertex, pinned to its own region ──────────────────────────────
class VertexClaude(Claude):
    """Claude on Vertex reading ``SAAKSHE_CLAUDE_LOCATION`` (not the Gemini region).

    Stock ADK ``Claude`` reads ``GOOGLE_CLOUD_LOCATION`` — the same env Gemini
    uses — which would force both models into one region. Claude on Vertex is
    region-restricted, so we override the client to read the Claude region and
    leave Gemini's region free.
    """

    @cached_property
    def _anthropic_client(self):  # type: ignore[override]
        from anthropic import AsyncAnthropicVertex

        project = config.GOOGLE_CLOUD_PROJECT or os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not project:
            raise ValueError("GOOGLE_CLOUD_PROJECT must be set for Claude on Vertex.")
        return AsyncAnthropicVertex(project_id=project, region=config.CLAUDE_LOCATION)


# ─── Deterministic offline replay ────────────────────────────────────────────
# Each quadrant registers a payload resolver under its namespace; the scripted
# model dispatches to it by (namespace, role). Keeps demo fixtures per-quadrant
# while the scripted-model machinery is shared.
_RESOLVERS: dict[str, Callable[[str, object], str]] = {}


def register_demo(namespace: str, resolver: Callable[[str, object], str]) -> None:
    """Register a quadrant's demo payload resolver: (role, llm_request) -> text."""
    _RESOLVERS[namespace] = resolver


class ScriptedLlm(BaseLlm):
    """Returns a fixed, role-appropriate response from the registered resolver.
    Exercises the real ADK orchestration without any network/credentials."""

    namespace: str = "generic"
    role: str = "generic"

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"scripted/.*"]

    async def generate_content_async(
        self, llm_request, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        resolver = _RESOLVERS.get(self.namespace)
        text = resolver(self.role, llm_request) if resolver else "{}"
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=text)])
        )


# ─── Public factory ──────────────────────────────────────────────────────────
def gemini_pro(namespace: str = "saakshe", role: str = "coordinator"):
    if config.is_live():
        return config.MODEL_PRO
    return ScriptedLlm(model=f"scripted/{namespace}/{role}", namespace=namespace, role=role)


def gemini_flash(namespace: str, role: str):
    if config.is_live():
        return config.MODEL_FLASH
    return ScriptedLlm(model=f"scripted/{namespace}/{role}", namespace=namespace, role=role)


def claude(namespace: str, role: str):
    """One of the two Claude-via-Vertex high-stakes seats in a quadrant.

    Claude when config.claude_live(); otherwise, in a live run, the seat falls to
    a LIVE Gemini Pro understudy (real reasoning for arbitrary questions — never
    canned tokens in a live product) while the Vertex Anthropic quota is pending.
    Scripted replay exists ONLY in the creds-free demo/CI mode.
    """
    if config.claude_live():
        return VertexClaude(model=config.MODEL_CLAUDE)
    if config.is_live():
        return config.MODEL_PRO
    return ScriptedLlm(model=f"scripted/{namespace}/{role}", namespace=namespace, role=role)


def describe() -> dict:
    """Human-readable summary of what will actually run — surfaced in the UI."""
    live = config.is_live()
    claude_live = config.claude_live()
    return {
        "mode": config.mode() + ("" if claude_live or not live else " (hybrid: Claude seats on Gemini understudy)"),
        "routine": config.MODEL_PRO + " / " + config.MODEL_FLASH if live else "scripted-replay",
        "high_stakes": (
            (config.MODEL_CLAUDE + " · Vertex") if claude_live
            else (config.MODEL_PRO + " · Gemini understudy") if live
            else "scripted-replay"
        ),
        "vertex_project": config.GOOGLE_CLOUD_PROJECT or "(unset)",
        "gemini_region": config.GEMINI_LOCATION,
        "claude_region": config.CLAUDE_LOCATION,
        "claude_seats": config.TOTAL_CLAUDE_SEATS,
        "seats": config.TOTAL_SEATS,
    }

"""arivu — model factory.

Routine intelligence (chair-orchestration + the five mantris) runs on **Gemini**.
The two highest-stakes steps (verdict synthesis + adversarial prosecution) run on
**Claude via Vertex AI Model Garden** — the challenge's third-party-LLM-via-Vertex
path, deliberately a separate, stronger model than the one that produced the
positions it must now judge.

If live credentials don't resolve, the factory returns a deterministic offline
model so the *orchestration* (Parallel / Loop / escalate / HITL / executor) still
runs end-to-end — only token generation is replayed. Live is the product; this
replay is a thin net for CI and for surviving a 429 mid-demo.
"""

from __future__ import annotations

import json
import os
from functools import cached_property
from typing import AsyncGenerator

from google.adk.models.anthropic_llm import Claude
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types

from . import config


def configure_runtime() -> None:
    """Push resolved Vertex settings into the env ADK reads at call time."""
    if config.is_live():
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
        if config.GOOGLE_CLOUD_PROJECT:
            os.environ.setdefault("GOOGLE_CLOUD_PROJECT", config.GOOGLE_CLOUD_PROJECT)
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", config.GEMINI_LOCATION)


class VertexClaude(Claude):
    """Claude on Vertex pinned to its own region.

    ADK's stock ``Claude`` reads ``GOOGLE_CLOUD_LOCATION`` — the same env Gemini
    uses — so Gemini and Claude would be forced into one region. Claude on Vertex
    is region-restricted (us-east5 et al.), so we override the client to read
    ``ARIVU_CLAUDE_LOCATION`` and leave Gemini's region free.
    """

    @cached_property
    def _anthropic_client(self):  # type: ignore[override]
        from anthropic import AsyncAnthropicVertex

        project = config.GOOGLE_CLOUD_PROJECT or os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not project:
            raise ValueError("GOOGLE_CLOUD_PROJECT must be set for Claude on Vertex.")
        return AsyncAnthropicVertex(project_id=project, region=config.CLAUDE_LOCATION)


# ─── Deterministic offline replay ────────────────────────────────────────────
class ScriptedLlm(BaseLlm):
    """Returns a fixed, role-appropriate response. Exercises the real ADK
    orchestration without any network/credentials."""

    role: str = "generic"

    @classmethod
    def supported_models(cls) -> list[str]:
        return [r"scripted/.*"]

    async def generate_content_async(
        self, llm_request, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        from .demo_fixtures import scripted_payload

        text = scripted_payload(self.role, llm_request)
        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=text)])
        )


# ─── Public factory ──────────────────────────────────────────────────────────
def gemini_pro():
    """Model for the chair-orchestrator."""
    if config.is_live():
        return config.MODEL_CHAIR
    return ScriptedLlm(model="scripted/chair", role="chair")


def gemini_flash(role: str):
    """Model for one of the five mantris (role = economist|growth|brand|risk|ops)."""
    if config.is_live():
        return config.MODEL_MANTRI
    return ScriptedLlm(model=f"scripted/{role}", role=role)


def claude_verdict():
    """Claude via Vertex — verdict synthesis. Scripted in a hybrid run
    (Gemini live, SAAKSHE_CLAUDE_MODE=demo) while the Anthropic quota is pending."""
    if config.claude_live():
        return VertexClaude(model=config.MODEL_VERDICT)
    return ScriptedLlm(model="scripted/verdict", role="verdict")


def claude_prosecutor():
    """Claude via Vertex — adversarial prosecution. Scripted in a hybrid run."""
    if config.claude_live():
        return VertexClaude(model=config.MODEL_PROSECUTOR)
    return ScriptedLlm(model="scripted/prosecutor", role="prosecutor")


def describe() -> dict:
    """Human-readable summary of what will actually run — surfaced in the UI."""
    live = config.is_live()
    claude_live = config.claude_live()
    return {
        "mode": config.mode() + ("" if claude_live or not live else " (hybrid: Claude scripted)"),
        "chair": config.MODEL_CHAIR if live else "scripted-replay",
        "mantris": config.MODEL_MANTRI if live else "scripted-replay",
        "verdict": (config.MODEL_VERDICT + " · Vertex") if claude_live else "scripted-replay",
        "prosecutor": (config.MODEL_PROSECUTOR + " · Vertex") if claude_live else "scripted-replay",
        "vertex_project": config.GOOGLE_CLOUD_PROJECT or "(unset)",
        "gemini_region": config.GEMINI_LOCATION,
        "claude_region": config.CLAUDE_LOCATION,
    }

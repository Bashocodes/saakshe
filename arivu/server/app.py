"""arivu — FastAPI live bridge.

HTTP surface the cockpit calls to drive the deliberation chamber:

    GET  /api/arivu/health      → {mode, models}
    POST /api/arivu/run         → run a deliberation, return transcript + verdict
    POST /api/arivu/approve     → approve a halted verdict, fire the executor (dry)
    GET  /api/arivu/agent-card  → the A2A agent card

State lives in an in-process dict keyed by a uuid4 run_id — no DB, no disk.
The chamber HALTS at the gate inside /run; nothing is committed or published
there. /approve is the separate, human-in-the-loop step, and it stays a
**dry run** unless ARIVU_SERVER_ALLOW_LIVE_EXEC=true *and* config.is_live() —
the server never fires a real side effect on its own.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from arivu import config, runner
from arivu import models as arivu_models
from arivu.util import parse_json

# Local OpenTelemetry console tracing (the deployed Agent Engine traces to Cloud
# Trace via enable_tracing=True; this lights up the same spans for local runs).
try:  # pragma: no cover - observability is best-effort
    from arivu.callbacks import otel as _otel

    _otel.configure_tracing()
except Exception:  # noqa: BLE001
    pass

SK = config.StateKeys
_LIVE_HTML = Path(__file__).resolve().parent.parent / "arivu_live.html"

# Project root = parent of this `server/` package; the inner `arivu` package and
# agent-card.json (if present) sit alongside it. Resolved off __file__ so it
# survives any cwd reset.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_AGENT_CARD_PATH = _PROJECT_ROOT / "agent-card.json"

# In-process run store: run_id -> final chamber state dict. Deliberately ephemeral
# (lost on restart) — these are decisions awaiting a founder, not records of truth;
# the durable record is the filed board resolution the executor publishes.
_RUNS: dict[str, dict[str, Any]] = {}

app = FastAPI(
    title="arivu — deliberation chamber",
    description="HTTP bridge over the arivu multi-agent ADK chamber.",
    version="1.0.0",
)

# Permissive CORS so a file:// page (Origin: null) or the cockpit on any local
# port can call us. credentials=False is required for the "*" wildcard to be
# honoured by browsers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request bodies ──────────────────────────────────────────────────────────
class RunRequest(BaseModel):
    question: str | None = None


class ApproveRequest(BaseModel):
    run_id: str


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _verdict_dict(state: dict[str, Any]) -> dict[str, Any]:
    """Serialize the verdict to a plain dict (it is stored as a JSON string)."""
    v = state.get(SK.VERDICT, {})
    return v if isinstance(v, dict) else parse_json(v)


def _live_exec_allowed() -> bool:
    """Real side effects fire ONLY when the operator opted in AND we're live.

    In demo mode config.is_live() is False, so this is always False and every
    /approve stays a dry run regardless of the env flag — the AND-gate the
    contract requires.
    """
    flag = os.environ.get("ARIVU_SERVER_ALLOW_LIVE_EXEC", "").strip().lower()
    opted_in = flag in ("1", "true", "yes", "on")
    return opted_in and config.is_live()


def _inline_agent_card() -> dict[str, Any]:
    """Minimal A2A agent card used when agent-card.json is absent."""
    return {
        "name": "arivu",
        "description": (
            "A deliberation chamber: five advisor agents, a deterministic debate, "
            "a Claude-on-Vertex verdict, adversarial prosecution, and a single "
            "human approval gate before any action."
        ),
        "version": app.version,
        "protocol": "a2a",
        "url": "/api/arivu",
        "capabilities": {"streaming": False, "pushNotifications": False},
        "defaultInputModes": ["text"],
        "defaultOutputModes": ["text"],
        "skills": [
            {
                "id": "deliberate",
                "name": "Deliberate a founder decision",
                "description": (
                    "Decompose a question, ground it in the org's live numbers, "
                    "run five advisor lenses to a deterministic convergence, "
                    "synthesize a verdict, prosecute it adversarially, and halt "
                    "at a human approval gate."
                ),
                "tags": ["decision", "deliberation", "multi-agent", "governance"],
            }
        ],
    }


# ─── Endpoints ───────────────────────────────────────────────────────────────
@app.get("/api/arivu/health")
def health() -> dict[str, Any]:
    """Liveness + a description of which models will actually run."""
    return {"mode": config.mode(), "models": arivu_models.describe()}


@app.post("/api/arivu/run")
async def run(req: RunRequest) -> dict[str, Any]:
    """Run a full deliberation (await the chamber) and stash the halted state.

    The chamber stops at the gate — nothing is committed here. The returned
    state is keyed by a fresh run_id the caller passes back to /approve.
    """
    state = await runner.deliberate(req.question)
    run_id = uuid4().hex
    _RUNS[run_id] = state
    return {
        "run_id": run_id,
        "mode": config.mode(),
        "transcript": runner.build_transcript(state),
        "verdict": _verdict_dict(state),
        "defensibility": state.get(SK.DEFENSIBILITY),
        "gate_status": state.get(SK.GATE_STATUS),
        "survived": state.get(SK.VERDICT_SURVIVED),
    }


@app.post("/api/arivu/approve")
def approve(req: ApproveRequest) -> dict[str, Any]:
    """Approve a halted verdict and fire the executor.

    Always a dry run unless ARIVU_SERVER_ALLOW_LIVE_EXEC=true AND we're live.
    Unknown run_id → 404. A gate that is not awaiting approval → 409 (already
    executed, or never reached the gate) — the executor is not fired.
    """
    state = _RUNS.get(req.run_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"unknown run_id {req.run_id!r}")

    gate = state.get(SK.GATE_STATUS)
    if gate != "awaiting_approval":
        raise HTTPException(
            status_code=409,
            detail=f"run {req.run_id} is not awaiting approval (gate_status={gate!r})",
        )

    state[SK.GATE_STATUS] = "approved"
    dry_run = not _live_exec_allowed()
    result = runner.execute_decision(state, dry_run=dry_run)

    return {
        "run_id": req.run_id,
        "mode": config.mode(),
        "gate_status": state.get(SK.GATE_STATUS),
        "result": result,
        "transcript": runner.build_transcript(state),
    }


@app.get("/api/arivu/agent-card")
def agent_card() -> dict[str, Any]:
    """Serve the A2A agent card — from agent-card.json if present, else inline."""
    if _AGENT_CARD_PATH.exists():
        try:
            return json.loads(_AGENT_CARD_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # Corrupt/unreadable file → fall back to the inline card rather than 500.
            pass
    return _inline_agent_card()


@app.get("/", response_class=HTMLResponse)
@app.get("/live", response_class=HTMLResponse)
def live_console() -> Any:
    """Serve the live chamber console (same origin as the API → no CORS friction).

    Visiting http://localhost:8000/ gives the founder the live cockpit; its fetch
    calls hit this very server. The cockpit's ●LIVE link points straight here.
    """
    if _LIVE_HTML.exists():
        return FileResponse(_LIVE_HTML)
    return HTMLResponse(
        "<h1>arivu — live chamber</h1><p>arivu_live.html not found next to the "
        "server package.</p>",
        status_code=404,
    )

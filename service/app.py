"""saakshe — the ONE FastAPI service. The single front door behind which the four
quadrants and the witness live.

The founder talks only to saakshe (chat at /api/saakshe/ask, voice at /ws/voice).
The flywheel runs through the orchestrator (the resumable 2-gate state machine).
Every surface is a pure render of the one ordered stream (/api/stream); the gate
queue (/api/gates) is derived from it. arivu's standalone console is retired —
its chamber now runs as step 1 of the flywheel, inside saakshe.

    cd ~/Desktop/Working/saakshe && PYTHONPATH=. ./.venv/bin/uvicorn service.app:app --port 8000
    open http://localhost:8000/        → the cockpit, in live mode

Demo by default (no creds). Real side effects only when ARIVU/SAAKSHE are live AND
SAAKSHE_SERVER_ALLOW_LIVE_EXEC=true — the server never fires a real publish on its own.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel
import traceback

import common  # noqa: F401 — bootstraps arivu onto sys.path
from common import a2a, config, models, project
from common.stream import STREAM
import orchestrator
import manas.runner as manas_runner
from witness import agent as witness
from witness import telemetry as tel
from witness import voice as witness_voice

# Best-effort local OTel (the deployed Agent Engine traces to Cloud Trace).
try:  # pragma: no cover
    from arivu.callbacks import otel as _otel

    _otel.configure_tracing()
except Exception:  # noqa: BLE001
    pass

config.sync_runtime_mode()

_ROOT = Path(__file__).resolve().parents[1]          # the saakshe repo root
_WORKING = _ROOT.parent                              # legacy parent dir (pre-repo layout)
_WEB = _ROOT / "web"                                 # the site (landing, onboarding, cockpit, …)
_HOME = "saakshe_landing.html"                       # / serves the landing page
_LEGACY_COCKPIT = _WORKING / "cockpit.html"          # fallback for a pre-migration checkout
_ARIVU_CARD = _ROOT / "arivu" / "agent-card.json"

app = FastAPI(
    title="saakshe — the agentic company, behind one witness",
    description="One front door over four ADK quadrants (manas·arivu·kalai·kural) and the witness.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"],
)


@app.exception_handler(Exception)
async def _json_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Never return a plain-text 500. A live model call can raise mid-flywheel;
    the cockpit calls r.json(), so an unhandled exception MUST still be valid JSON
    (otherwise the console dies on 'Unexpected token I, Internal S…'). This turns
    every failure into a structured, renderable error."""
    print("saakshe error @", request.url.path, "\n", traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"error": type(exc).__name__, "detail": str(exc)[:600], "where": request.url.path},
    )


# ─── request bodies ──────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    text: str
    run_id: Optional[str] = None


class RunRequest(BaseModel):
    question: Optional[str] = None


class ApproveRequest(BaseModel):
    run_id: str
    gate_id: Optional[str] = None


class ConnectRequest(BaseModel):
    kind: str                       # "github" | "website" | "docs" | "social"
    ref: str                        # repo url/owner-repo, site url, docs url, handle
    mechanism: Optional[str] = None  # github: "ssh" (default) | "pat" | "public"
    token: Optional[str] = None      # github PAT (only when mechanism == "pat")


class AnswerRequest(BaseModel):
    qid: str
    answer: str


# A decision-shaped question (starts the flywheel) needs an explicit decision phrase —
# NOT a bare noun like "price", so "what's our price?" stays a telemetry question.
_DECISION_HINTS = ("should we", "should i", "should the", "run the day", "start the day",
                   "raise pro", "raise our", "raise the price", "decide whether", "decide if")


# ─── health ──────────────────────────────────────────────────────────────────
@app.get("/api/saakshe/health")
def health() -> dict[str, Any]:
    return {
        "mode": config.mode(),
        "models": models.describe(),
        "company": {"seats": config.TOTAL_SEATS, "claude_seats": config.TOTAL_CLAUDE_SEATS,
                    "quadrants": config.QUADRANTS},
        "cards": list(a2a.all_cards().keys()) + (["arivu"] if _ARIVU_CARD.exists() else []),
    }


# ─── setu · the connect bridge (empty until the founder connects a real source) ─
@app.get("/api/connect/status")
def connect_status() -> dict[str, Any]:
    """The single source of truth the cockpit boots on: connected? grounded? what
    org, what version, which open clarifying questions."""
    return project.STORE.status_dict()


@app.post("/api/connect/source")
def connect_source(req: ConnectRequest) -> dict[str, Any]:
    """Register a real source over setu (a GitHub repo, a website, docs, a social
    handle). Granted, never taken — this only records the ref; ingestion reads it."""
    kind = (req.kind or "").strip().lower()
    if kind not in ("github", "repo", "website", "web", "docs", "social"):
        raise HTTPException(status_code=400, detail=f"unknown source kind {kind!r}")
    kind = {"repo": "github", "web": "website"}.get(kind, kind)
    meta: dict[str, Any] = {}
    if kind == "github":
        meta["mechanism"] = (req.mechanism or "ssh").lower()
        if req.token:
            meta["token"] = req.token
    conn = project.STORE.add_connection(kind, req.ref.strip(), meta)
    return {"ok": True, "connection": conn.as_dict(), "status": project.STORE.status_dict()}


@app.post("/api/connect/ingest")
async def connect_ingest() -> dict[str, Any]:
    """Run the REAL manas ingestion over the connected sources: read repo + site →
    live Gemini extracts cited facts/voice/brand → commit a versioned Context Pack →
    surface any honest clarifying questions. All automatic after connect."""
    if not project.STORE.is_connected():
        raise HTTPException(status_code=409, detail="nothing connected yet — add a source first")
    run_id = "ingest_" + os.urandom(4).hex()
    result = await manas_runner.ingest_connected(STREAM, run_id, project.STORE)
    return {"run_id": run_id, **result}


@app.post("/api/connect/answer")
async def connect_answer(req: AnswerRequest) -> dict[str, Any]:
    """Answer a clarifying question; manas folds it back into the corpus + re-grounds."""
    run_id = "answer_" + os.urandom(4).hex()
    result = await manas_runner.answer_question(STREAM, run_id, req.qid, req.answer, project.STORE)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error", "no such question"))
    return result


@app.post("/api/connect/reset")
def connect_reset() -> dict[str, Any]:
    """Disconnect everything and return to empty-state (re-connect from scratch)."""
    project.STORE.reset()
    return {"ok": True, "status": project.STORE.status_dict()}


# ─── the witness chat (the founder talks ONLY to saakshe) ────────────────────
@app.post("/api/saakshe/ask")
async def ask(req: AskRequest) -> dict[str, Any]:
    """Telemetry Q&A through the witness; a decision-shaped question starts the flywheel."""
    text = (req.text or "").strip()
    low = text.lower()
    if any(h in low for h in _DECISION_HINTS) and "?" in text:
        if not project.STORE.is_grounded():
            return {"kind": "connect_first",
                    "text": "I can't run a decision on a blank memory — connect your project first "
                            "(a repo + your site), and I'll ground the company before deciding.",
                    "status": project.STORE.status_dict()}
        summary = await orchestrator.start(question=text)
        return {"kind": "flywheel_started",
                "text": "That's a real decision — routing it to arivu. A gate will land in your queue.",
                "flywheel": summary}
    reply = await witness.respond(text, req.run_id, STREAM)
    return {"kind": "witness", **reply}


# ─── the flywheel (resumable 2-gate state machine) ───────────────────────────
@app.post("/api/hero/run")
async def hero_run(req: RunRequest) -> dict[str, Any]:
    if not project.STORE.is_grounded():
        return {"status": "not_connected", "connected": project.STORE.is_connected(),
                "text": "Connect your project first — saakshe runs on YOUR company, never a canned example.",
                "connect": project.STORE.status_dict()}
    return await orchestrator.start(question=req.question)


@app.post("/api/hero/approve")
async def hero_approve(req: ApproveRequest) -> dict[str, Any]:
    try:
        return await orchestrator.approve(req.run_id, req.gate_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


# ─── the one ordered stream + the derived gate queue ─────────────────────────
@app.get("/api/stream")
def stream(cursor: int = 0, run_id: Optional[str] = None) -> dict[str, Any]:
    rows = STREAM.rows(cursor)
    if run_id:
        rows = [r for r in rows if r["run_id"] == run_id]
    return {"cursor": STREAM.cursor, "rows": rows}


@app.get("/api/gates")
def gates(run_id: Optional[str] = None) -> dict[str, Any]:
    return {"gates": STREAM.open_gates(run_id)}


# ─── witness telemetry tools (also reachable directly, for the cockpit pills) ─
@app.get("/api/witness/telemetry")
def witness_telemetry(run_id: Optional[str] = None) -> dict[str, Any]:
    return {
        "waiting": tel.anyone_waiting(run_id, STREAM),
        "cost": tel.cost_today(run_id, STREAM),
        "reversible": tel.whats_reversible(run_id, STREAM),
        "learned": tel.what_learned(run_id, STREAM),
        "acting": tel.whos_acting_now(run_id, STREAM),
    }


# ─── A2A agent cards (served manually; a2a-sdk to_a2a() pending) ──────────────
@app.get("/api/{quadrant}/agent-card")
def agent_card(quadrant: str) -> Any:
    if quadrant == "arivu" and _ARIVU_CARD.exists():
        try:
            return JSONResponse(json.loads(_ARIVU_CARD.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            pass
    card = a2a.agent_card(quadrant)
    if card is None:
        raise HTTPException(status_code=404, detail=f"no agent card for {quadrant!r}")
    return JSONResponse(card)


# ─── voice (Gemini Live; text-over-WS in demo) ───────────────────────────────
@app.websocket("/ws/voice")
async def voice(websocket: WebSocket) -> None:
    await witness_voice.handle_ws(websocket)


# ─── serve the site: landing at /, every page under web/ at /<name>.html ─────
# The whole experience lives in web/ — landing → onboarding → cockpit, plus the
# faculty pages (manas·arivu·kalai·kural·setu·darshana) and the explainers. The
# pages link each other by bare filename (href="cockpit.html"), so serving each at
# /<name>.html makes that navigation work with no link rewriting. API routes above
# are multi-segment, so this single-segment catch-all never shadows them.
def _serve_page(name: str) -> Any:
    if not name.endswith(".html"):
        name += ".html"
    if "/" in name or ".." in name:
        raise HTTPException(status_code=404, detail="not found")
    page = _WEB / name
    if page.exists():
        return FileResponse(page)
    if name == "cockpit.html" and _LEGACY_COCKPIT.exists():
        return FileResponse(_LEGACY_COCKPIT)
    raise HTTPException(status_code=404, detail=f"no page {name!r}")


@app.get("/", response_class=HTMLResponse)
def home() -> Any:
    return _serve_page(_HOME)


@app.get("/{page}", response_class=HTMLResponse)
def web_page(page: str) -> Any:
    return _serve_page(page)

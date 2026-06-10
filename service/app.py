"""saakshe — the ONE FastAPI service. The single front door behind which the four
quadrants and the witness live.

The founder talks only to saakshe (chat at /api/saakshe/ask, voice at /ws/voice).
The flywheel runs through the orchestrator (the resumable 2-gate state machine).
Every surface is a pure render of the one ordered stream (/api/stream); the gate
queue (/api/gates) is derived from it.

    cd ~/Desktop/Working/saakshe && PYTHONPATH=. ./.venv/bin/uvicorn service.app:app --port 8000
    open http://localhost:8000/        → the cockpit

AUTH + CREDITS (the gate): demo-first by default — with no Supabase backend
(SAAKSHE_STORE != supabase) there is NO sign-in and NO billing, so the public demo
and the 135 tests run unchanged. When SAAKSHE_STORE=supabase, a per-request
``Session`` resolves the founder from the verified JWT, binds their per-user store
+ stream for the request (the multi-tenant seam), and chargeable actions spend
credits (refunded on any internal failure, including the resumable flywheel's later
gates). Owners + the file-store demo are always free.
"""

from __future__ import annotations

import base64
import json
import os
import re
import tempfile
import threading
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from fastapi import (Depends, FastAPI, File, Form, HTTPException, Request,
                     UploadFile, WebSocket)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel

import common  # noqa: F401 — bootstraps arivu onto sys.path
from common import a2a, auth, config, credits, models, project
from common.stream import STREAM
from common.supastream import SupabaseEventStream
import orchestrator
import manas.runner as manas_runner
from kalai import media_crew, media_pipeline
from service import presenter
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

# ─── the real outbound channel (opt-in, generic) ──────────────────────────────
# With SAAKSHE_ALLOW_LIVE_SEND=1 + SAAKSHE_CHANNEL_WEBHOOK_URL set, kural gains a
# real ChannelCall: every armed publish/outreach POSTs to the founder's own
# delivery endpoint (an autopilot queue, a relay, a worker — pure configuration;
# saakshe names no platform). Without BOTH, tap-2 stays dry-run, exactly as before.
if os.environ.get("SAAKSHE_ALLOW_LIVE_SEND") == "1":
    try:
        from kural.tools import channels as _channels
        from kural.tools.adapters import webhook as _webhook

        _fn = _webhook.from_env()
        if _fn is not None:
            _channels.set_channel_client(_fn)
            print("kural: live channel armed → webhook adapter registered")
    except Exception:  # noqa: BLE001 — a bad adapter config must not sink the site
        traceback.print_exc()

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
    the cockpit calls r.json(), so an unhandled exception MUST still be valid JSON."""
    print("saakshe error @", request.url.path, "\n", traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"error": type(exc).__name__, "detail": str(exc)[:600], "where": request.url.path},
    )


# ─── the per-request session (auth + per-user store/stream binding) ───────────
@dataclass
class Session:
    user: Any            # auth.User | None
    store: Any           # the founder's ProjectStore / SupabaseStore (or the global)
    stream: Any          # the founder's event stream (or the global)


def _supabase_backend() -> bool:
    return os.environ.get("SAAKSHE_STORE", "").lower() == "supabase"


def _require_signin() -> bool:
    """The gated-demo switch: SAAKSHE_REQUIRE_SIGNIN=1 (with Supabase auth
    configured) puts the WHOLE API surface behind sign-in — judge credentials go
    in the Devpost testing instructions — while the store stays the seeded,
    sealed file-store demo. The sign-in surfaces themselves (HTML pages,
    /api/public-config, the health probe) stay open."""
    return os.environ.get("SAAKSHE_REQUIRE_SIGNIN", "") == "1" and auth.auth_enabled()


_GRANTED: set[str] = set()  # process cache: signup-grant a user once per process


def _ensure_account(user) -> None:
    """Idempotently create the account + first-time credit grant on first authed
    touch (the RPC is ON CONFLICT DO NOTHING; the cache just avoids a round-trip)."""
    if not user or user.user_id in _GRANTED:
        return
    try:
        credits.grant_signup(user.user_id, getattr(user, "email", ""), getattr(user, "is_owner", False))
        _GRANTED.add(user.user_id)
    except Exception:  # noqa: BLE001 — never block a request on a grant hiccup
        pass


def _stream_factory(user_id: str):
    """The per-user event stream (overridable in tests)."""
    return SupabaseEventStream(user_id)


async def _session_dep(request: Request):
    """Resolve the founder from the Bearer JWT, bind their per-user store + stream
    for the whole request (so every deep read follows the right tenant), and reset
    on the way out. Demo/file-store (no Supabase backend) → no auth, the globals."""
    user = auth.optional_user(request) if auth.auth_enabled() else None
    if _require_signin() and user is None:
        raise HTTPException(status_code=401, detail="auth_required")
    if _supabase_backend() and user is not None:
        _ensure_account(user)
        store = project.store_for(user.user_id)
        stream = _stream_factory(user.user_id)
    elif user is not None and getattr(user, "is_owner", False):
        # Gated file-store demo, signed-in OWNER: an isolated per-user sandbox
        # store so the founder can run the real connect→ingest flywheel without
        # touching the seeded company the judges see. Events ride the global
        # stream (file mode has no per-user stream; the feed is cursor-seeded).
        store = project.store_for(user.user_id)
        stream = STREAM
    else:
        store = project.STORE
        stream = STREAM
    token = project.set_current_store(store)
    try:
        yield Session(user=user, store=store, stream=stream)
    finally:
        project.reset_current_store(token)


def _require_auth_if_live(user) -> None:
    """A chargeable / own-data route needs a signed-in founder when the Supabase
    backend is active. The public file-store demo needs none."""
    if _supabase_backend() and auth.auth_enabled() and user is None:
        raise HTTPException(status_code=401, detail="auth_required")


def _billing_active(user) -> bool:
    """Billing tracks the persisted backend + a real, non-owner founder (NOT the
    model-liveness mode) — so the file-store demo is free and owners are free."""
    return _supabase_backend() and user is not None and not getattr(user, "is_owner", False)


# ─── public-demo lock + per-IP rate limiting ──────────────────────────────────
# The public deploy is ONE shared file-store any visitor can reach. With
# SAAKSHE_PUBLIC_DEMO=1 the mutating connect/vault surface is sealed (a visitor
# could otherwise wipe the seeded company for everyone), and the model-burning
# routes get a small per-IP token bucket so an open demo can't be farmed.
def _public_demo() -> bool:
    return os.environ.get("SAAKSHE_PUBLIC_DEMO", "") == "1"


def _require_not_public_demo(user=None) -> None:
    """Seal mutations on the shared demo — except for a signed-in OWNER, who
    works in an isolated sandbox store (see _session_dep) and can't hurt it."""
    if _public_demo() and not getattr(user, "is_owner", False):
        raise HTTPException(
            status_code=403,
            detail="the public demo is sealed — its grounded company is shared and read-only; "
                   "run saakshe locally (or sign in on a billing deploy) to connect your own",
        )


_BUCKETS: dict[str, tuple[float, float]] = {}  # key → (tokens, last_refill_ts)


def _rate_limit(request, route: str, capacity: float, per_seconds: float) -> None:
    """A tiny in-process token bucket per (client-ip, route). Single-instance
    deploy (max-instances=1) makes in-process state authoritative."""
    import time as _time

    ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()
          or (request.client.host if request.client else "?"))
    key = f"{ip}:{route}"
    now = _time.monotonic()
    tokens, last = _BUCKETS.get(key, (capacity, now))
    tokens = min(capacity, tokens + (now - last) * (capacity / per_seconds))
    if tokens < 1.0:
        raise HTTPException(status_code=429, detail="slow down — the demo is shared")
    _BUCKETS[key] = (tokens - 1.0, now)


def _refund_run(run, user, reason: str) -> bool:
    """Refund a charged flywheel run once (idempotent on the spend key; releases the
    claim so a genuine retry re-charges). Returns whether a refund was issued."""
    if run is None or not getattr(run, "charged", False) or not run.spend_idem_key or user is None:
        return False
    try:
        credits.refund(user.user_id, credits.cost("flywheel_run"), reason,
                       run.spend_idem_key, run.spend_idem_key + ":refund")
    except Exception:  # noqa: BLE001
        pass
    run.charged = False
    return True


# ─── request bodies ──────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    text: str
    run_id: Optional[str] = None
    idem_key: Optional[str] = None


class RunRequest(BaseModel):
    question: Optional[str] = None
    idem_key: Optional[str] = None     # stable client key → idempotent spend + refund


class ApproveRequest(BaseModel):
    run_id: str
    gate_id: Optional[str] = None
    # The founder's explicit per-tap arm flag. It is one of THREE keys (with the
    # SAAKSHE_ALLOW_LIVE_SEND env and a registered channel client) that must all
    # turn before tap-2 fires a real publish; absent any one, the publish dry-runs.
    arm_real_send: bool = False


class ConnectRequest(BaseModel):
    kind: str
    ref: str
    mechanism: Optional[str] = None
    token: Optional[str] = None


class AnswerRequest(BaseModel):
    qid: str
    answer: str


class ManasEditRequest(BaseModel):
    instruction: str
    entity_type: str = "company_profile"
    target: Optional[dict] = None
    idem_key: Optional[str] = None


class VaultAddRequest(BaseModel):
    kind: str
    filename: str
    content_type: str = "image/png"
    data_b64: str
    tags: list[str] = []


_DECISION_HINTS = ("should we", "should i", "should the", "run the day", "start the day",
                   "raise pro", "raise our", "raise the price", "decide whether", "decide if")


# ─── public config + identity ─────────────────────────────────────────────────
@app.get("/api/public-config")
def public_config() -> dict[str, Any]:
    """What the cockpit needs to boot Supabase-JS (the anon key is public-safe)."""
    return {
        "supabase_url": os.environ.get("SAAKSHE_SUPABASE_URL", ""),
        "anon_key": os.environ.get("SUPABASE_ANON_KEY", ""),
        "store": os.environ.get("SAAKSHE_STORE", "file"),
        "auth_enabled": auth.auth_enabled() and (_supabase_backend() or _require_signin()),
        "require_signin": _require_signin(),
        "public_demo": _public_demo(),
        "mode": config.mode(),
    }


@app.get("/api/me")
def me(sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    """The founder's identity + live credit balance (the cockpit's balance pill).
    On the gated file-store demo a signed-in user still gets their identity —
    the cockpit needs is_owner to decide whether to show sandbox controls."""
    if sess.user is not None:
        if _supabase_backend():
            _ensure_account(sess.user)
        return {
            "user_id": sess.user.user_id, "email": sess.user.email,
            "is_owner": sess.user.is_owner,
            "balance": credits.balance(sess.user.user_id) if _supabase_backend() else None,
            "demo": not _supabase_backend(),
        }
    if not _supabase_backend():
        return {"demo": True, "balance": None, "auth_enabled": False}
    raise HTTPException(status_code=401, detail="auth_required")


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


# ─── setu · the connect bridge ────────────────────────────────────────────────
@app.get("/api/connect/status")
def connect_status(sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    _require_auth_if_live(sess.user)
    return sess.store.status_dict()


@app.post("/api/connect/source")
def connect_source(req: ConnectRequest, sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    _require_not_public_demo(sess.user)
    _require_auth_if_live(sess.user)
    kind = (req.kind or "").strip().lower()
    if kind not in ("github", "repo", "website", "web", "docs", "social"):
        raise HTTPException(status_code=400, detail=f"unknown source kind {kind!r}")
    kind = {"repo": "github", "web": "website"}.get(kind, kind)
    meta: dict[str, Any] = {}
    if kind == "github":
        # Default to a mechanism that can actually work in-container: https for
        # public repos, PAT when a token rides along. ssh only when asked for —
        # the container ships no deploy key, so an ssh default can never clone.
        meta["mechanism"] = (req.mechanism or ("pat" if req.token else "public")).lower()
        if req.token:
            meta["token"] = req.token
    conn = sess.store.add_connection(kind, req.ref.strip(), meta)
    return {"ok": True, "connection": conn.as_dict(), "status": sess.store.status_dict()}


@app.post("/api/connect/ingest")
async def connect_ingest(sess: Session = Depends(_session_dep)) -> Any:
    """Run the REAL manas ingestion over the connected sources (chargeable)."""
    _require_not_public_demo(sess.user)
    _require_auth_if_live(sess.user)
    store, stream, user = sess.store, sess.stream, sess.user
    if not store.is_connected():
        raise HTTPException(status_code=409, detail="nothing connected yet — add a source first")
    run_id = "ingest_" + os.urandom(4).hex()
    try:
        with credits.charge(user, "connect_ingest", idem_key="ingest:" + run_id, reason="connect ingest"):
            result = await manas_runner.ingest_connected(stream, run_id, store)
    except credits.OutOfCredits as exc:
        return JSONResponse(status_code=402, content=credits.out_of_credits_payload(exc.balance))
    except Exception as exc:  # noqa: BLE001 — charge() already refunded on the inner failure
        print("ingest failed @", run_id, "\n", traceback.format_exc())
        return JSONResponse(status_code=200, content={
            "status": "error", "text": credits.TEMPORARY_FAILURE_MSG, "detail": str(exc)[:300]})
    return {"run_id": run_id, **result}


@app.post("/api/connect/answer")
async def connect_answer(req: AnswerRequest, sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    _require_auth_if_live(sess.user)
    run_id = "answer_" + os.urandom(4).hex()
    result = await manas_runner.answer_question(sess.stream, run_id, req.qid, req.answer, sess.store)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error", "no such question"))
    return result


@app.post("/api/connect/reset")
def connect_reset(sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    _require_not_public_demo(sess.user)
    _require_auth_if_live(sess.user)
    sess.store.reset()
    return {"ok": True, "status": sess.store.status_dict()}


# ─── the brand-asset vault (manas owns the index; this is the founder's surface) ─
@app.get("/api/vault/list")
def vault_list(sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    """The vault's metadata index — empty in demo (the byte-identical guarantee)."""
    _require_auth_if_live(sess.user)
    return {"assets": project.current_store().assets_for()}


@app.post("/api/vault/add")
def vault_add(req: VaultAddRequest, sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    """The manual add path: stores bytes via the blob backend + records the index
    (through manas's vault face — kalai consumes, never owns the index)."""
    _require_not_public_demo(sess.user)
    _require_auth_if_live(sess.user)
    from manas import vault
    data = base64.b64decode(req.data_b64)
    rec = vault.add_asset(kind=req.kind, filename=req.filename, data=data,
                          content_type=req.content_type, tags=req.tags)
    return {"asset": rec}


_VAULT_URI_RE = re.compile(r"vault://[0-9a-f]{8,64}")


def _sniff_image_type(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


@app.get("/api/vault/asset")
def vault_asset(uri: str, sess: Session = Depends(_session_dep)) -> Response:
    """Serve a vault blob's bytes (read-only) — the gate-2 card's <img> source.
    Only content-addressed vault://<hex> URIs are servable: never a path, never a
    raw live-storage key."""
    _require_auth_if_live(sess.user)
    if not _VAULT_URI_RE.fullmatch(uri or ""):
        raise HTTPException(status_code=400, detail="expected a vault://<sha> uri")
    from common import vault as blob
    data = blob.get(uri)
    if data is None:
        raise HTTPException(status_code=404, detail="no such asset")
    return Response(content=data, media_type=_sniff_image_type(data))


# ─── the witness chat ─────────────────────────────────────────────────────────
@app.post("/api/saakshe/ask")
async def ask(req: AskRequest, request: Request, sess: Session = Depends(_session_dep)) -> Any:
    """Telemetry Q&A through the witness; a decision-shaped question starts the flywheel."""
    _rate_limit(request, "ask", capacity=12, per_seconds=60)
    _require_auth_if_live(sess.user)
    text = (req.text or "").strip()
    low = text.lower()
    mi = presenter.media_intent(text)
    if mi["is_media"]:
        q = media_crew.quote(seconds=4, budget_usd=mi["budget_usd"],
                             has_source_image=True, wants_hdr=mi["wants_hdr"])
        return {"kind": "media_quote", "quote": q,
                "blocks": presenter.quote_blocks(q)}
    if any(h in low for h in _DECISION_HINTS) and "?" in text:
        if not sess.store.is_grounded():
            return {"kind": "connect_first",
                    "text": "I can't run a decision on a blank memory — connect your project first "
                            "(a repo + your site), and I'll ground the company before deciding.",
                    "status": sess.store.status_dict()}
        return await _start_flywheel(sess, question=text, idem_key=req.idem_key,
                                     ok_text="That's a real decision — routing it to arivu. A gate will land in your queue.",
                                     wrap_key="flywheel")
    reply = await witness.respond(text, req.run_id, sess.stream)
    return {"kind": "witness", **reply, "blocks": presenter.to_blocks(reply)}


# ─── the flywheel (resumable 2-gate state machine) ───────────────────────────
async def _start_flywheel(sess: Session, *, question: Optional[str], idem_key: Optional[str],
                          ok_text: Optional[str] = None, wrap_key: str = "raw") -> Any:
    """Spend → start the flywheel → refund on internal failure or a terminal
    no-safe-decision. The spend is ONCE per run (keyed on a stable client key) and
    is refunded by /api/hero/approve too, since the run spans three requests."""
    store, stream, user = sess.store, sess.stream, sess.user
    billing = _billing_active(user)
    spend_key = idem_key or ("run:" + uuid4().hex)
    if billing:
        try:
            credits.spend(user.user_id, credits.cost("flywheel_run"), "flywheel run", spend_key)
        except credits.OutOfCredits as exc:
            return JSONResponse(status_code=402, content=credits.out_of_credits_payload(exc.balance))
    try:
        summary = await orchestrator.start(
            question=question, stream=stream, store=store,
            user_id=(user.user_id if user else ""), spend_idem_key=spend_key, charged=billing)
    except Exception as exc:  # noqa: BLE001 — internal failure: refund + reassure
        if billing:
            credits.refund(user.user_id, credits.cost("flywheel_run"), credits.TEMPORARY_FAILURE_MSG,
                           spend_key, spend_key + ":refund")
        print("flywheel start failed:\n", traceback.format_exc())
        return JSONResponse(status_code=200, content={
            "status": "error", "refunded": billing, "text": credits.TEMPORARY_FAILURE_MSG,
            "detail": str(exc)[:300]})
    if summary.get("status") == "no_safe_decision":
        # The run produced nothing shippable → make the founder whole.
        if _refund_run(orchestrator.get_run(summary["run_id"]), user, "no safe decision — not charged"):
            summary["refunded"] = True
    if wrap_key == "flywheel":
        return {"kind": "flywheel_started", "text": ok_text, "flywheel": summary}
    return summary


@app.post("/api/hero/run")
async def hero_run(req: RunRequest, request: Request, sess: Session = Depends(_session_dep)) -> Any:
    _rate_limit(request, "hero_run", capacity=4, per_seconds=60)
    _require_auth_if_live(sess.user)
    if not sess.store.is_grounded():
        return {"status": "not_connected", "connected": sess.store.is_connected(),
                "text": "Connect your project first — saakshe runs on YOUR company, never a canned example.",
                "connect": sess.store.status_dict()}
    return await _start_flywheel(sess, question=req.question, idem_key=req.idem_key)


@app.post("/api/hero/approve")
async def hero_approve(req: ApproveRequest, sess: Session = Depends(_session_dep)) -> Any:
    _require_auth_if_live(sess.user)
    run = orchestrator.get_run(req.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"unknown flywheel run_id {req.run_id!r}")
    # Run ownership: a tenant may only advance its OWN run (don't reveal existence).
    if _supabase_backend() and run.user_id and (sess.user is None or run.user_id != sess.user.user_id):
        raise HTTPException(status_code=404, detail=f"unknown flywheel run_id {req.run_id!r}")
    try:
        summary = await orchestrator.approve(req.run_id, req.gate_id,
                                             stream=sess.stream, store=run.store or sess.store,
                                             arm_real_send=req.arm_real_send)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))   # bad gate / not awaiting → no refund
    except Exception as exc:  # noqa: BLE001 — internal failure mid-flywheel: refund the run
        _refund_run(run, sess.user, credits.TEMPORARY_FAILURE_MSG)
        print("flywheel approve failed:\n", traceback.format_exc())
        return JSONResponse(status_code=200, content={
            "status": "error", "refunded": True, "text": credits.TEMPORARY_FAILURE_MSG,
            "detail": str(exc)[:300]})
    if summary.get("status") == "no_safe_decision":
        if _refund_run(run, sess.user, "no safe decision — not charged"):
            summary["refunded"] = True
    return summary


# ─── kalai media crew (router · pricer · renderer · verifier) ────────────────
# In-process job table — single-instance Cloud Run, same assumption as the
# rate limiter above. A job is the chargeable compute act; quote is free.
_media_jobs: dict[str, dict] = {}


class MediaQuoteRequest(BaseModel):
    seconds: int = 4
    budget_usd: float = 1.0
    has_source_image: bool = True


@app.post("/api/kalai/media/quote")
def media_quote(req: MediaQuoteRequest, sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    return media_crew.quote(seconds=req.seconds, budget_usd=req.budget_usd,
                            has_source_image=req.has_source_image, wants_hdr=True)


@app.post("/api/kalai/media/render")
async def media_render(request: Request,
                       image: UploadFile = File(...),
                       fx: str = Form("sat_sort"), seconds: int = Form(4),
                       budget_usd: float = Form(1.0),
                       width: int = Form(1080), height: int = Form(1920),
                       fps: int = Form(24),
                       sess: Session = Depends(_session_dep)) -> Any:
    _rate_limit(request, "media_render", capacity=4, per_seconds=300)
    _require_auth_if_live(sess.user)
    from kalai.media_fx import EFFECTS
    if fx not in EFFECTS:
        return JSONResponse(status_code=422, content={"error": f"unknown fx '{fx}'"})
    q = media_crew.quote(seconds=seconds, budget_usd=budget_usd,
                         has_source_image=True, wants_hdr=True)
    if not q["fits_budget"]:
        return JSONResponse(status_code=409, content={"error": "over budget", "quote": q})
    jid = uuid4().hex
    src = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    src.write(await image.read())
    src.close()
    out = src.name.replace(".png", "_hdr.mp4")
    _media_jobs[jid] = {"status": "rendering", "frame": 0,
                        "frames": q["seconds"] * fps, "quote": q}

    def _run() -> None:
        job = _media_jobs[jid]
        try:
            res = media_pipeline.render(
                src_path=src.name, fx=fx, seconds=q["seconds"], out_path=out,
                width=width, height=height, fps=fps,
                progress=lambda i, n: job.update(frame=i, frames=n))
            job.update(status="done", out_path=res["out_path"], verify=res["verify"],
                       receipt=media_crew.receipt(
                           q, measured_vcpu_sec=res["vcpu_sec_estimate"], vertex_usd=0.0))
        except Exception as exc:  # noqa: BLE001 — job surface reports, never raises
            job.update(status="error", error=str(exc)[:300])
        finally:
            os.unlink(src.name)

    threading.Thread(target=_run, daemon=True).start()
    return {"job_id": jid, "quote": q}


@app.get("/api/kalai/media/job/{jid}")
def media_job(jid: str, sess: Session = Depends(_session_dep)) -> Any:
    job = _media_jobs.get(jid)
    if not job:
        return JSONResponse(status_code=404, content={"error": "unknown job"})
    return job


@app.get("/api/kalai/media/file/{jid}")
def media_file(jid: str, sess: Session = Depends(_session_dep)) -> Any:
    job = _media_jobs.get(jid)
    if not job or job.get("status") != "done":
        return JSONResponse(status_code=404, content={"error": "not ready"})
    return FileResponse(job["out_path"], media_type="video/mp4",
                        filename="saakshe_hdr.mp4")


# ─── the one ordered stream + the derived gate queue ─────────────────────────
@app.get("/api/stream")
def stream(cursor: int = 0, run_id: Optional[str] = None,
           sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    _require_auth_if_live(sess.user)
    rows = sess.stream.rows(cursor)
    if run_id:
        rows = [r for r in rows if r["run_id"] == run_id]
    return {"cursor": sess.stream.cursor, "rows": rows}


@app.get("/api/gates")
def gates(run_id: Optional[str] = None, sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    _require_auth_if_live(sess.user)
    return {"gates": sess.stream.open_gates(run_id)}


# ─── witness telemetry tools ──────────────────────────────────────────────────
@app.get("/api/witness/telemetry")
def witness_telemetry(run_id: Optional[str] = None,
                      sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    _require_auth_if_live(sess.user)
    s = sess.stream
    return {
        "waiting": tel.anyone_waiting(run_id, s),
        "cost": tel.cost_today(run_id, s),
        "reversible": tel.whats_reversible(run_id, s),
        "learned": tel.what_learned(run_id, s),
        "acting": tel.whos_acting_now(run_id, s),
    }


# ─── manas live-edits → charged, immutable pending changes ───────────────────
def _pending_factory(user_id: str):
    """The per-user pending-changes store (overridable in tests)."""
    from common.pending import PendingChanges
    return PendingChanges(user_id)


def _generate_edit(entity_type: str, instruction: str, target: dict) -> tuple[dict, dict, list, str]:
    """Produce a STRUCTURED edit (a real deploy swaps in a Gemini-Flash call here;
    saakshe only persists the diff — executing it is wired elsewhere)."""
    target = dict(target or {})
    field = "tagline" if "tagline" in target else ("summary" if "summary" in target else "note")
    old_val = str(target.get(field, ""))
    new_val = (f"{old_val} — {instruction}".strip(" —")) if old_val else instruction
    new_json = {**target, field: new_val}
    return new_json, {field: [old_val, new_val]}, [field], ("gemini-flash" if config.is_live() else "scripted")


def _public_pending(row: dict) -> dict:
    return {k: row.get(k) for k in (
        "id", "entity_type", "diff_json", "changed_fields", "status", "review_status",
        "ai_model", "cost_credits", "created_at", "applied_at")}


@app.post("/api/manas/edit")
async def manas_edit(req: ManasEditRequest, sess: Session = Depends(_session_dep)) -> Any:
    """Charge + persist a manas-authored edit as an immutable pending change."""
    _require_auth_if_live(sess.user)
    target = req.target or {}
    new_json, diff_json, changed, model = _generate_edit(req.entity_type, req.instruction, target)
    if not _supabase_backend():
        # Demo preview — the edit is generated but neither charged nor persisted.
        return {"persisted": False, "entity_type": req.entity_type, "diff": diff_json,
                "changed_fields": changed, "new_json": new_json}
    user = sess.user
    billing = _billing_active(user)
    edit_key = req.idem_key or ("edit:" + uuid4().hex)
    cost = credits.cost("manas_edit")
    try:
        with credits.charge(user, "manas_edit", idem_key=edit_key, reason="manas edit"):
            row = _pending_factory(user.user_id).create(
                entity_type=req.entity_type, old_json=target, new_json=new_json,
                diff_json=diff_json, changed_fields=changed, idem_key=edit_key,
                ai_model=model, cost_credits=(cost if billing else 0))
    except credits.OutOfCredits as exc:
        return JSONResponse(status_code=402, content=credits.out_of_credits_payload(exc.balance))
    except Exception as exc:  # noqa: BLE001 — charge() already refunded on the inner failure
        print("manas edit failed:\n", traceback.format_exc())
        return JSONResponse(status_code=200, content={
            "status": "error", "text": credits.TEMPORARY_FAILURE_MSG, "detail": str(exc)[:300]})
    return {"persisted": True, "pending": _public_pending(row)}


@app.get("/api/manas/pending")
def manas_pending(sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    _require_auth_if_live(sess.user)
    if not _supabase_backend() or sess.user is None:
        return {"pending": []}
    return {"pending": [_public_pending(r) for r in _pending_factory(sess.user.user_id).list_open()]}


@app.post("/api/manas/pending/{pid}/apply")
def manas_apply(pid: str, sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    _require_auth_if_live(sess.user)
    if not _supabase_backend() or sess.user is None:
        raise HTTPException(status_code=401, detail="auth_required")
    pc = _pending_factory(sess.user.user_id)
    if pc.get(pid) is None:
        raise HTTPException(status_code=404, detail="no such pending change")
    applied = pc.apply(pid)
    return {"ok": True, "pending": _public_pending(applied or pc.get(pid) or {})}


@app.post("/api/manas/pending/{pid}/reject")
def manas_reject(pid: str, sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    _require_auth_if_live(sess.user)
    if not _supabase_backend() or sess.user is None:
        raise HTTPException(status_code=401, detail="auth_required")
    pc = _pending_factory(sess.user.user_id)
    row = pc.get(pid)
    if row is None:
        raise HTTPException(status_code=404, detail="no such pending change")
    pc.reject(pid)
    # Refund the edit charge (idempotent; releases the claim so a re-edit re-charges).
    refunded = False
    if _billing_active(sess.user) and row.get("idem_key") and row.get("cost_credits"):
        try:
            credits.refund(sess.user.user_id, int(row["cost_credits"]), "edit rejected",
                           row["idem_key"], row["idem_key"] + ":refund")
            refunded = True
        except Exception:  # noqa: BLE001
            pass
    return {"ok": True, "refunded": refunded}


# ─── A2A agent cards (open) ───────────────────────────────────────────────────
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
    if _require_signin():
        # Browsers can't set WS headers, so the gated demo passes ?token=<jwt>.
        try:
            auth.verify_token(websocket.query_params.get("token", ""))
        except auth.AuthError:
            await websocket.close(code=4401)
            return
    await witness_voice.handle_ws(websocket)


# ─── serve the site ───────────────────────────────────────────────────────────
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
    branded = _WEB / "404.html"
    if branded.exists():  # a typo'd URL lands on a saakshe page, not bare JSON
        return FileResponse(branded, status_code=404)
    raise HTTPException(status_code=404, detail=f"no page {name!r}")


@app.get("/auth/callback", response_class=HTMLResponse)
def auth_callback() -> Any:
    """Completes the Supabase OAuth round-trip (supabase-js parses the URL, then we
    bounce to the cockpit). Explicit route since the catch-all is single-segment."""
    return _serve_page("auth-callback.html")


@app.get("/", response_class=HTMLResponse)
def home() -> Any:
    return _serve_page(_HOME)


@app.get("/{page}", response_class=HTMLResponse)
def web_page(page: str) -> Any:
    return _serve_page(page)

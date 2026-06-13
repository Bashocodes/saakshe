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
import hmac
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
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse,
                               RedirectResponse, Response)
from pydantic import BaseModel
from starlette.websockets import WebSocketDisconnect

import common  # noqa: F401 — bootstraps arivu onto sys.path
from common import a2a, auth, config, credits, models, project
from common import agents as staff
from common.stream import STREAM
from common.supastream import SupabaseEventStream
import orchestrator
import manas.runner as manas_runner
import manas.sources as manas_sources
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

        if config.faculty_v2():
            # faculty-v2: the channel KEY lives in manas (the keeper). kural holds
            # only a tokenless capability handle that dispatches to the broker;
            # set_channel_client stays HERE on kural so has_channel_client() and the
            # orchestrator arm-gate are unchanged. The token never reaches kural.
            from manas import connectors as _connectors   # registers the broker skills
            from common import a2a as _a2a

            if _connectors.channel_configured():
                _channels.set_channel_client(
                    lambda action, args: _a2a.dispatch("manas", "publish_action", action, args)
                )
                print("kural: live channel armed → manas connector (v2 key custody)")
        else:
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
_DEFAULT_ORIGINS = (
    "https://saakshe.com,https://www.saakshe.com,"
    "http://localhost:8000,http://localhost:8765"
)
_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("SAAKSHE_ALLOWED_ORIGINS", _DEFAULT_ORIGINS).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware, allow_origins=_ALLOWED_ORIGINS, allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    """Baseline hardening headers on every response (no CSP yet — the site is
    single-file inline-everything HTML, a CSP would need nonces page-by-page)."""
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.exception_handler(Exception)
async def _json_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Never return a plain-text 500. A live model call can raise mid-flywheel;
    the cockpit calls r.json(), so an unhandled exception MUST still be valid JSON.
    The traceback stays server-side — clients get a generic detail, never str(exc)
    (exception text can leak paths, keys and SQL)."""
    print("saakshe error @", request.url.path, "\n", traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"error": type(exc).__name__, "detail": "internal error", "where": request.url.path},
    )


# ─── the per-request session (auth + per-user store/stream binding) ───────────
@dataclass
class Session:
    user: Any            # auth.User | None
    store: Any           # the founder's ProjectStore / SupabaseStore (or the global)
    stream: Any          # the founder's event stream (or the global)


def _supabase_backend() -> bool:
    return os.environ.get("SAAKSHE_STORE", "").lower() == "supabase"


def _is_judge(user) -> bool:
    """A judging account (JUDGE_EMAILS, default the Devpost credential) rides the
    SHARED seeded store read-only — it must always land on the pristine grounded
    demo company, never an empty sandbox, and never a credit balance."""
    if user is None:
        return False
    emails = os.environ.get("JUDGE_EMAILS", "judge@saakshe.com")
    judge_set = {e.strip().lower() for e in emails.split(",") if e.strip()}
    return (getattr(user, "email", "") or "").lower() in judge_set


def _judge_token() -> str:
    """The judge magic-link secret. Empty (or too short to be a real secret) =
    the feature is OFF — the link route 404s and the cookie is inert."""
    t = os.environ.get("SAAKSHE_JUDGE_TOKEN", "").strip()
    return t if len(t) >= 16 else ""


def _judge_link_ok(request) -> bool:
    """A valid judge-link cookie on this request (constant-time compare)."""
    expected = _judge_token()
    presented = request.cookies.get("sk_judge", "")
    return bool(expected and presented and hmac.compare_digest(presented, expected))


def _judge_link_user():
    """The synthesized judge identity a valid link cookie signs in as — the SAME
    judge the email credential maps to, so every existing seal applies: shared
    seeded store, mutations sealed, no billing."""
    emails = os.environ.get("JUDGE_EMAILS", "judge@saakshe.com")
    email = next((e.strip() for e in emails.split(",") if e.strip()), "judge@saakshe.com")
    return auth.User(user_id="judge-link", email=email, is_owner=False)


def _require_signin() -> bool:
    """The gated-demo switch: SAAKSHE_REQUIRE_SIGNIN=1 puts the WHOLE API surface
    behind sign-in — judge credentials go in the Devpost testing instructions —
    while the store stays the seeded, sealed file-store demo. The sign-in surfaces
    themselves (HTML pages, /api/public-config, the health probe) stay open.

    Fails CLOSED: if the flag is set while Supabase auth is misconfigured
    (SAAKSHE_SUPABASE_URL dropped), every session-bound route 401s and the
    cockpit shows its misconfig gate — never a gated deploy silently wide open."""
    return os.environ.get("SAAKSHE_REQUIRE_SIGNIN", "") == "1"


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
    if user is None and _judge_link_ok(request):
        user = _judge_link_user()
    if _require_signin() and user is None:
        raise HTTPException(status_code=401, detail="auth_required")
    if _supabase_backend() and user is not None:
        _ensure_account(user)
        store = project.store_for(user.user_id)
        stream = _stream_factory(user.user_id)
    elif user is not None and not _is_judge(user):
        # Gated file-store demo, ANY signed-in founder (owner or not): an
        # isolated per-user sandbox store + the first-touch credit grant, so
        # everyone who signs in can run the real connect→ingest flywheel
        # without touching the seeded company the judges see. Events ride the
        # global stream (file mode has no per-user stream; the feed is
        # cursor-seeded). Judges fall through to the shared seeded store.
        _ensure_account(user)
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


def _redact_secrets(obj: Any) -> Any:
    """Connection meta may carry a GitHub PAT — credentials ride IN over setu
    but must never ride back OUT in any response body."""
    if isinstance(obj, dict):
        return {k: ("•••" if k == "token" and isinstance(v, str) and v else _redact_secrets(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact_secrets(x) for x in obj]
    return obj


def _require_auth_if_live(user) -> None:
    """A chargeable / own-data route needs a signed-in founder when the Supabase
    backend is active. The public file-store demo needs none."""
    if _supabase_backend() and auth.auth_enabled() and user is None:
        raise HTTPException(status_code=401, detail="auth_required")


def _billing_active(user) -> bool:
    """Billing tracks a billing-armed deploy + a real, non-owner, non-judge
    founder (NOT the model-liveness mode) — the anonymous demo is free, owners
    are free, and the judging account is free (it is sealed read-only anyway)."""
    return (credits.billing_enabled() and user is not None
            and not getattr(user, "is_owner", False) and not _is_judge(user))


def _live_send_armed() -> bool:
    """The deploy-level half of the publish triple AND-gate: the env opt-in plus
    a registered channel client. Without both, an armed tap dry-runs — and a
    dry-run must never bill the kural_engage credit."""
    from kural.tools import channels
    return (os.environ.get("SAAKSHE_ALLOW_LIVE_SEND", "") == "1"
            and channels.has_channel_client())


# ─── public-demo lock + per-IP rate limiting ──────────────────────────────────
# The public deploy is ONE shared file-store any visitor can reach. With
# SAAKSHE_PUBLIC_DEMO=1 the mutating connect/vault surface is sealed (a visitor
# could otherwise wipe the seeded company for everyone), and the model-burning
# routes get a small per-IP token bucket so an open demo can't be farmed.
def _public_demo() -> bool:
    return os.environ.get("SAAKSHE_PUBLIC_DEMO", "") == "1"


def _require_not_public_demo(user=None) -> None:
    """Seal mutations on the shared demo for ANONYMOUS visitors and the judging
    account only — every other signed-in founder works in an isolated sandbox
    store (see _session_dep) and can't hurt the seeded company."""
    if _public_demo() and (user is None or _is_judge(user)):
        raise HTTPException(
            status_code=403,
            detail="the shared demo company is sealed read-only — sign in to connect "
                   "your own (500 free credits), or run saakshe locally",
        )


_BUCKETS: dict[str, tuple[float, float]] = {}  # key → (tokens, last_refill_ts)


def _rate_limit(request, route: str, capacity: float, per_seconds: float) -> None:
    """A tiny in-process token bucket per (client-ip, route). Single-instance
    deploy (max-instances=1) makes in-process state authoritative."""
    import time as _time

    import ipaddress

    # Trust x-forwarded-for only when it parses as a real IP — a forged header
    # ("Bob", a fresh string per request) must not mint unlimited buckets or
    # impersonate another client's bucket. Cloud Run sets the header itself;
    # this guards the local/direct case.
    fwd = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    try:
        ip = str(ipaddress.ip_address(fwd))
    except ValueError:
        ip = request.client.host if request.client else "?"
    key = f"{ip}:{route}"
    now = _time.monotonic()
    tokens, last = _BUCKETS.get(key, (capacity, now))
    tokens = min(capacity, tokens + (now - last) * (capacity / per_seconds))
    if tokens < 1.0:
        raise HTTPException(status_code=429, detail="slow down — the demo is shared")
    _BUCKETS[key] = (tokens - 1.0, now)


def _refund_run(run, user, reason: str) -> bool:
    """Refund a charged flywheel run once (idempotent on the spend key; releases the
    claim so a genuine retry re-charges). Returns whether a refund was REALLY issued
    — a failed refund RPC must never be reported to the founder as "refunded"."""
    if run is None or not getattr(run, "charged", False) or not run.spend_idem_key or user is None:
        return False
    try:
        credits.refund(user.user_id, credits.cost("flywheel_run"), reason,
                       run.spend_idem_key, run.spend_idem_key + ":refund")
    except Exception:  # noqa: BLE001
        # Keep run.charged so a later path can re-attempt; the refund key is
        # idempotent, so a replay is always safe.
        print("REFUND FAILED — replay refund for spend key", run.spend_idem_key,
              "\n", traceback.format_exc())
        return False
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
    # "own" (default) | "public" — whether the founder owns the product or is
    # exploring someone else's public one; lands on org.relationship.
    relationship: Optional[str] = None


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
                   "raise pro", "raise our", "raise the price", "decide whether", "decide if",
                   "decide and", "and decide", "then decide", "decide this", "decide for me",
                   "is this a good", "is it a good", "good idea", "worth building",
                   "worth doing", "give me a verdict", "your verdict", "seal a verdict")


# ─── public config + identity ─────────────────────────────────────────────────
@app.get("/api/public-config")
def public_config(request: Request) -> dict[str, Any]:
    """What the cockpit needs to boot Supabase-JS (the anon key is public-safe).

    A valid judge-link cookie flips require_signin/auth_enabled OFF in this
    response only — the cockpit then boots exactly like the open demo (no
    sign-in gate) while every API call resolves to the sealed judge session."""
    judge = _judge_link_ok(request)
    return {
        "supabase_url": os.environ.get("SAAKSHE_SUPABASE_URL", ""),
        "anon_key": os.environ.get("SUPABASE_ANON_KEY", ""),
        "store": os.environ.get("SAAKSHE_STORE", "file"),
        "auth_enabled": (not judge) and auth.auth_enabled() and (_supabase_backend() or _require_signin()),
        "require_signin": (not judge) and _require_signin(),
        "judge_link": judge,
        "public_demo": _public_demo(),
        "mode": config.mode(),
        # Deploy provenance: K_REVISION is set by Cloud Run itself; the sha/time
        # are stamped by deploy_cloudrun.sh. Locally: revision "local".
        "revision": os.environ.get("K_REVISION", "local"),
        "git_sha": os.environ.get("SAAKSHE_GIT_SHA", ""),
        "deployed_at": os.environ.get("SAAKSHE_DEPLOYED_AT", ""),
    }


@app.get("/api/me")
def me(sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    """The founder's identity + live credit balance (the cockpit's balance pill).
    On the gated file-store demo a signed-in user still gets their identity —
    the cockpit shows sandbox controls (start over) to anyone whose store is
    their own, and the balance pill whenever billing is armed."""
    if sess.user is not None:
        sandbox = not _is_judge(sess.user)   # everyone but the judging account
        if _supabase_backend() or (sandbox and credits.billing_enabled()):
            _ensure_account(sess.user)
        return {
            "user_id": sess.user.user_id, "email": sess.user.email,
            "is_owner": sess.user.is_owner, "sandbox": sandbox,
            "balance": (credits.balance(sess.user.user_id)
                        if (_supabase_backend() or credits.billing_enabled()) and sandbox
                        else None),
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


@app.get("/api/saakshe/agents")
def agents_registry() -> dict[str, Any]:
    """The staff register — 42 agents · 4 realms (+ the witness above them).
    Free, unauthenticated, deterministic: pure data the cockpit renders."""
    return staff.as_payload()


# ─── setu · the connect bridge ────────────────────────────────────────────────
@app.get("/api/connect/status")
def connect_status(sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    _require_auth_if_live(sess.user)
    return _redact_secrets(sess.store.status_dict())


class ProfileEditRequest(BaseModel):
    label: str = ""
    edit_id: str = ""
    current_text: str = ""
    provenance: str = ""
    instruction: str


_PROFILE_EDIT_SYSTEM = (
    "You are manas, editing ONE element of a company-profile page. You are given the "
    "element's role/label, its current text, and (optionally) its cited source. Apply the "
    "user's instruction and return ONLY the new text for that element — no preamble, no "
    "surrounding quotes, no markdown, no explanation. Preserve the element's voice (plain, "
    "creator-first, never hype). Keep roughly the same length unless asked to shorten or expand. "
    "If the instruction is a simple 'change X to Y', change only that. Never invent facts that "
    "are not supported by the current text or the cited source."
)


def _profile_edit_sanitize(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"^```[A-Za-z0-9]*\s*", "", t)
    t = re.sub(r"\s*```$", "", t).strip()
    if len(t) >= 2 and t[0] in "\"'“‘" and t[-1] in "\"'”’":
        t = t[1:-1].strip()
    return re.sub(r"\s+", " ", t).strip()


def _profile_edit_llm(prompt: str) -> str:
    """The Vertex Gemini-Flash call behind /api/profile/edit — a module-level
    seam so tests fake the model without faking Vertex."""
    from google import genai
    from google.genai import types as gtypes

    client = genai.Client(vertexai=True, project=config.GOOGLE_CLOUD_PROJECT or None,
                          location=config.GEMINI_LOCATION)
    cfg = dict(system_instruction=_PROFILE_EDIT_SYSTEM, temperature=0.4,
               max_output_tokens=1200)
    try:  # flash is a THINKING model — keep thoughts from eating the output budget
        cfg["thinking_config"] = gtypes.ThinkingConfig(thinking_level="low")
        gen = gtypes.GenerateContentConfig(**cfg)
    except Exception:  # noqa: BLE001 — older SDK: drop the knob, not the call
        cfg.pop("thinking_config", None)
        gen = gtypes.GenerateContentConfig(**cfg)
    out = client.models.generate_content(model=config.MODEL_FLASH, contents=prompt, config=gen)
    return out.text or ""


@app.options("/api/profile/edit")
async def profile_edit_probe() -> Response:
    """grasped.html liveness-probes this route with OPTIONS on load; answer 204
    instead of Starlette's auto-405 so the browser console stays clean."""
    return Response(status_code=204)


@app.post("/api/profile/edit")
async def profile_edit(req: ProfileEditRequest, request: Request,
                       sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    """The grasped page's point-and-edit chat (web/grasped.html): rewrite ONE
    element's text with Gemini Flash, grounded in its cited source — a 1-credit
    move on the price card. Demo mode 503s so the page falls back to its own
    deterministic local engine."""
    _require_auth_if_live(sess.user)
    _rate_limit(request, "profile_edit", capacity=10, per_seconds=60)
    if not config.is_live():
        raise HTTPException(status_code=503, detail="live edit runs in live mode — the page's local engine covers demo")
    import asyncio as _asyncio

    prompt = (
        f"ELEMENT ROLE: {req.label or 'Element'}\n"
        f"CITED SOURCE: {req.provenance or '(none)'}\n"
        f"CURRENT TEXT:\n{req.current_text}\n\n"
        f"INSTRUCTION: {req.instruction}\n\n"
        f"Return ONLY the new text for this element."
    )

    payer = sess.user if _billing_active(sess.user) else None
    pe_key = "pedit:" + uuid4().hex
    try:
        with credits.charge(payer, "profile_edit", idem_key=pe_key, reason="profile edit"):
            text = _profile_edit_sanitize(await _asyncio.to_thread(_profile_edit_llm, prompt))
            if not text:
                raise RuntimeError("empty reply")
    except credits.OutOfCredits as exc:
        return JSONResponse(status_code=402, content=credits.out_of_credits_payload(exc.balance))
    except Exception as exc:  # noqa: BLE001 — charge() already refunded; the page
        # falls back to its local engine
        raise HTTPException(status_code=502, detail=f"edit model unavailable: {str(exc)[:200]}")
    return {"text": text, "message": "Applied your change (live manas).",
            "engine": config.MODEL_FLASH}


@app.get("/api/connect/grasped")
def connect_grasped(sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    """What manas GRASPED from the connected sources — the extraction readout
    (org · cited facts · voice/brand rules · open questions). Re-openable any
    time from the cockpit's CONNECT pill; status_dict alone carries only counts."""
    _require_auth_if_live(sess.user)
    pack = sess.store.pack()
    st = sess.store.status_dict()
    return _redact_secrets({
        "connected": st["connected"], "grounded": st["grounded"],
        "version": st["version"], "org": st["org"],
        "facts": pack.facts, "voice_rules": pack.voice_rules,
        "brand_rules": pack.brand_rules, "questions": st["questions"],
        # kind+ref only (never meta — that's where a PAT rides): the grasped page
        # names what manas actually read in its masthead prompt line + footer.
        "connections": [{"kind": c.kind, "ref": c.ref} for c in sess.store.connections],
    })


@app.post("/api/connect/source")
def connect_source(req: ConnectRequest, sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    _require_not_public_demo(sess.user)
    _require_auth_if_live(sess.user)
    kind = (req.kind or "").strip().lower()
    if kind not in ("github", "repo", "website", "web", "docs", "social"):
        raise HTTPException(status_code=400, detail=f"unknown source kind {kind!r}")
    kind = {"repo": "github", "web": "website"}.get(kind, kind)
    rel = (req.relationship or "").strip().lower()
    if rel and rel not in ("own", "public"):
        raise HTTPException(status_code=400,
                            detail=f"unknown relationship {rel!r} — 'own' or 'public'")
    meta: dict[str, Any] = {}
    if kind == "github":
        # Default to a mechanism that can actually work in-container: https for
        # public repos, PAT when a token rides along. ssh only when asked for —
        # the container ships no deploy key, so an ssh default can never clone.
        meta["mechanism"] = (req.mechanism or ("pat" if req.token else "public")).lower()
        if req.token:
            meta["token"] = req.token
    conn = sess.store.add_connection(kind, req.ref.strip(), meta)
    if rel:
        sess.store.set_org(relationship=rel)
    return _redact_secrets({"ok": True, "connection": conn.as_dict(), "status": sess.store.status_dict()})


class ProbeRequest(BaseModel):
    ref: str


_PROBE_HINTS = {
    "public": "public — manas reads it anonymously, zero setup",
    "private": "private (or not found) — paste a fine-grained token "
               "(read-only Contents), or run saakshe locally over your git SSH",
    "ssh": "an ssh ref — works where your key lives (a local run); "
           "in the cloud paste a token instead",
    "unknown": "can't read that ref — use owner/repo or a full https URL",
}


@app.post("/api/connect/probe")
def connect_probe(req: ProbeRequest, sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    """The gate's pre-grant visibility check: tell the founder NOW whether a repo
    reads anonymously (public/open-source), needs a token (private), or needs a
    local SSH run — instead of failing later inside a chargeable imbibe. Sealed
    like its mutating siblings so the shared demo never becomes a probe proxy."""
    _require_not_public_demo(sess.user)
    _require_auth_if_live(sess.user)
    verdict = manas_sources.probe_repo_visibility(req.ref)
    visibility = verdict.get("visibility", "unknown")
    return {"ok": True, "visibility": visibility, "hint": _PROBE_HINTS[visibility]}


class IngestRequest(BaseModel):
    # Stable client key → a replayed/retried POST can never double-charge.
    idem_key: Optional[str] = None


@app.post("/api/connect/ingest")
async def connect_ingest(req: Optional[IngestRequest] = None, sess: Session = Depends(_session_dep)) -> Any:
    """Run the REAL manas ingestion over the connected sources (chargeable)."""
    _require_not_public_demo(sess.user)
    _require_auth_if_live(sess.user)
    store, stream, user = sess.store, sess.stream, sess.user
    # No connections is no longer a 409 dead end — manas starts the INTERVIEW
    # (empty start): clarifying questions open, and every answer folds back as a
    # cited founder-word fact. A founder without a public repo/site can begin.
    run_id = "ingest_" + os.urandom(4).hex()
    spend_key = "ingest:" + ((req.idem_key or run_id)[:120] if req and req.idem_key else run_id)
    # Grasping a CONNECTED repo is the big-ticket action; an empty start (zero
    # connections) only opens the interview — that's "a move", priced 1, not 100.
    cost_key = "connect_ingest" if store.is_connected() else "interview_open"
    payer = user if _billing_active(user) else None
    try:
        with credits.charge(payer, cost_key, idem_key=spend_key,
                            reason=("connect ingest" if cost_key == "connect_ingest"
                                    else "interview open")):
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
    _require_not_public_demo(sess.user)   # commits to memory — sealed like its siblings
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
    return _redact_secrets({"ok": True, "status": sess.store.status_dict()})


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
def _remember_turn(sess: Session, role: str, text: str, meta: Optional[dict] = None) -> None:
    """Fail-soft transcript write — a closed tab must not amnesia the chat, but
    the transcript must never break the ask it records. Judges ride the SHARED
    seeded store: their turns are never written into it."""
    if not text or _is_judge(sess.user):
        return
    try:
        sess.store.append_message(role, text, meta=meta or {})
    except Exception:  # noqa: BLE001
        pass


@app.get("/api/saakshe/messages")
def chat_history(request: Request, limit: int = 60,
                 sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    """The persisted witness-chat transcript, oldest first — the feed restores
    from here when the tab's sessionStorage is gone (closed window, new device)."""
    _rate_limit(request, "chat_history", capacity=20, per_seconds=60)
    _require_auth_if_live(sess.user)
    if _is_judge(sess.user):
        return {"messages": []}    # the shared store holds no judge transcript
    try:
        return {"messages": sess.store.get_messages(limit=max(1, min(200, limit)))}
    except Exception:  # noqa: BLE001
        return {"messages": []}


@app.post("/api/saakshe/ask")
async def ask(req: AskRequest, request: Request, sess: Session = Depends(_session_dep)) -> Any:
    """Telemetry Q&A through the witness; a decision-shaped question starts the flywheel."""
    _rate_limit(request, "ask", capacity=12, per_seconds=60)
    _require_auth_if_live(sess.user)
    text = (req.text or "").strip()
    low = text.lower()
    _remember_turn(sess, "you", text)
    mi = presenter.media_intent(text)
    if mi["is_media"]:
        q = media_crew.quote(seconds=4, budget_usd=mi["budget_usd"],
                             has_source_image=True, wants_hdr=mi["wants_hdr"])
        qb = presenter.quote_blocks(q)
        _remember_turn(sess, "kalai/router", f"Path {q['path']} — {q['rationale']}.",
                       {"kind": "media_quote", "blocks": qb})
        return {"kind": "media_quote", "quote": q, "blocks": qb}
    # A decision ask routes to arivu on the hint phrase alone — founders (and
    # voice transcripts) say "decide and tell me" without a question mark, and
    # requiring "?" used to drop those into a witness refusal.
    if any(h in low for h in _DECISION_HINTS) or low.rstrip(" .!").endswith("decide"):
        if not sess.store.is_grounded():
            _remember_turn(sess, "saakshe/witness",
                           "I can't run a decision on a blank memory — connect your project first "
                           "(a repo + your site), and I'll ground the company before deciding.")
            return {"kind": "connect_first",
                    "text": "I can't run a decision on a blank memory — connect your project first "
                            "(a repo + your site), and I'll ground the company before deciding.",
                    "status": _redact_secrets(sess.store.status_dict()),
                    "blocks": [
                        {"t": "text", "who": "saakshe/witness",
                         "md": "I can't run a decision on a blank memory — connect your project "
                               "first (a repo + your site), and I'll ground the company before deciding."},
                        {"t": "actions", "items": [
                            {"label": "CONNECT PROJECT", "kind": "primary",
                             "action": "nav.connections", "args": {}}]},
                        {"t": "options", "items": [
                            {"label": "what can you see right now?",
                             "send": "what can you see right now?"}]},
                    ]}
        _remember_turn(sess, "saakshe/witness",
                       "That's a real decision — routing it to arivu. A gate will land in your queue.")
        return await _start_flywheel(sess, question=text, idem_key=req.idem_key,
                                     ok_text="That's a real decision — routing it to arivu. A gate will land in your queue.",
                                     wrap_key="flywheel")
    # A witness chat turn is a chargeable action (1 credit) — the decision path
    # above carries its own flywheel spend, and a media quote is just a price.
    payer = sess.user if _billing_active(sess.user) else None  # judges/owners chat free
    ask_key = "ask:" + (req.idem_key or uuid4().hex)
    try:
        with credits.charge(payer, "saakshe_ask", idem_key=ask_key, reason="witness chat turn"):
            reply = await witness.respond(text, req.run_id, sess.stream)
    except credits.OutOfCredits as exc:
        return JSONResponse(status_code=402, content=credits.out_of_credits_payload(exc.balance))
    blocks = presenter.to_blocks(reply, asked=text)
    _remember_turn(sess, "saakshe/witness", reply.get("text", ""),
                   {"kind": "witness", "blocks": blocks})
    return {"kind": "witness", **reply, "blocks": blocks}


# ─── the flywheel (resumable 2-gate state machine) ───────────────────────────
async def _start_flywheel(sess: Session, *, question: Optional[str], idem_key: Optional[str],
                          ok_text: Optional[str] = None, wrap_key: str = "raw") -> Any:
    """Spend → start the flywheel → refund on internal failure or a terminal
    no-safe-decision. The spend is ONCE per run (keyed on a stable client key) and
    is refunded by /api/hero/approve too, since the run spans three requests."""
    store, stream, user = sess.store, sess.stream, sess.user
    billing = _billing_active(user)
    # The SERVER owns the spend-key namespace ("run:") — a client-chosen key must
    # never be able to squat on another action's claim (e.g. "ingest:<k>", which
    # would make the later 100-credit grasp replay as already-spent).
    spend_key = "run:" + (idem_key or uuid4().hex)
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
        # arivu speaks for its own chamber in the chat — the witness only carries
        # telemetry; the realm that decides is the one that communicates the run.
        if summary.get("status") == "no_safe_decision":
            md = ("The five lenses argued it and no verdict survived the bench — "
                  "dissent is on the record, and you were not charged.")
        else:
            md = (ok_text or "Convening the five lenses on this now — a sealed "
                             "verdict will land in your queue for your tap.")
        return {"kind": "flywheel_started", "text": ok_text, "flywheel": summary,
                "blocks": [
                    {"t": "text", "who": "arivu/chair", "md": md},
                    {"t": "options", "items": [
                        {"label": "what is waiting on me?", "send": "what's waiting on me?"},
                        {"label": "who is acting right now?", "send": "who is acting right now?"}]},
                ]}
    return summary


@app.post("/api/hero/run")
async def hero_run(req: RunRequest, request: Request, sess: Session = Depends(_session_dep)) -> Any:
    _rate_limit(request, "hero_run", capacity=4, per_seconds=60)
    _require_auth_if_live(sess.user)
    if not sess.store.is_grounded():
        return {"status": "not_connected", "connected": sess.store.is_connected(),
                "text": "Connect your project first — saakshe runs on YOUR company, never a canned example.",
                "connect": _redact_secrets(sess.store.status_dict())}
    return await _start_flywheel(sess, question=req.question, idem_key=req.idem_key)


@app.post("/api/hero/approve")
async def hero_approve(req: ApproveRequest, sess: Session = Depends(_session_dep)) -> Any:
    _require_auth_if_live(sess.user)
    run = orchestrator.get_run(req.run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"unknown flywheel run_id {req.run_id!r}")
    # Run ownership: a tenant may only advance its OWN run (don't reveal existence).
    # Holds on EVERY auth-enabled profile — gated file-store judges included.
    # Ownerless runs (user_id == "") are tappable ONLY by anonymous sessions in an
    # open-demo profile — a signed-in user must own the run, so an empty owner can
    # never bypass the check (legacy/orphan runs are not a free tap).
    if auth.auth_enabled() and (sess.user is not None or run.user_id):
        if sess.user is None or not run.user_id or run.user_id != sess.user.user_id:
            raise HTTPException(status_code=404, detail=f"unknown flywheel run_id {req.run_id!r}")
    # An ARMED tap on a deploy that can really send is the kural engagement —
    # the one extra credit on the price card. Unarmed taps and dry-run deploys
    # ride the run's own spend. charge() refunds on any raise below; a
    # no-safe-decision refund follows the run's, and the key is stable per
    # (run, gate) so a retried tap never double-bills.
    engage_payer = (sess.user if (req.arm_real_send and _live_send_armed()
                                  and _billing_active(sess.user)) else None)
    engage_key = f"engage:{req.run_id}:{req.gate_id or 'tap'}"
    try:
        with credits.charge(engage_payer, "kural_engage", idem_key=engage_key,
                            reason="kural engage (armed publish)"):
            summary = await orchestrator.approve(req.run_id, req.gate_id,
                                                 stream=sess.stream, store=run.store or sess.store,
                                                 arm_real_send=req.arm_real_send)
    except credits.OutOfCredits as exc:
        return JSONResponse(status_code=402, content=credits.out_of_credits_payload(exc.balance))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc))   # bad gate / not awaiting → no refund
    except Exception as exc:  # noqa: BLE001 — internal failure mid-flywheel: refund the run
        refunded = _refund_run(run, sess.user, credits.TEMPORARY_FAILURE_MSG)
        print("flywheel approve failed:\n", traceback.format_exc())
        return JSONResponse(status_code=200, content={
            "status": "error", "refunded": refunded,
            "text": credits.TEMPORARY_FAILURE_MSG if refunded or not getattr(run, "charged", False)
                    else "Something failed on our side — the charge is being reversed; "
                         "if it doesn't appear shortly, it will be replayed.",
            "detail": str(exc)[:300]})
    if summary.get("status") == "no_safe_decision":
        if _refund_run(run, sess.user, "no safe decision — not charged"):
            summary["refunded"] = True
        if engage_payer is not None:    # nothing shipped → the engage credit too
            try:
                credits.refund(engage_payer.user_id, credits.cost("kural_engage"),
                               "no safe decision — not charged",
                               engage_key, engage_key + ":refund")
            except Exception:  # noqa: BLE001 — idempotent key; ops can replay
                print(f"REFUND FAILED — replay refund for spend key {engage_key!r}")
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


def _auto_canvas(src_path: str) -> tuple[int, int]:
    """Output canvas matched to the SOURCE's orientation — a landscape plate
    must not come back as a 9:16 centre-crop (founder, 2026-06-12). Same pixel
    budget as the old fixed 1080x1920 (so the quote's render-time model holds),
    long edge capped at 1920, even dims for the 10-bit HEVC encoder."""
    try:
        from PIL import Image
        with Image.open(src_path) as im:
            iw, ih = im.size
    except Exception:  # noqa: BLE001 — unreadable image → the old portrait default
        return 1080, 1920
    if not iw or not ih:
        return 1080, 1920
    budget = 1080 * 1920
    ar = iw / ih
    w = min(1920.0, (budget * ar) ** 0.5)
    h = min(1920.0, w / ar)
    return max(2, int(w // 2) * 2), max(2, int(h // 2) * 2)


@app.post("/api/kalai/media/render")
async def media_render(request: Request,
                       image: UploadFile = File(...),
                       fx: str = Form("sat_sort"), seconds: int = Form(4),
                       budget_usd: float = Form(1.0),
                       width: int = Form(0), height: int = Form(0),
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
    # The RENDER is the chargeable compute act (the quote stays free) — spend
    # before the job starts, refund from the worker if the render dies.
    payer = sess.user if _billing_active(sess.user) else None
    render_cost = credits.cost("kalai_make")
    render_key = "kalai:" + uuid4().hex
    if payer is not None and render_cost > 0:   # COST_KALAI_MAKE=0 → free render
        try:
            credits.spend(payer.user_id, render_cost, "kalai media render", render_key)
        except credits.OutOfCredits as exc:
            return JSONResponse(status_code=402, content=credits.out_of_credits_payload(exc.balance))
    else:
        payer = None   # nothing spent → the worker must not try to refund
    jid = uuid4().hex
    src = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    src.write(await image.read())
    src.close()
    if width <= 0 or height <= 0:        # the cockpit sends no dims — follow the source
        width, height = _auto_canvas(src.name)
    _media_jobs[jid] = {"status": "rendering", "frame": 0,
                        "frames": q["seconds"] * fps, "quote": q,
                        # Tenancy: jobs are keyed by jid for lookup but OWNED by the
                        # creating user — retrieval must not be guessable cross-tenant.
                        "user_id": sess.user.user_id if sess.user else ""}
    # Durability BEFORE the first frame: the source image + job spec go to the
    # vault/transcript now, so an instance death mid-render (deploy, crash) is
    # recoverable — _resume_media_job restarts it from this record.
    try:
        from common import vault as blob
        src_uri = blob.put(f"render_src_{jid}.png", open(src.name, "rb").read(),
                           "image/png", user=sess.user.user_id if sess.user else "founder")
        _remember_turn(sess, "kalai/producer",
                       f"render started — {q['seconds']}s {fx.replace('_', ' ')}, background.",
                       {"kind": "render_pending", "job_id": jid, "src_uri": src_uri,
                        "fx": fx, "seconds": q["seconds"], "budget_usd": budget_usd,
                        "width": width, "height": height, "fps": fps})
    except Exception:  # noqa: BLE001 — durability is best-effort
        pass
    _spawn_render(jid, sess=sess, src_path=src.name, fx=fx, q=q,
                  width=width, height=height, fps=fps,
                  payer=payer, render_key=render_key)
    return {"job_id": jid, "quote": q}


def _spawn_render(jid: str, *, sess: Session, src_path: str, fx: str, q: dict,
                  width: int, height: int, fps: int,
                  payer=None, render_key: str = "") -> None:
    """The one render worker — fresh starts and resumes share it. On success the
    MP4 is copied to the vault + a render_done transcript row (what job/file fall
    back to after a restart); on failure the original spend is refunded (fresh
    starts only — a resume carries no new spend to refund)."""
    vault_user = sess.user.user_id if sess.user else "founder"
    out = src_path.rsplit(".", 1)[0] + "_hdr.mp4"

    def _run() -> None:
        job = _media_jobs[jid]
        try:
            res = media_pipeline.render(
                src_path=src_path, fx=fx, seconds=q["seconds"], out_path=out,
                width=width, height=height, fps=fps,
                progress=lambda i, n: job.update(frame=i, frames=n))
            job.update(status="done", out_path=res["out_path"], verify=res["verify"],
                       receipt=media_crew.receipt(
                           q, measured_vcpu_sec=res["vcpu_sec_estimate"], vertex_usd=0.0))
            try:
                from common import vault as blob
                data = open(res["out_path"], "rb").read()
                uri = blob.put(f"render_{jid}.mp4", data, "video/mp4", user=vault_user)
                job["vault_uri"] = uri
                _remember_turn(sess, "kalai/renderer",
                               f"render done — {q['seconds']}s {fx.replace('_', ' ')} HDR clip.",
                               {"kind": "render_done", "job_id": jid, "vault_uri": uri,
                                "receipt": job["receipt"], "verify": job["verify"]})
            except Exception:  # noqa: BLE001 — durability is best-effort; the job dict still serves
                pass
        except Exception as exc:  # noqa: BLE001 — job surface reports, never raises
            job.update(status="error", error=str(exc)[:300])
            if payer is not None:   # the render died on OUR side — make them whole
                try:
                    credits.refund(payer.user_id, credits.cost("kalai_make"),
                                   credits.TEMPORARY_FAILURE_MSG,
                                   render_key, render_key + ":refund")
                    job["refunded"] = True
                except Exception:  # noqa: BLE001 — idempotent key; ops can replay
                    print(f"REFUND FAILED — replay refund for spend key {render_key!r}")
        finally:
            try:
                os.unlink(src_path)
            except OSError:
                pass

    threading.Thread(target=_run, daemon=True).start()


_resume_lock = threading.Lock()


def _resume_media_job(jid: str, sess: Session) -> Optional[dict]:
    """An interrupted render (the instance died mid-flight) restarts from its
    vaulted source the moment any owner surface asks about it. The original
    spend stands — a resume never charges again. Reads only the caller's own
    store, so tenancy holds."""
    try:
        pending = None
        for m in reversed(sess.store.get_messages(limit=200)):
            meta = m.get("meta") or {}
            if meta.get("job_id") != jid:
                continue
            if meta.get("kind") == "render_done":
                return None                      # it actually finished — nothing to resume
            if meta.get("kind") == "render_pending":
                pending = meta
                break
        if not pending or not pending.get("src_uri"):
            return None
        from common import vault as blob
        data = blob.get(pending["src_uri"], user=sess.user.user_id if sess.user else "founder")
        if not data:
            return None
        fps = int(pending.get("fps") or 24)
        q = media_crew.quote(seconds=int(pending.get("seconds") or 4),
                             budget_usd=float(pending.get("budget_usd") or 1.0),
                             has_source_image=True, wants_hdr=True)
        with _resume_lock:                       # two polling tabs must not double-spawn
            if jid in _media_jobs:
                return _media_jobs[jid]
            src = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            src.write(data)
            src.close()
            _media_jobs[jid] = {"status": "rendering", "frame": 0,
                                "frames": q["seconds"] * fps, "quote": q, "resumed": True,
                                "user_id": sess.user.user_id if sess.user else ""}
        _spawn_render(jid, sess=sess, src_path=src.name,
                      fx=str(pending.get("fx") or "sat_sort"), q=q,
                      width=int(pending.get("width") or 1080),
                      height=int(pending.get("height") or 1920), fps=fps)
        return _media_jobs[jid]
    except Exception:  # noqa: BLE001 — a failed resume reads as unknown job
        return None


def _owned_media_job(jid: str, sess: Session) -> Optional[dict]:
    """A media job is visible only to its creator — a guessed/enumerated jid from
    another tenant reads as unknown (don't reveal existence). Mirrors the run-
    ownership rule on /api/hero/approve."""
    job = _media_jobs.get(jid)
    if not job:
        return None
    owner = job.get("user_id", "")
    caller = sess.user.user_id if sess.user else ""
    if owner != caller:
        return None
    return job


def _persisted_media_job(jid: str, sess: Session) -> Optional[dict]:
    """After a restart the in-memory job table is empty — fall back to the
    transcript record the worker persisted. Reads only the caller's OWN store,
    so the tenancy rule of _owned_media_job carries over for free."""
    try:
        for m in reversed(sess.store.get_messages(limit=200)):
            meta = m.get("meta") or {}
            if meta.get("kind") == "render_done" and meta.get("job_id") == jid:
                return {"status": "done", "persisted": True,
                        "vault_uri": meta.get("vault_uri"),
                        "receipt": meta.get("receipt"), "verify": meta.get("verify")}
    except Exception:  # noqa: BLE001
        pass
    return None


@app.get("/api/kalai/media/jobs")
def media_jobs(sess: Session = Depends(_session_dep)) -> dict[str, Any]:
    """The studio's job board — THIS founder's renders, live ones first, then
    persisted finished ones. Lets the kalai panel show renders outside the chat."""
    _require_auth_if_live(sess.user)
    caller = sess.user.user_id if sess.user else ""
    live, done, seen = [], [], set()
    for jid, job in list(_media_jobs.items()):
        if job.get("user_id", "") != caller:
            continue
        seen.add(jid)
        row = {"job_id": jid, "status": job.get("status"),
               "frame": job.get("frame", 0), "frames": job.get("frames", 0),
               "error": (job.get("error") or "")[:120] or None,
               "verify_ok": (job.get("verify") or {}).get("ok")}
        (live if job.get("status") == "rendering" else done).append(row)
    if not _is_judge(sess.user):
        try:
            resumed_one = False
            for m in reversed(sess.store.get_messages(limit=200)):
                meta = m.get("meta") or {}
                mjid, kind = meta.get("job_id"), meta.get("kind")
                if not mjid or mjid in seen:
                    continue
                if kind == "render_done":
                    seen.add(mjid)
                    done.append({"job_id": mjid, "status": "done",
                                 "persisted": True, "error": None,
                                 "verify_ok": (meta.get("verify") or {}).get("ok")})
                elif kind == "render_pending":
                    # interrupted mid-flight (no done record, not in memory) —
                    # auto-resume the NEWEST one; older ones wait their turn so a
                    # cold instance isn't asked to render everything at once.
                    seen.add(mjid)
                    rj = None if resumed_one else _resume_media_job(mjid, sess)
                    if rj:
                        resumed_one = True
                        live.append({"job_id": mjid, "status": "rendering", "resumed": True,
                                     "frame": rj.get("frame", 0), "frames": rj.get("frames", 0),
                                     "error": None, "verify_ok": None})
                    else:
                        done.append({"job_id": mjid, "status": "interrupted", "error": None,
                                     "verify_ok": None})
        except Exception:  # noqa: BLE001 — the board is best-effort
            pass
    return {"jobs": (list(reversed(live)) + done)[:12]}


@app.get("/api/kalai/media/job/{jid}")
def media_job(jid: str, sess: Session = Depends(_session_dep)) -> Any:
    job = (_owned_media_job(jid, sess) or _persisted_media_job(jid, sess)
           or _resume_media_job(jid, sess))
    if not job:
        return JSONResponse(status_code=404, content={"error": "unknown job"})
    return job


@app.get("/api/kalai/media/file/{jid}")
def media_file(jid: str, sess: Session = Depends(_session_dep)) -> Any:
    job = _owned_media_job(jid, sess)
    if job and job.get("status") == "done" and job.get("out_path") \
            and os.path.exists(job["out_path"]):
        return FileResponse(job["out_path"], media_type="video/mp4",
                            filename="saakshe_hdr.mp4")
    # /tmp is gone (restart) — serve the vault copy the worker persisted.
    pj = job if (job and job.get("vault_uri")) else _persisted_media_job(jid, sess)
    if pj and pj.get("vault_uri"):
        from common import vault as blob
        data = blob.get(pj["vault_uri"], user=sess.user.user_id if sess.user else "founder")
        if data:
            return Response(content=data, media_type="video/mp4", headers={
                "Content-Disposition": 'inline; filename="saakshe_hdr.mp4"'})
    return JSONResponse(status_code=404, content={"error": "not ready"})


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
    # The edit persists (and bills) wherever Supabase can hold the pending row:
    # the full supabase-store profile OR a billing-armed deploy (the gated prod
    # runs the file store but ships the service key) — a creds-free local demo
    # and an anonymous visitor still get the free preview.
    if (not (_supabase_backend() or credits.billing_enabled())) or sess.user is None:
        # Demo preview — the edit is generated but neither charged nor persisted.
        return {"persisted": False, "entity_type": req.entity_type, "diff": diff_json,
                "changed_fields": changed, "new_json": new_json}
    user = sess.user
    billing = _billing_active(user)
    payer = user if billing else None        # judges/owners edit free
    # Server-owned key namespace — see _start_flywheel's note on key squatting.
    edit_key = "edit:" + (req.idem_key or uuid4().hex)
    cost = credits.cost("manas_edit")
    try:
        with credits.charge(payer, "manas_edit", idem_key=edit_key, reason="manas edit"):
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
def _voice_user(token: str):
    """Resolve the founder from the WS ?token= (browsers can't set WS headers).
    Raises auth.AuthError on a bad token; '' resolves to None (anonymous)."""
    if not token:
        return None
    claims = auth.verify_token(token)
    email = claims.get("email", "")
    return auth.User(user_id=claims["sub"], email=email,
                     is_owner=email.lower() in auth.owner_emails())


class _AcceptedWS:
    """Wraps an already-accepted WebSocket so witness_voice.handle_ws's own
    accept() becomes a no-op (first-frame auth must accept early to read the
    auth frame). Everything else delegates to the real socket."""

    def __init__(self, ws: WebSocket) -> None:
        self._ws = ws

    async def accept(self, *args: Any, **kwargs: Any) -> None:
        return None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._ws, name)


@app.websocket("/ws/voice")
async def voice(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token", "")
    ws: Any = websocket
    if not token and _require_signin():
        # First-frame auth: browsers can't set WS headers, and a JWT in the
        # query string leaks into access logs — so the gated prod accepts the
        # socket, then expects {"type":"auth","token":...} as the opening
        # frame. ?token= stays honoured above for back-compat, and the open
        # demo (no gate) keeps today's accept-and-hello flow untouched.
        await websocket.accept()
        try:
            frame = json.loads(await websocket.receive_text())
        except WebSocketDisconnect:
            return
        except Exception:  # noqa: BLE001 — malformed opening frame = unauthenticated
            frame = None
        if isinstance(frame, dict) and frame.get("type") == "auth":
            token = str(frame.get("token") or "")
        ws = _AcceptedWS(websocket)
    try:
        user = _voice_user(token)
    except auth.AuthError:
        user = None
    if _require_signin() and user is None:
        await websocket.close(code=4401)
        return
    # A voice turn is a chat turn (1 credit on the price card) — billed whenever
    # a real founder is on the line, free for the open demo / owners / judges.
    payer = user if _billing_active(user) else None

    def bill_turn() -> None:
        turn_cost = credits.cost("voice_turn")
        if payer is not None and turn_cost > 0:   # COST_VOICE_TURN=0 → free voice
            credits.spend(payer.user_id, turn_cost, "voice turn", "voice:" + uuid4().hex)

    await witness_voice.handle_ws(ws, bill_turn=bill_turn)


# ─── serve the site ───────────────────────────────────────────────────────────
# The cockpit links its css/js relatively (chat-panel.css/js) and og:image needs
# a real /og.png — a safelist, not a static mount, so the .html catch-all (and
# its branded 404) keeps owning every other path.
_ASSET_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


def _serve_page(name: str) -> Any:
    if "/" in name or ".." in name:
        raise HTTPException(status_code=404, detail="not found")
    ext = os.path.splitext(name)[1].lower()
    if ext in _ASSET_TYPES:
        asset = _WEB / name
        if not asset.resolve().is_relative_to(_WEB.resolve()):  # belt-and-braces
            raise HTTPException(status_code=404, detail="not found")
        if asset.exists():
            return FileResponse(asset, media_type=_ASSET_TYPES[ext],
                                headers={"Cache-Control": "public, max-age=86400"})
        raise HTTPException(status_code=404, detail=f"no asset {name!r}")
    if not name.endswith(".html"):
        name += ".html"
    _html_headers = {"Cache-Control": "no-cache"}
    page = _WEB / name
    if not page.resolve().is_relative_to(_WEB.resolve()):  # belt-and-braces
        raise HTTPException(status_code=404, detail="not found")
    if page.exists():
        return FileResponse(page, headers=_html_headers)
    if name == "cockpit.html" and _LEGACY_COCKPIT.exists():
        return FileResponse(_LEGACY_COCKPIT, headers=_html_headers)
    branded = _WEB / "404.html"
    if branded.exists():  # a typo'd URL lands on a saakshe page, not bare JSON
        return FileResponse(branded, status_code=404, headers=_html_headers)
    raise HTTPException(status_code=404, detail=f"no page {name!r}")


_ASSETS_DIR = _WEB / "assets"


@app.get("/assets/{path:path}", include_in_schema=False)
def asset_file(path: str) -> Any:
    """Brand/static assets live under web/assets/ (wordmark SVG/PNG, brand css).
    The only multi-segment web route — same extension safelist + traversal guard
    as _serve_page, same long-lived cache header."""
    ext = os.path.splitext(path)[1].lower()
    if ".." in path or ext not in _ASSET_TYPES:
        raise HTTPException(status_code=404, detail="not found")
    asset = _ASSETS_DIR / path
    if not asset.resolve().is_relative_to(_ASSETS_DIR.resolve()):  # belt-and-braces
        raise HTTPException(status_code=404, detail="not found")
    if asset.exists():
        return FileResponse(asset, media_type=_ASSET_TYPES[ext],
                            headers={"Cache-Control": "public, max-age=86400"})
    raise HTTPException(status_code=404, detail=f"no asset {path!r}")


@app.get("/favicon.ico", include_in_schema=False)
def favicon_ico() -> Any:
    """Browsers hit bare /favicon.ico unprompted — serve the SVG witness mark
    instead of a branded-404 page. (/favicon.svg already rides _ASSET_TYPES.)"""
    return FileResponse(_WEB / "favicon.svg", media_type="image/svg+xml",
                        headers={"Cache-Control": "public, max-age=86400"})


@app.get("/auth/callback", response_class=HTMLResponse)
def auth_callback() -> Any:
    """Completes the Supabase OAuth round-trip (supabase-js parses the URL, then we
    bounce to the cockpit). Explicit route since the catch-all is single-segment."""
    return _serve_page("auth-callback.html")


@app.get("/judge/{token}", include_in_schema=False)
def judge_link(token: str) -> Any:
    """The judge magic link — the capability URL shipped in the Devpost testing
    field. A matching token sets the HttpOnly judge cookie and lands on the
    cockpit, signed in as the judging identity (shared seeded store, mutations
    sealed, free). Feature OFF (no/short SAAKSHE_JUDGE_TOKEN) or a wrong token →
    the branded 404, indistinguishable from any other missing page."""
    expected = _judge_token()
    if expected and hmac.compare_digest(token, expected):
        resp = RedirectResponse("/cockpit", status_code=303)
        resp.set_cookie("sk_judge", token, max_age=30 * 24 * 3600, path="/",
                        httponly=True, secure=True, samesite="lax")
        return resp
    branded = _WEB / "404.html"
    if branded.exists():
        return FileResponse(branded, status_code=404, headers={"Cache-Control": "no-cache"})
    raise HTTPException(status_code=404, detail="not found")


@app.get("/", response_class=HTMLResponse)
def home() -> Any:
    return _serve_page(_HOME)


@app.get("/{page}", response_class=HTMLResponse)
def web_page(page: str) -> Any:
    return _serve_page(page)

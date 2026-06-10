"""saakshe.common.credits — the credit cost-map + an idempotent spend/refund
wrapper over the live Postgres money functions.

WHY: every chargeable founder action (a flywheel run, a connect ingestion, a
manas edit, a kalai make, a kural engage) costs credits. The *authoritative*
arithmetic — balance check, atomic debit, idempotent replay, refund netting —
lives in SECURITY DEFINER Postgres functions (``saakshe_spend`` /
``saakshe_refund`` / ``saakshe_grant_signup``) so the balance can never go
negative and a retried request can never double-charge. This module is the thin,
typed, service-role-only client that calls them over PostgREST RPC and maps their
results into the application's error vocabulary.

ERROR RULE (the witness's "temporary, not charged" promise): an internal failure
is classified by the Postgres error *code*, not a substring of the message. The
only error code that means "the founder is genuinely out of credits" is P0001 with
message ``INSUFFICIENT_CREDITS`` → that surfaces as :class:`OutOfCredits` (the
route answers HTTP 402 with the remaining balance). Every other failure is *ours*:
we refund (under a derived ``:refund`` idempotency key, so the refund itself is
replay-safe) and tell the founder it was temporary and they were not charged —
we never blame them for our side dying mid-run.

SEAM FOR TESTS: the two functions that touch the network are isolated —
``_rpc(fn, params)`` (the RPC POST) and ``_get_balance(user_id)`` (the balance
GET). Tests monkeypatch those with in-process fakes, so the whole credit surface
runs creds-free and offline; nothing else here does I/O.

CONFIG: same secret as the operational store — the service_role key via
:func:`common.supastore._read_key` and the project URL via ``SAAKSHE_SUPABASE_URL``
(the service_role key bypasses RLS, so only this backend can move credits).
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import httpx

from common.config import _int
from common import supastore


# ─── the cost-map ─────────────────────────────────────────────────────────────
# (env var, default) for each chargeable action. ``COSTS`` is the import-time
# snapshot every surface can read cheaply; ``cost()`` re-reads env at call time so
# a per-deploy override (or a test) takes effect without a reimport.
_COST_ENV: dict[str, tuple[str, int]] = {
    "flywheel_run": ("COST_FLYWHEEL_RUN", 20),
    "connect_ingest": ("COST_CONNECT_INGEST", 20),
    "manas_edit": ("COST_MANAS_EDIT", 10),
    "kalai_make": ("COST_KALAI_MAKE", 15),
    "kural_engage": ("COST_KURAL_ENGAGE", 15),
}

COSTS: dict[str, int] = {key: _int(env, default) for key, (env, default) in _COST_ENV.items()}
SIGNUP_GRANT: int = _int("SIGNUP_GRANT", 100)


def cost(key: str) -> int:
    """Credit cost of an action, recomputed from env at call time."""
    env, default = _COST_ENV[key]
    return _int(env, default)


# ─── error vocabulary ─────────────────────────────────────────────────────────
class CreditError(Exception):
    """Any failure moving credits. Carries the Postgres error ``code`` when known."""

    def __init__(self, message: str = "", *, code: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class OutOfCredits(CreditError):
    """The founder genuinely cannot afford the action (Postgres P0001).

    Carries the current ``balance`` so the route can answer HTTP 402 with the
    remaining figure (see :func:`out_of_credits_payload`).
    """

    def __init__(self, *, balance: int) -> None:
        super().__init__("out of credits", code="P0001")
        self.balance = balance


# ─── route-facing constants ───────────────────────────────────────────────────
TEMPORARY_FAILURE_MSG = (
    "Something failed on our side — this is temporary and you were not charged."
)


def out_of_credits_payload(balance: int) -> dict:
    """The HTTP 402 body a route returns when an action is unaffordable."""
    return {"error": "out of credits", "balance": balance}


# ─── the network seams (the only I/O; tests monkeypatch these) ────────────────
def _supabase_url() -> str:
    return os.environ.get("SAAKSHE_SUPABASE_URL", "").rstrip("/")


def _headers() -> dict[str, str]:
    key = supastore._read_key()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _rpc(fn: str, params: dict) -> int:
    """POST a SECURITY DEFINER function via PostgREST RPC; return its int result.

    A P0001 (raised by the function, e.g. INSUFFICIENT_CREDITS) comes back as an
    HTTP 400 carrying ``{"code":"P0001","message":...}`` — we raise that as a
    :class:`CreditError` carrying the code so the caller can classify it. Any other
    transport/HTTP failure is also a :class:`CreditError` (code from the body when
    present, else the HTTP status).
    """
    url = f"{_supabase_url()}/rest/v1/rpc/{fn}"
    try:
        r = httpx.post(url, json=params, headers=_headers(), timeout=15.0)
    except httpx.HTTPError as exc:  # network/timeout — ours, not the founder's
        raise CreditError(str(exc), code="transport") from exc
    if r.status_code >= 400:
        body: dict = {}
        try:
            body = r.json()
        except ValueError:
            body = {}
        raise CreditError(
            body.get("message", r.text),
            code=str(body.get("code", r.status_code)),
        )
    return int(r.json())


def _get_balance(user_id: str) -> int | None:
    """GET the current balance for a user — 0 when no account row exists, None
    when the lookup itself failed (an outage must never read as 'broke')."""
    url = f"{_supabase_url()}/rest/v1/accounts"
    params = {"user_id": f"eq.{user_id}", "select": "balance"}
    try:
        r = httpx.get(url, params=params, headers=_headers(), timeout=15.0)
        r.raise_for_status()
        rows = r.json()
    except (httpx.HTTPError, ValueError):
        return None
    if rows and isinstance(rows, list):
        return int(rows[0].get("balance", 0) or 0)
    return 0


# ─── the public money operations ──────────────────────────────────────────────
def spend(user_id: str, amount: int, reason: str, idem_key: str) -> int:
    """Atomically debit ``amount`` from ``user_id``; return the new balance.

    Idempotent on ``idem_key`` (a replay returns the same balance, no double
    charge). Raises :class:`OutOfCredits` (carrying the current balance) when the
    function reports P0001/INSUFFICIENT_CREDITS; any other failure is a
    :class:`CreditError`.
    """
    try:
        return _rpc(
            "saakshe_spend",
            {
                "p_user_id": user_id,
                "p_amount": amount,
                "p_reason": reason,
                "p_idem_key": idem_key,
            },
        )
    except CreditError as exc:
        # Classify by error CODE, never by a substring of the message: P0001 is the
        # only "genuinely broke" signal the function raises (_rpc always populates
        # .code from the body). Any other code is OUR failure, re-raised as-is.
        if exc.code == "P0001":
            raise OutOfCredits(balance=balance(user_id)) from exc
        raise


def refund(
    user_id: str,
    amount: int,
    reason: str,
    spend_idem_key: str,
    refund_idem_key: str,
) -> int:
    """Refund ``amount`` to ``user_id`` (idempotent on ``refund_idem_key``, netted
    against the original ``spend_idem_key``); return the new balance."""
    return _rpc(
        "saakshe_refund",
        {
            "p_user_id": user_id,
            "p_amount": amount,
            "p_reason": reason,
            "p_spend_idem_key": spend_idem_key,
            "p_refund_idem_key": refund_idem_key,
        },
    )


def grant_signup(user_id: str, email: str, is_owner: bool = False) -> int:
    """Grant the one-time signup credits (idempotent per user); return the
    balance. The owner flag is threaded so the function can mark the account."""
    return _rpc(
        "saakshe_grant_signup",
        {
            "p_user_id": user_id,
            "p_email": email,
            "p_grant": SIGNUP_GRANT,
            "p_is_owner": is_owner,
        },
    )


def balance(user_id: str) -> int | None:
    """Current credit balance for a user — 0 when no account row exists, None
    when the balance can't be read right now (the pill renders '—' for None)."""
    return _get_balance(user_id)


# ─── the charge context manager ───────────────────────────────────────────────
@contextmanager
def charge(user, cost_key: str, *, idem_key: str, reason: str) -> Iterator[dict]:
    """Charge ``cost(cost_key)`` around a block of work, refunding on failure.

    NO-OP (yields ``{'charged': False}`` and touches no RPC) when the founder is
    the owner, or when the Supabase store isn't the active backend — billing tracks
    the persisted backend + a real signed-in founder, NOT the model-liveness mode.
    So the public, creds-free demo (file store, no sign-in) is always free, while a
    real authed user on the Supabase backend is billed even in the hybrid (scripted-
    Claude) deploy — and the billing path stays testable in scripted mode.

    Otherwise it spends *before* the work; if the block raises, it refunds (under a
    derived ``:refund`` key so the refund is replay-safe) and re-raises — the
    "temporary, not charged" promise, classified by the spend's error code, never
    by blaming the founder for an internal failure.
    """
    if (
        getattr(user, "is_owner", False)
        or os.environ.get("SAAKSHE_STORE", "").lower() != "supabase"
    ):
        yield {"charged": False}
        return

    spend(user.user_id, cost(cost_key), reason, idem_key)
    try:
        yield {"charged": True}
    except Exception:
        try:
            refund(
                user.user_id,
                cost(cost_key),
                "internal failure — not charged",
                idem_key,
                idem_key + ":refund",
            )
        except Exception:  # noqa: BLE001 — the refund failing must not mask the
            # original error; the refund key is idempotent, so ops can replay it.
            print(f"REFUND FAILED — replay refund for spend key {idem_key!r}")
        raise

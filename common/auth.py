"""saakshe.common.auth — Supabase (Google sign-in) JWT / JWKS verification.

WHY: the witness, the cockpit and every per-quadrant server need to know *which
founder* is talking so multi-tenant state (the ``user_id`` seam in the store) is
keyed to a real, verified identity instead of a trusted-client claim. Supabase
Auth issues an ES256-signed JWT after Google sign-in; this module verifies the
signature against the project's published JWKS, checks issuer / audience / expiry,
and hands the cockpit a small :class:`User`.

ZERO-TRUST: the signature is verified locally against Supabase's *public* keys
(JWKS) — no service key, no round-trip to Supabase per request. Keys are cached
5 minutes; whole verified tokens ~30s, so a chatty cockpit doesn't re-verify on
every poll.

CONFIG (env):
    SAAKSHE_SUPABASE_URL   the project URL; issuer = ``<url>/auth/v1`` and the
                           JWKS defaults to ``<url>/auth/v1/.well-known/jwks.json``.
    SUPABASE_JWKS_URL      override the JWKS endpoint (optional).
    OWNER_EMAILS           comma-separated allowlist; a matching email → owner.

When ``SAAKSHE_SUPABASE_URL`` is unset, :func:`auth_enabled` is False and surfaces
can run the demo-first, creds-free flow (no sign-in required) unchanged.

USAGE (FastAPI):
    from fastapi import Depends
    @app.get("/me")
    def me(user = Depends(get_current_user)): ...
    @app.get("/feed")
    def feed(user = Depends(optional_user)): ...    # public, owner-aware if signed in
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

import httpx
import jwt
from fastapi import HTTPException

AUDIENCE = "authenticated"
_TOKEN_TTL = 30.0          # seconds a verified token's claims stay cached
_JWKS_TTL = 300.0          # seconds the published signing keys stay cached

# Module-level caches. Tests clear these between cases; do NOT bind local copies
# of _fetch_jwks elsewhere — verify_token calls the global so monkeypatch wins.
_TOKEN_CACHE: dict[str, tuple[float, dict]] = {}   # token -> (expires_at, claims)
_JWKS_CACHE: dict[str, tuple[float, dict]] = {}    # jwks_url -> (expires_at, jwks)


# ── identity ─────────────────────────────────────────────────────────────────
@dataclass
class User:
    user_id: str
    email: str = ""
    is_owner: bool = False


class AuthError(Exception):
    """Raised on any invalid / expired / unverifiable token (missing key, bad
    signature, wrong issuer/audience, missing required claim)."""


# ── configuration helpers ────────────────────────────────────────────────────
def _supabase_url() -> str:
    return os.environ.get("SAAKSHE_SUPABASE_URL", "").strip().rstrip("/")


def auth_enabled() -> bool:
    """True iff a Supabase project URL is configured (auth is wired up)."""
    return bool(_supabase_url())


def _issuer() -> str:
    return f"{_supabase_url()}/auth/v1"


def _jwks_url() -> str:
    override = os.environ.get("SUPABASE_JWKS_URL", "").strip()
    if override:
        return override
    return f"{_supabase_url()}/auth/v1/.well-known/jwks.json"


def owner_emails() -> set[str]:
    """The OWNER_EMAILS allowlist, comma-split, lowercased and stripped."""
    raw = os.environ.get("OWNER_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


# ── JWKS fetch (monkeypatch-friendly; 5-min in-memory cache) ─────────────────
def _fetch_jwks() -> dict:
    """GET the project's JWKS document, cached ~5 min. Tests monkeypatch this."""
    url = _jwks_url()
    cached = _JWKS_CACHE.get(url)
    now = time.monotonic()
    if cached and cached[0] > now:
        return cached[1]
    try:
        resp = httpx.get(url, timeout=5.0)
        resp.raise_for_status()
        jwks = resp.json()
    except Exception as exc:  # noqa: BLE001 — any fetch/parse failure is an auth failure
        raise AuthError(f"jwks_fetch_failed: {exc}") from exc
    _JWKS_CACHE[url] = (now + _JWKS_TTL, jwks)
    return jwks


def _signing_key(token: str):
    """Resolve the public key that signed *token* from the published JWKS, keyed
    on the token's unverified ``kid`` header."""
    try:
        kid = jwt.get_unverified_header(token).get("kid")
    except jwt.InvalidTokenError as exc:
        raise AuthError(f"malformed_token: {exc}") from exc

    jwks = _fetch_jwks()
    jwk_dict = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if jwk_dict is None:
        raise AuthError(f"unknown_kid: {kid}")

    try:
        return jwt.PyJWK(jwk_dict).key
    except Exception:  # noqa: BLE001 — fall back to the EC-specific loader
        try:
            return jwt.algorithms.ECAlgorithm.from_jwk(json.dumps(jwk_dict))
        except Exception as exc:  # noqa: BLE001
            raise AuthError(f"bad_jwk: {exc}") from exc


# ── verification (with a ~30s verified-token cache) ──────────────────────────
def verify_token(token: str) -> dict:
    """Verify *token*'s signature + claims; return the JWT claims dict.

    Caches the verified claims ~30s keyed by the raw token string, so the JWKS is
    never re-fetched for the same token within the window. Raises :class:`AuthError`
    on any failure (missing key, bad signature, wrong issuer/audience, expiry,
    missing required claim).
    """
    if not token:
        raise AuthError("empty_token")

    now = time.monotonic()
    cached = _TOKEN_CACHE.get(token)
    if cached and cached[0] > now:
        return cached[1]

    key = _signing_key(token)
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["ES256", "RS256"],
            audience=AUDIENCE,
            issuer=_issuer(),
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError(f"expired: {exc}") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError(f"invalid_token: {exc}") from exc
    except KeyError as exc:
        raise AuthError(f"missing_claim: {exc}") from exc

    _TOKEN_CACHE[token] = (now + _TOKEN_TTL, claims)
    return claims


# ── header parsing ───────────────────────────────────────────────────────────
def _bearer_token(request) -> str | None:
    """Pull the Bearer token from the request's Authorization header (case-
    insensitive scheme); None when absent or not a Bearer header."""
    header = request.headers.get("authorization")
    if not header:
        return None
    parts = header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    token = parts[1].strip()
    return token or None


# ── FastAPI dependencies ─────────────────────────────────────────────────────
def get_current_user(request) -> User:
    """FastAPI dependency: require a valid Bearer token, return the :class:`User`.

    Raises ``HTTPException(401, 'auth_required')`` when the header is missing /
    malformed or the token fails verification.
    """
    token = _bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="auth_required")
    try:
        claims = verify_token(token)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail="auth_required") from exc
    email = claims.get("email", "")
    return User(
        user_id=claims["sub"],
        email=email,
        is_owner=email.lower() in owner_emails(),
    )


def optional_user(request) -> User | None:
    """Like :func:`get_current_user` but returns None instead of raising when the
    header is missing OR the token is invalid (public, owner-aware-if-signed-in)."""
    try:
        return get_current_user(request)
    except HTTPException:
        return None

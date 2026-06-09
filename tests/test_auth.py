"""Auth tests — Supabase Google JWT/JWKS verification (common.auth).

Self-contained: mints ES256 tokens with a throwaway EC P-256 key, exposes its
public half as a JWK, and monkeypatches ``auth._fetch_jwks`` so nothing ever hits
the network. Pins the seam the cockpit + per-quadrant servers depend on:

  (a) a valid token resolves to the right User (id + email);
  (b) an expired token is rejected (AuthError);
  (c) a token signed by a DIFFERENT key is rejected (AuthError);
  (d) a missing Authorization header → HTTPException 401 (get_current_user) and
      → None (optional_user);
  (e) OWNER_EMAILS membership flips User.is_owner True;
  (f) two verify_token calls on the same token hit the JWKS at most once (cache).
"""

from __future__ import annotations

import base64
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException

from common import auth


# ── key + JWK fixtures ───────────────────────────────────────────────────────
def _b64u(n: int) -> str:
    """P-256 coordinate → unpadded base64url of its 32-byte big-endian encoding."""
    return base64.urlsafe_b64encode(n.to_bytes(32, "big")).rstrip(b"=").decode()


def _new_key():
    return ec.generate_private_key(ec.SECP256R1())


def _private_pem(key) -> bytes:
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _jwk_for(key, kid: str = "testkid") -> dict:
    nums = key.public_key().public_numbers()
    return {
        "kty": "EC",
        "crv": "P-256",
        "x": _b64u(nums.x),
        "y": _b64u(nums.y),
        "kid": kid,
        "alg": "ES256",
        "use": "sig",
    }


def _mint(key, *, email: str = "founder@example.com", sub: str = "user-123",
          exp_delta: int = 3600, kid: str = "testkid") -> str:
    now = int(time.time())
    claims = {
        "iss": "https://ref.supabase.co/auth/v1",
        "aud": "authenticated",
        "sub": sub,
        "email": email,
        "iat": now,
        "exp": now + exp_delta,
    }
    return jwt.encode(claims, _private_pem(key), algorithm="ES256",
                      headers={"kid": kid})


class _FakeRequest:
    """Minimal stand-in for a FastAPI Request — the deps only read .headers.get."""

    def __init__(self, authorization: str | None = None):
        self.headers: dict[str, str] = {}
        if authorization is not None:
            self.headers["authorization"] = authorization


# ── per-test wiring: env + a known signing key + clean caches ────────────────
@pytest.fixture
def signing(monkeypatch):
    monkeypatch.setenv("SAAKSHE_SUPABASE_URL", "https://ref.supabase.co")
    monkeypatch.delenv("SUPABASE_JWKS_URL", raising=False)
    monkeypatch.delenv("OWNER_EMAILS", raising=False)
    key = _new_key()
    jwk = _jwk_for(key)

    calls = {"n": 0}

    def _fake_fetch():
        calls["n"] += 1
        return {"keys": [jwk]}

    monkeypatch.setattr(auth, "_fetch_jwks", _fake_fetch)
    auth._TOKEN_CACHE.clear()
    auth._JWKS_CACHE.clear()
    yield {"key": key, "jwk": jwk, "calls": calls}
    auth._TOKEN_CACHE.clear()
    auth._JWKS_CACHE.clear()


# ── (sanity) the test's own JWK must round-trip ──────────────────────────────
def test_handcrafted_jwk_matches_library_encoding(signing):
    key = signing["key"]
    lib = jwt.algorithms.ECAlgorithm.to_jwk(key.public_key(), as_dict=True)
    assert signing["jwk"]["x"] == lib["x"]
    assert signing["jwk"]["y"] == lib["y"]


# ── (a) valid token → right User ─────────────────────────────────────────────
def test_valid_token_resolves_user(signing):
    token = _mint(signing["key"], email="Founder@Example.com", sub="user-abc")
    claims = auth.verify_token(token)
    assert claims["sub"] == "user-abc"

    user = auth.get_current_user(_FakeRequest(f"Bearer {token}"))
    assert user.user_id == "user-abc"
    assert user.email == "Founder@Example.com"
    assert user.is_owner is False


# ── (b) expired token → AuthError ────────────────────────────────────────────
def test_expired_token_rejected(signing):
    token = _mint(signing["key"], exp_delta=-10)
    with pytest.raises(auth.AuthError):
        auth.verify_token(token)


# ── (c) wrong-key signature → AuthError ──────────────────────────────────────
def test_wrong_key_signature_rejected(signing):
    other = _new_key()  # NOT the key whose JWK is published
    token = _mint(other)
    with pytest.raises(auth.AuthError):
        auth.verify_token(token)


# ── (d) missing header → 401 / None ──────────────────────────────────────────
def test_missing_header_get_current_user_raises_401(signing):
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user(_FakeRequest(None))
    assert exc.value.status_code == 401
    assert exc.value.detail == "auth_required"


def test_missing_header_optional_user_returns_none(signing):
    assert auth.optional_user(_FakeRequest(None)) is None


def test_invalid_token_optional_user_returns_none(signing):
    bad = _mint(_new_key())  # signed by an unpublished key → invalid
    assert auth.optional_user(_FakeRequest(f"Bearer {bad}")) is None


def test_non_bearer_header_get_current_user_raises_401(signing):
    token = _mint(signing["key"])
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user(_FakeRequest(token))  # no "Bearer " scheme
    assert exc.value.status_code == 401


# ── (e) OWNER_EMAILS membership → is_owner ───────────────────────────────────
def test_owner_email_flips_is_owner(signing, monkeypatch):
    monkeypatch.setenv("OWNER_EMAILS", " Founder@Example.com , other@x.com ")
    token = _mint(signing["key"], email="founder@example.com", sub="owner-1")
    user = auth.get_current_user(_FakeRequest(f"Bearer {token}"))
    assert user.is_owner is True
    assert auth.owner_emails() == {"founder@example.com", "other@x.com"}


def test_non_owner_email_is_not_owner(signing, monkeypatch):
    monkeypatch.setenv("OWNER_EMAILS", "boss@x.com")
    token = _mint(signing["key"], email="someone@example.com")
    user = auth.get_current_user(_FakeRequest(f"Bearer {token}"))
    assert user.is_owner is False


# ── (f) caching: same token → JWKS fetched at most once ──────────────────────
def test_verify_token_caches_jwks_lookup(signing):
    token = _mint(signing["key"])
    auth.verify_token(token)
    auth.verify_token(token)
    assert signing["calls"]["n"] <= 1


# ── auth_enabled reflects the URL env ────────────────────────────────────────
def test_auth_enabled_true_when_url_set(signing):
    assert auth.auth_enabled() is True


def test_auth_enabled_false_when_url_unset(monkeypatch):
    monkeypatch.delenv("SAAKSHE_SUPABASE_URL", raising=False)
    assert auth.auth_enabled() is False

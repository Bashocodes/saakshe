"""saakshe.common.supastore — Supabase-backed operational store (drop-in for the
file-based ProjectStore).

WHY: persists the founder's project state, the witness CHAT, manas's versioned
Context Packs, clarifying questions, the ordered event stream, and the HITL gate
queue in Postgres (the `saakshe` schema inside your own Supabase project), so the
product survives restarts, supports multiple founders (the `user_id` seam), and
can push live updates via Supabase Realtime.

ISOLATION + SECURITY: its own dedicated Supabase project (`saakshe`, ref
a dedicated project, separate from your app DB), public schema, RLS deny-by-default
on every table. The BACKEND uses the **service_role** key, which bypasses RLS — so
only this server (holding the secret) can read/write. Client/Realtime access
(anon/authenticated) stays denied until sign-in lands and we add owner policies
keyed on auth.uid().

TRANSPORT: PostgREST over httpx (httpx is already a dependency); public schema, so
no schema-profile headers needed. No new driver dependency.

CONFIG (the one secret you provide — never commit it):
    SAAKSHE_SUPABASE_URL   default https://YOUR-PROJECT.supabase.co
    SAAKSHE_SUPABASE_KEY   the **service_role** secret (Supabase dashboard →
                           saakshe → Settings → API → service_role) — or put it in
                           ~/.saakshe_supabase_key (chmod 600).
`available()` is False when no key is set, so callers fall back to the file store.

WIRING (one line, when the connect-flow sessions settle): in common/project.py,
choose the backend at STORE construction —
    STORE = supastore.SupabaseStore() if supastore.available() else FileProjectStore()
The method surface here mirrors the documented ProjectStore so nothing else changes.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import httpx

DEFAULT_URL = "https://YOUR-PROJECT.supabase.co"  # placeholder — set SAAKSHE_SUPABASE_URL in your env
_SECRET_FILE = Path(os.path.expanduser("~/.saakshe_supabase_key"))
_DEFAULT_USER = "founder"


def _read_key() -> str:
    key = os.environ.get("SAAKSHE_SUPABASE_KEY", "").strip()
    if key:
        return key
    try:
        return _SECRET_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def available() -> bool:
    """True when BOTH a service_role key and a project URL are configured (else the
    callers fall back to the file store). No real project URL ships in the repo — set
    SAAKSHE_SUPABASE_URL (e.g. in .env.local) to opt in."""
    return bool(_read_key()) and bool(os.environ.get("SAAKSHE_SUPABASE_URL", "").strip())


class SupabaseStore:
    """Operational store over the `saakshe` Postgres schema via PostgREST.

    Mirrors the ProjectStore surface (status/connect/ground/version/org) and adds
    chat + event-stream + gate persistence. One row in saakshe.projects per user_id.
    """

    def __init__(self, user_id: str = _DEFAULT_USER, url: Optional[str] = None,
                 key: Optional[str] = None) -> None:
        self.user_id = user_id
        self.url = (url or os.environ.get("SAAKSHE_SUPABASE_URL") or DEFAULT_URL).rstrip("/")
        self.key = key or _read_key()
        if not self.key:
            raise RuntimeError(
                "SupabaseStore needs a service_role key (SAAKSHE_SUPABASE_KEY or "
                "~/.saakshe_supabase_key). Use available() to guard construction."
            )
        self._rest = f"{self.url}/rest/v1"
        self._client = httpx.Client(timeout=15.0, headers={
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        })
        self._pid: Optional[str] = None

    # ── low-level ────────────────────────────────────────────────────────────
    def _get(self, table: str, **params) -> list[dict]:
        r = self._client.get(f"{self._rest}/{table}", params=params)
        r.raise_for_status()
        return r.json()

    def _insert(self, table: str, row: dict) -> dict:
        r = self._client.post(f"{self._rest}/{table}", json=row,
                              headers={"Prefer": "return=representation"})
        r.raise_for_status()
        out = r.json()
        return out[0] if isinstance(out, list) and out else (out or {})

    def _patch(self, table: str, match: dict, patch: dict) -> dict:
        params = {k: f"eq.{v}" for k, v in match.items()}
        r = self._client.patch(f"{self._rest}/{table}", params=params, json=patch,
                               headers={"Prefer": "return=representation"})
        r.raise_for_status()
        out = r.json()
        return out[0] if isinstance(out, list) and out else (out or {})

    def _delete(self, table: str, match: dict) -> None:
        params = {k: f"eq.{v}" for k, v in match.items()}
        self._client.delete(f"{self._rest}/{table}", params=params).raise_for_status()

    # ── the project row (one per user) ───────────────────────────────────────
    def _project(self) -> dict:
        rows = self._get("projects", user_id=f"eq.{self.user_id}", select="*", limit=1)
        if rows:
            self._pid = rows[0]["id"]
            return rows[0]
        row = self._insert("projects", {"user_id": self.user_id})
        self._pid = row["id"]
        return row

    @property
    def pid(self) -> str:
        if self._pid is None:
            self._project()
        return self._pid  # type: ignore[return-value]

    # ── ProjectStore surface (the swappable interface) ───────────────────────
    def is_connected(self) -> bool:
        return bool(self._get("connections", project_id=f"eq.{self.pid}", select="id", limit=1))

    def is_grounded(self) -> bool:
        return bool(self._project().get("grounded"))

    @property
    def version(self) -> str:
        return self._project().get("version", "v0")

    def org_for_flywheel(self) -> dict:
        return self._project().get("org") or {}

    def add_connection(self, kind: str, ref: str, meta: Optional[dict] = None) -> dict:
        conn = self._insert("connections", {
            "project_id": self.pid, "kind": kind, "ref": ref, "meta": meta or {}})
        if self._project().get("status") == "empty":
            self._patch("projects", {"id": self.pid}, {"status": "connected"})
        return conn

    def list_connections(self) -> list[dict]:
        return self._get("connections", project_id=f"eq.{self.pid}", select="*",
                         order="created_at.asc")

    def commit_pack(self, version: str, facts: list, voice_rules: list,
                    brand_rules: list, grounded: bool = True) -> dict:
        pack = self._insert("context_packs", {
            "project_id": self.pid, "version": version, "facts": facts,
            "voice_rules": voice_rules, "brand_rules": brand_rules, "grounded": grounded})
        self._patch("projects", {"id": self.pid},
                    {"version": version, "grounded": grounded, "status": "grounded"})
        return pack

    def latest_pack(self) -> Optional[dict]:
        rows = self._get("context_packs", project_id=f"eq.{self.pid}", select="*",
                         order="created_at.desc", limit=1)
        return rows[0] if rows else None

    def set_org(self, org: dict) -> None:
        self._patch("projects", {"id": self.pid}, {"org": org})

    # ── clarifying questions ─────────────────────────────────────────────────
    def add_question(self, q: dict) -> dict:
        return self._insert("questions", {"project_id": self.pid, **q})

    def open_questions(self) -> list[dict]:
        return self._get("questions", project_id=f"eq.{self.pid}", status="eq.open", select="*")

    def answer_question(self, qid: str, answer: str) -> dict:
        return self._patch("questions", {"project_id": self.pid, "qid": qid},
                           {"status": "answered", "answer": answer})

    # ── witness chat ─────────────────────────────────────────────────────────
    def append_message(self, role: str, text: str, run_id: str = "", meta: Optional[dict] = None) -> dict:
        return self._insert("messages", {
            "project_id": self.pid, "run_id": run_id or None, "role": role,
            "text": text, "meta": meta or {}})

    def get_messages(self, limit: int = 100) -> list[dict]:
        return self._get("messages", project_id=f"eq.{self.pid}", select="*",
                         order="created_at.asc", limit=limit)

    # ── the ordered event stream (operational mirror; BigQuery = analytics) ──
    def append_event(self, run_id: str, seq: int, source: str, agent: str,
                     text: str, span: str = "agent_run", kind: str = "note",
                     meta: Optional[dict] = None) -> dict:
        return self._insert("events", {
            "run_id": run_id, "seq": seq, "source": source, "agent": agent,
            "text": text, "span": span, "kind": kind, "meta": meta or {}})

    def events_since(self, run_id: str, cursor: int = 0) -> list[dict]:
        return self._get("events", run_id=f"eq.{run_id}", seq=f"gte.{cursor}",
                         select="*", order="seq.asc")

    # ── the HITL gate queue ──────────────────────────────────────────────────
    def upsert_gate(self, run_id: str, gate_id: str, quadrant: str, gate_kind: str,
                    proposal: str, reversible: bool, agent: str = "", detail: Optional[dict] = None) -> dict:
        return self._insert("gates", {
            "run_id": run_id, "gate_id": gate_id, "quadrant": quadrant, "agent": agent,
            "gate_kind": gate_kind, "proposal": proposal, "reversible": reversible,
            "detail": detail or {}})

    def open_gates(self, run_id: Optional[str] = None) -> list[dict]:
        params: dict[str, Any] = {"status": "eq.open", "select": "*", "order": "created_at.asc"}
        if run_id:
            params["run_id"] = f"eq.{run_id}"
        return self._get("gates", **params)

    def resolve_gate(self, run_id: str, gate_id: str, decision: str = "approved") -> dict:
        return self._patch("gates", {"run_id": run_id, "gate_id": gate_id}, {"status": decision})

    # ── status (the single dict the cockpit boots on — mirrors ProjectStore) ─
    def status_dict(self) -> dict:
        p = self._project()
        return {
            "connected": self.is_connected(),
            "grounded": bool(p.get("grounded")),
            "status": p.get("status", "empty"),
            "org": p.get("org") or {},
            "version": p.get("version", "v0"),
            "connections": [{"kind": c["kind"], "ref": c["ref"]} for c in self.list_connections()],
            "open_questions": self.open_questions(),
            "backend": "supabase",
        }

    def reset(self) -> dict:
        """Wipe this user's project back to empty-state (re-connect from scratch)."""
        self._delete("projects", {"user_id": self.user_id})  # cascades to children
        self._pid = None
        return self.status_dict()


if __name__ == "__main__":  # tiny connectivity self-test (needs the service key)
    import sys
    if not available():
        print("✗ no service key — set SAAKSHE_SUPABASE_KEY or ~/.saakshe_supabase_key"); sys.exit(1)
    s = SupabaseStore(user_id="selftest")
    print("project:", s.pid)
    s.append_message("founder", "ping")
    print("messages:", len(s.get_messages()))
    s.reset()
    print("✓ supabase store reachable + RW ok (selftest reset)")

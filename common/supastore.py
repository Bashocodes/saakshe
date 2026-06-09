"""saakshe.common.supastore — Supabase-backed operational store (drop-in for the
file-based ProjectStore).

WHY: persists the founder's project state, the witness CHAT, manas's versioned
Context Packs, clarifying questions, the ordered event stream, and the HITL gate
queue in Postgres (the dedicated `saakshe` Supabase project), so the product
survives restarts, supports multiple founders (the `user_id` seam), and can push
live updates via Supabase Realtime.

ISOLATION + SECURITY: its own dedicated Supabase project, public schema, RLS
deny-by-default on every table. The BACKEND uses the **service_role** key, which
bypasses RLS — so only this server (holding the secret) can read/write. Client/
Realtime access (anon/authenticated) stays denied until sign-in lands and we add
owner policies keyed on auth.uid().

INTERCHANGEABLE WITH ProjectStore: this class mirrors the file ``ProjectStore``
public surface EXACTLY (``add_connection``/``set_org``/``set_status``/
``commit_pack``/``pack``/``all_facts``/``set_questions``/``open_questions``/
``blocking_questions``/``answer_question``/``is_connected``/``is_grounded``/
``version``/``ingest_status``/``org``/``connections``/``org_for_flywheel``/
``status_dict``/``reset``) returning the same shapes (``a2a.ContextPack``,
``a2a.ClarifyingQuestion``, ``project.Connection``) — so the orchestrator, manas,
corpus, and the service call it unchanged. It activates only when
``SAAKSHE_STORE=supabase`` AND a service key is configured; otherwise the callers
use the file store and the 135 demo tests are untouched.

TRANSPORT: PostgREST over httpx (already a dependency); public schema, so no
schema-profile headers needed. No new driver dependency.

CONFIG (the one secret you provide — never commit it):
    SAAKSHE_SUPABASE_URL   the project URL (e.g. https://<ref>.supabase.co)
    SAAKSHE_SUPABASE_KEY   the **service_role** secret — or ~/.saakshe_supabase_key
                           (chmod 600).
``available()`` is False when no key is set, so callers fall back to the file store.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import httpx

from . import a2a

DEFAULT_URL = "https://YOUR-PROJECT.supabase.co"  # placeholder — set SAAKSHE_SUPABASE_URL in your env
_SECRET_FILE = Path(os.path.expanduser("~/.saakshe_supabase_key"))
_DEFAULT_USER = "founder"

# Ingest-lifecycle vocabulary, mirrored from project.py so we never import it at
# module load (project lazily imports THIS module when SAAKSHE_STORE=supabase, so a
# top-level `from . import project` here would be a circular import). project.* is
# imported lazily inside the two methods that build Connection objects.
EMPTY = "empty"
CONNECTING = "connecting"
INGESTING = "ingesting"
NEEDS_ANSWERS = "needs_answers"
GROUNDED = "grounded"
TOPIC = "company"


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
    """Operational store over the public schema via PostgREST. One row in
    ``projects`` per ``user_id``; mirrors the file ProjectStore surface exactly."""

    def __init__(self, user_id: str = _DEFAULT_USER, url: Optional[str] = None,
                 key: Optional[str] = None) -> None:
        self.user_id = user_id
        self.user = user_id  # ProjectStore exposes `.user`; keep the alias for parity
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

    # ── state queries (ProjectStore parity) ──────────────────────────────────
    def is_connected(self) -> bool:
        return bool(self._get("connections", project_id=f"eq.{self.pid}", select="id", limit=1))

    def is_grounded(self) -> bool:
        p = self._project()
        return bool(p.get("grounded")) and p.get("version", "v0") != "v0"

    @property
    def version(self) -> str:
        return self._project().get("version", "v0")

    @property
    def ingest_status(self) -> str:
        return self._project().get("status", EMPTY)

    @property
    def org(self) -> dict:
        return self._project().get("org") or {"name": "", "kind": "", "one_liner": ""}

    @property
    def connections(self) -> list:
        """Live connections as ``project.Connection`` objects (so callers can read
        ``c.kind`` / ``c.ref`` / ``c.meta`` exactly as on the file store)."""
        from . import project  # lazy: avoids the project↔supastore import cycle
        return [
            project.Connection(kind=c["kind"], ref=c["ref"],
                               status=c.get("status") or "connected",
                               meta=c.get("meta") or {})
            for c in self.list_connections()
        ]

    def list_connections(self) -> list[dict]:
        return self._get("connections", project_id=f"eq.{self.pid}", select="*",
                         order="created_at.asc")

    def org_for_flywheel(self) -> dict:
        """The org dict the orchestrator/arivu consume (never a canned default)."""
        org = self.org
        return {
            "name": org.get("name") or "your company",
            "kind": org.get("kind") or "the connected company",
            "memory_pack": self.version,
            "one_liner": org.get("one_liner", ""),
        }

    # ── mutations ─────────────────────────────────────────────────────────────
    def add_connection(self, kind: str, ref: str, meta: Optional[dict] = None):
        """Register a source; return a ``project.Connection`` (parity with file store)."""
        from . import project  # lazy import (cycle-safe)
        self._insert("connections", {
            "project_id": self.pid, "kind": kind, "ref": ref, "meta": meta or {}})
        if self._project().get("status") in (EMPTY, None):
            self._patch("projects", {"id": self.pid}, {"status": CONNECTING})
        return project.Connection(kind=kind, ref=ref, meta=meta or {})

    def set_status(self, status: str) -> None:
        self._patch("projects", {"id": self.pid}, {"status": status})

    def set_org(self, name: str = "", kind: str = "", one_liner: str = "") -> None:
        org = dict(self.org)
        if name:
            org["name"] = name
        if kind:
            org["kind"] = kind
        if one_liner:
            org["one_liner"] = one_liner
        self._patch("projects", {"id": self.pid}, {"org": org})

    def _next_version(self) -> str:
        try:
            n = int(str(self.version).lstrip("v") or "0")
        except ValueError:
            n = 0
        return f"v{n + 1}"

    def commit_pack(self, facts: list, voice_rules: list, brand_rules: list, *,
                    topic: str = TOPIC, note: str = "",
                    groundedness: Optional[float] = None) -> str:
        """Write a Context Pack and tick the company memory version; return the new
        version. Grounded once a clean pack exists and no contradiction blocks it
        (missing-field questions are enrichment, they don't block) — mirrors the
        file store's grounding rule."""
        new_v = self._next_version()
        has_facts = bool(facts)
        blocking = bool(self.blocking_questions())
        self._insert("context_packs", {
            "project_id": self.pid, "version": new_v,
            "facts": [dict(f) for f in facts],
            "voice_rules": list(voice_rules), "brand_rules": list(brand_rules),
            "grounded": has_facts})
        grounded = has_facts and not blocking
        if grounded:
            status = GROUNDED
        elif blocking:
            status = NEEDS_ANSWERS
        else:
            status = self.ingest_status
        self._patch("projects", {"id": self.pid},
                    {"version": new_v, "grounded": grounded, "status": status})
        return new_v

    def latest_pack(self) -> Optional[dict]:
        rows = self._get("context_packs", project_id=f"eq.{self.pid}", select="*",
                         order="created_at.desc", limit=1)
        return rows[0] if rows else None

    def pack(self, topic: str = TOPIC) -> a2a.ContextPack:
        """The versioned, source-cited Context Pack — empty/ungrounded when nothing
        is committed yet (preserves the refuse-out-of-corpus contract)."""
        row = self.latest_pack()
        if not row or not row.get("facts"):
            return a2a.ContextPack(version=self.version, topic=topic, facts=[],
                                   voice_rules=[], brand_rules=[], grounded=False)
        return a2a.ContextPack(
            version=row.get("version", self.version), topic=topic,
            facts=[dict(f) for f in row.get("facts", [])],
            voice_rules=list(row.get("voice_rules", [])),
            brand_rules=list(row.get("brand_rules", [])),
            grounded=bool(row.get("facts")),
        )

    def all_facts(self) -> list[dict]:
        row = self.latest_pack()
        return [dict(f) for f in (row or {}).get("facts", [])]

    # ── clarifying questions (a2a.ClarifyingQuestion parity) ──────────────────
    def _to_question(self, row: dict) -> a2a.ClarifyingQuestion:
        return a2a.ClarifyingQuestion(
            id=row.get("qid", ""), text=row.get("text", ""), why=row.get("why", "") or "",
            trigger=row.get("trigger", "") or "", blocks=row.get("blocks", "") or "",
            status=row.get("status", "open"), answer=row.get("answer", "") or "",
            options=list(row.get("options") or []), sources=list(row.get("sources") or []),
        )

    def set_questions(self, questions: list) -> None:
        """Replace the open question set with a freshly-detected one; answered
        questions are preserved (a re-ingest never re-asks what's settled)."""
        existing = self._get("questions", project_id=f"eq.{self.pid}", select="*")
        answered_ids = {q["qid"] for q in existing if q.get("status") == "answered"}
        # Drop currently-open rows (we re-detect them); keep answered rows untouched.
        self._delete("questions", {"project_id": self.pid, "status": "open"})
        for q in questions:
            if q.id in answered_ids:
                continue
            self._insert("questions", {
                "project_id": self.pid, "qid": q.id, "text": q.text, "why": q.why,
                "trigger": q.trigger, "blocks": q.blocks, "status": q.status,
                "answer": q.answer, "options": list(q.options), "sources": list(q.sources)})
        if self.blocking_questions() and self.ingest_status in (INGESTING, CONNECTING, GROUNDED):
            self.set_status(NEEDS_ANSWERS)

    def open_questions(self) -> list:
        return [self._to_question(r) for r in
                self._get("questions", project_id=f"eq.{self.pid}", status="eq.open", select="*")]

    def blocking_questions(self) -> list:
        """Open questions that BLOCK grounding — only a contradiction blocks."""
        return [q for q in self.open_questions() if q.trigger == "contradiction"]

    def answer_question(self, qid: str, answer: str):
        rows = self._get("questions", project_id=f"eq.{self.pid}", qid=f"eq.{qid}",
                         select="*", limit=1)
        if not rows:
            return None
        self._patch("questions", {"project_id": self.pid, "qid": qid},
                    {"status": "answered", "answer": answer})
        row = dict(rows[0]); row["status"] = "answered"; row["answer"] = answer
        return self._to_question(row)

    # ── witness chat ─────────────────────────────────────────────────────────
    def append_message(self, role: str, text: str, run_id: str = "", meta: Optional[dict] = None) -> dict:
        return self._insert("messages", {
            "project_id": self.pid, "run_id": run_id or None, "role": role,
            "text": text, "meta": meta or {}})

    def get_messages(self, limit: int = 100) -> list[dict]:
        return self._get("messages", project_id=f"eq.{self.pid}", select="*",
                         order="created_at.asc", limit=limit)

    # ── the ordered event stream (low-level; SupabaseEventStream is the surface) ─
    def append_event(self, run_id: str, seq: int, source: str, agent: str,
                     text: str, span: str = "agent_run", kind: str = "note",
                     meta: Optional[dict] = None) -> dict:
        return self._insert("events", {
            "user_id": self.user_id, "run_id": run_id, "seq": seq, "source": source,
            "agent": agent, "text": text, "span": span, "kind": kind, "meta": meta or {}})

    def events_since(self, run_id: str, cursor: int = 0) -> list[dict]:
        return self._get("events", user_id=f"eq.{self.user_id}", run_id=f"eq.{run_id}",
                         seq=f"gte.{cursor}", select="*", order="seq.asc")

    # ── the HITL gate queue (low-level) ───────────────────────────────────────
    def upsert_gate(self, run_id: str, gate_id: str, quadrant: str, gate_kind: str,
                    proposal: str, reversible: bool, agent: str = "", detail: Optional[dict] = None) -> dict:
        return self._insert("gates", {
            "user_id": self.user_id, "run_id": run_id, "gate_id": gate_id, "quadrant": quadrant,
            "agent": agent, "gate_kind": gate_kind, "proposal": proposal,
            "reversible": reversible, "detail": detail or {}})

    def open_gates(self, run_id: Optional[str] = None) -> list[dict]:
        params: dict[str, Any] = {"user_id": f"eq.{self.user_id}", "status": "eq.open",
                                  "select": "*", "order": "created_at.asc"}
        if run_id:
            params["run_id"] = f"eq.{run_id}"
        return self._get("gates", **params)

    def resolve_gate(self, run_id: str, gate_id: str, decision: str = "approved") -> dict:
        return self._patch("gates",
                            {"user_id": self.user_id, "run_id": run_id, "gate_id": gate_id},
                            {"status": decision})

    # ── status (the single dict the cockpit boots on — file-store shape) ──────
    def status_dict(self) -> dict:
        p = self._project()
        all_q = self._get("questions", project_id=f"eq.{self.pid}", select="*")
        return {
            "connected": self.is_connected(),
            "grounded": self.is_grounded(),
            "ingest_status": p.get("status", EMPTY),
            "version": p.get("version", "v0"),
            "org": p.get("org") or {"name": "", "kind": "", "one_liner": ""},
            "connections": [c.as_dict() for c in self.connections],
            "open_questions": [q.as_dict() for q in self.open_questions()],
            "questions": [self._to_question(r).as_dict() for r in all_q],
            "fact_count": len(self.all_facts()),
            "connected_day": 0,
            "backend": "supabase",
        }

    def reset(self, persist: bool = True) -> dict:
        """Wipe this user's project back to empty-state (re-connect from scratch).
        ``persist`` is accepted for ProjectStore signature parity (always persisted)."""
        self._delete("projects", {"user_id": self.user_id})  # cascades to children
        # events/gates are keyed by user_id (no project FK), so clear them explicitly.
        try:
            self._delete("events", {"user_id": self.user_id})
            self._delete("gates", {"user_id": self.user_id})
        except httpx.HTTPError:
            pass
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

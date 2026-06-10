"""saakshe.common.project — the connected-project store (the setu bridge's state).

The one place the whole company learns WHO it is working for. It starts EMPTY:
no connections, no org, no facts, version "v0", grounded=False. Nothing is canned.
The founder connects sources (a GitHub repo, a website, optionally docs/socials)
over setu; manas ingests them for real and commits a versioned, source-cited
Context Pack here; the flywheel reads its org + grounding from here.

This is what makes "empty-state until you connect" and "no fabricated data" true at
the data layer: every surface (cockpit, witness, orchestrator) asks this store, and
the store has nothing until a real ingestion fills it. The refusal contract in
``manas/tools/corpus.py`` is unchanged — it just reads an empty store by default
instead of a pre-seeded Sundara one.

Single-tenant for now (one project), but every accessor takes a ``user`` key so the
deferred sign-in/multi-tenant work is a seam, not a rewrite. Persisted as JSON so a
connection survives a server restart (the demo connects once, then just runs).
"""

from __future__ import annotations

import contextvars
import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from . import a2a

# Where the store persists. Override with SAAKSHE_PROJECT_DIR (tests point it at a
# tmp dir). The default is outside the repo so a connect never dirties git.
_DIR = Path(os.environ.get("SAAKSHE_PROJECT_DIR", "~/.saakshe")).expanduser()

# Ingest lifecycle (drives the cockpit's empty → connect → grounded states).
EMPTY = "empty"            # nothing connected
CONNECTING = "connecting"  # sources added, not yet ingested
INGESTING = "ingesting"    # manas is reading the sources right now
NEEDS_ANSWERS = "needs_answers"  # ingested, but open clarifying questions block grounding
GROUNDED = "grounded"      # a Context Pack is committed and clean

# The one topic the company's memory is keyed under for now (mirrors the single
# company-wide Context Pack the constellation describes). Kept as a constant so a
# future multi-topic store is a widening, not a rename.
TOPIC = "company"


@dataclass
class Connection:
    kind: str                       # "github" | "website" | "docs" | "social"
    ref: str                        # repo url/path, site url, docs url, handle
    status: str = "connected"       # "connected" | "error"
    day: int = 0                    # connected_day relative to first connect
    meta: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"kind": self.kind, "ref": self.ref, "status": self.status,
                "day": self.day, "meta": dict(self.meta)}


class ProjectStore:
    """One founder's connected project. Empty until a real source is connected."""

    def __init__(self, user: str = "founder") -> None:
        self.user = user
        self._lock = threading.RLock()
        self.reset(persist=False)
        self._load()

    # ── lifecycle ────────────────────────────────────────────────────────────
    def reset(self, persist: bool = True) -> None:
        with self._lock:
            self.version = "v0"                      # ticks v0→v1→… on each commit
            self.org: dict = {"name": "", "kind": "", "one_liner": ""}
            self.connections: list[Connection] = []
            self.packs: dict[str, dict] = {}         # topic -> ContextPack.as_dict()
            self.questions: list[a2a.ClarifyingQuestion] = []
            self.ingest_status = EMPTY
            self.connected_at: Optional[float] = None
            self.history: list[dict] = []            # [{version, at, note}]
            self.assets: list[dict] = []             # brand-asset vault index (bytes live in common/vault.py)
        if persist:
            self._save()

    @property
    def _path(self) -> Path:
        return _DIR / f"project_{self.user}.json"

    def _load(self) -> None:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        with self._lock:
            self.version = raw.get("version", "v0")
            self.org = raw.get("org") or {"name": "", "kind": "", "one_liner": ""}
            self.connections = [Connection(**c) for c in raw.get("connections", [])]
            self.packs = raw.get("packs", {})
            self.questions = [a2a.ClarifyingQuestion(**q) for q in raw.get("questions", [])]
            self.ingest_status = raw.get("ingest_status", EMPTY)
            self.connected_at = raw.get("connected_at")
            self.history = raw.get("history", [])
            self.assets = raw.get("assets", [])

    def _save(self) -> None:
        with self._lock:
            payload = {
                "version": self.version, "org": self.org,
                "connections": [c.as_dict() for c in self.connections],
                "packs": self.packs,
                "questions": [q.as_dict() for q in self.questions],
                "ingest_status": self.ingest_status,
                "connected_at": self.connected_at, "history": self.history,
                "assets": self.assets,
            }
        try:
            _DIR.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self._path)
        except OSError:
            pass

    # ── flywheel-run snapshots (restart-proofing; _RUNS is a cache, not the record) ─
    _RUN_ID_RE = re.compile(r"[A-Za-z0-9_\-]{1,64}")

    def _runs_dir(self) -> Path:
        return _DIR / "runs" / self.user

    def save_run(self, run_id: str, snapshot: dict) -> None:
        """Persist one flywheel run's JSON snapshot (atomic write, fail-soft —
        a blob error must never break the run it is backing up)."""
        if not self._RUN_ID_RE.fullmatch(run_id or ""):
            return
        try:
            d = self._runs_dir()
            d.mkdir(parents=True, exist_ok=True)
            tmp = d / f"{run_id}.json.tmp"
            tmp.write_text(json.dumps(snapshot), encoding="utf-8")
            tmp.replace(d / f"{run_id}.json")
        except OSError:
            pass

    def load_run(self, run_id: str) -> Optional[dict]:
        """The snapshot save_run persisted, or None. The run_id is validated so a
        caller-supplied id can never become a file path."""
        if not self._RUN_ID_RE.fullmatch(run_id or ""):
            return None
        try:
            return json.loads((self._runs_dir() / f"{run_id}.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    # ── state queries ─────────────────────────────────────────────────────────
    def is_connected(self) -> bool:
        return bool(self.connections)

    def is_grounded(self) -> bool:
        return self.ingest_status == GROUNDED and self.version != "v0"

    def _day(self) -> int:
        if not self.connected_at:
            return 0
        return int((time.time() - self.connected_at) // 86400)

    # ── mutations ──────────────────────────────────────────────────────────────
    def add_connection(self, kind: str, ref: str, meta: Optional[dict] = None) -> Connection:
        with self._lock:
            if self.connected_at is None:
                self.connected_at = time.time()
            # Replace an existing connection of the same kind (one repo, one site…).
            self.connections = [c for c in self.connections if c.kind != kind]
            conn = Connection(kind=kind, ref=ref, day=self._day(), meta=meta or {})
            self.connections.append(conn)
            if self.ingest_status == EMPTY:
                self.ingest_status = CONNECTING
        self._save()
        return conn

    def set_status(self, status: str) -> None:
        with self._lock:
            self.ingest_status = status
        self._save()

    def set_org(self, name: str = "", kind: str = "", one_liner: str = "") -> None:
        with self._lock:
            if name:
                self.org["name"] = name
            if kind:
                self.org["kind"] = kind
            if one_liner:
                self.org["one_liner"] = one_liner
        self._save()

    def _next_version(self) -> str:
        try:
            n = int(str(self.version).lstrip("v") or "0")
        except ValueError:
            n = 0
        return f"v{n + 1}"

    def commit_pack(
        self,
        facts: list[dict],
        voice_rules: list[str],
        brand_rules: list[str],
        *,
        topic: str = TOPIC,
        note: str = "",
        groundedness: Optional[float] = None,
    ) -> str:
        """Write a curated Context Pack and tick the company memory version.

        Returns the new version. The pack carries the version it was committed at so
        a downstream cite can name the exact memory it grounded in.
        """
        with self._lock:
            new_v = self._next_version()
            pack = a2a.ContextPack(
                version=new_v, topic=topic,
                facts=[dict(f) for f in facts],
                voice_rules=list(voice_rules), brand_rules=list(brand_rules),
                grounded=bool(facts),
            )
            self.packs[topic] = pack.as_dict()
            self.version = new_v
            self.history.append({"version": new_v, "at": time.time(),
                                 "note": note or f"committed {len(facts)} cited facts",
                                 "groundedness": groundedness})
            # Grounded once a clean pack exists and no BLOCKING (contradiction)
            # question is open. Missing-field questions are enrichment — they're
            # surfaced but don't stop the company from being grounded enough to run.
            if facts and not self.blocking_questions():
                self.ingest_status = GROUNDED
            elif self.blocking_questions():
                self.ingest_status = NEEDS_ANSWERS
        self._save()
        return new_v

    def pack(self, topic: str = TOPIC) -> a2a.ContextPack:
        """The versioned, source-cited Context Pack — empty + ungrounded by default.

        This is what corpus.context_pack delegates to: an unconnected/empty store
        returns grounded=False, preserving the refuse-out-of-corpus contract with no
        Sundara pre-seed."""
        blob = self.packs.get(topic)
        if not blob:
            return a2a.ContextPack(version=self.version, topic=topic, facts=[],
                                   voice_rules=[], brand_rules=[], grounded=False)
        return a2a.ContextPack(
            version=blob.get("version", self.version), topic=topic,
            facts=[dict(f) for f in blob.get("facts", [])],
            voice_rules=list(blob.get("voice_rules", [])),
            brand_rules=list(blob.get("brand_rules", [])),
            grounded=bool(blob.get("facts")),
        )

    def all_facts(self) -> list[dict]:
        out: list[dict] = []
        for blob in self.packs.values():
            out.extend(dict(f) for f in blob.get("facts", []))
        return out

    # ── brand-asset vault index (binary assets; bytes live in common/vault.py) ──
    def add_asset(self, *, kind: str, filename: str, content_type: str, uri: str,
                  sha256: str, tags=(), provenance: str = "") -> dict:
        """Record one vault asset and tick the memory version. Dedup by sha256:
        identical bytes are stored once (the blob is content-addressed too)."""
        with self._lock:
            for a in self.assets:
                if a.get("sha256") == sha256:
                    return a                       # already held — no duplicate
            rec = {"id": f"asset-{len(self.assets) + 1}", "kind": kind,
                   "filename": filename, "content_type": content_type, "uri": uri,
                   "sha256": sha256, "tags": list(tags), "provenance": provenance,
                   "version": self._next_version(), "day": self._day()}
            self.assets.append(rec)
            self.version = rec["version"]
            self.history.append({"version": self.version, "at": time.time(),
                                 "note": f"added {kind} asset {filename}"})
        self._save()
        return rec

    def assets_for(self, kinds=None, tags=None) -> list[dict]:
        """The serve selector — filter the index by kind and/or tag (in-memory)."""
        out = self.assets
        if kinds:
            ks = set(kinds)
            out = [a for a in out if a.get("kind") in ks]
        if tags:
            ts = set(tags)
            out = [a for a in out if ts & set(a.get("tags", []))]
        return [dict(a) for a in out]

    def asset_count(self) -> int:
        return len(self.assets)

    # ── clarifying questions ────────────────────────────────────────────────────
    def set_questions(self, questions: list[a2a.ClarifyingQuestion]) -> None:
        """Replace the open question set with a freshly-detected one (answered ones
        are preserved so a re-ingest doesn't re-ask what the founder already settled)."""
        with self._lock:
            answered = {q.id: q for q in self.questions if q.status == "answered"}
            merged: list[a2a.ClarifyingQuestion] = []
            for q in questions:
                if q.id in answered:
                    merged.append(answered[q.id])
                else:
                    merged.append(q)
            # keep any previously-answered questions not re-detected
            for qid, q in answered.items():
                if not any(m.id == qid for m in merged):
                    merged.append(q)
            self.questions = merged
            # Only a contradiction blocks grounding; missing-field doubts are enrichment.
            if self.blocking_questions() and self.ingest_status in (INGESTING, CONNECTING, GROUNDED):
                self.ingest_status = NEEDS_ANSWERS
        self._save()

    def open_questions(self) -> list[a2a.ClarifyingQuestion]:
        return [q for q in self.questions if q.status == "open"]

    def blocking_questions(self) -> list[a2a.ClarifyingQuestion]:
        """Open questions that BLOCK grounding — a contradiction can't be carried in
        memory until adjudicated. Missing-field questions never block."""
        return [q for q in self.questions if q.status == "open" and q.trigger == "contradiction"]

    def answer_question(self, qid: str, answer: str) -> Optional[a2a.ClarifyingQuestion]:
        with self._lock:
            for q in self.questions:
                if q.id == qid:
                    q.status = "answered"
                    q.answer = answer
                    self._save()
                    return q
        return None

    # ── the API view ────────────────────────────────────────────────────────────
    def status_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "connected": self.is_connected(),
                "grounded": self.is_grounded(),
                "ingest_status": self.ingest_status,
                "version": self.version,
                "org": dict(self.org),
                "connections": [c.as_dict() for c in self.connections],
                "open_questions": [q.as_dict() for q in self.open_questions()],
                "questions": [q.as_dict() for q in self.questions],
                "fact_count": len(self.all_facts()),
                "asset_count": self.asset_count(),
                "connected_day": self._day(),
            }

    def org_for_flywheel(self) -> dict:
        """The org dict the orchestrator/arivu consume — derived from the real
        connected project, never a canned default."""
        name = self.org.get("name") or "your company"
        return {
            "name": name,
            "kind": self.org.get("kind") or "the connected company",
            "memory_pack": self.version,
            "one_liner": self.org.get("one_liner", ""),
        }


# ── single shared store for the running service (key-by-user seam left clean) ──
_STORES: dict[str, ProjectStore] = {}
_STORES_LOCK = threading.Lock()


def _make_store(user: str):
    """Construct the backing store for a user.

    DEFAULT = the file-based ProjectStore (demo-first, creds-free, robust).
    OPT-IN  = Supabase, only when SAAKSHE_STORE=supabase AND a service key is
    configured (env SAAKSHE_SUPABASE_KEY or ~/.saakshe_supabase_key). This is
    additive: with no env set, behaviour is byte-identical to before, so the
    demo, pytest and isolated runs are unaffected. Any wiring/connectivity issue
    falls back to the file store rather than breaking the service.
    """
    if os.environ.get("SAAKSHE_STORE", "").strip().lower() == "supabase":
        try:
            from . import supastore
            if supastore.available():
                return supastore.SupabaseStore(user_id=user)
        except Exception:
            pass  # fall back to the file store
    return ProjectStore(user=user)


def store(user: str = "founder") -> ProjectStore:
    with _STORES_LOCK:
        s = _STORES.get(user)
        if s is None:
            s = _make_store(user)
            _STORES[user] = s
        return s


def store_for(user: str = "founder"):
    """The backing store for a user — Supabase when opted in (SAAKSHE_STORE=supabase
    + keys), else the file store. Cached per user; this is the multi-tenant factory
    the service calls once it has resolved the founder from the verified JWT."""
    return store(user)


STORE = store("founder")


# ── request-scoped store (the multi-tenant seam, made real) ───────────────────
# Library code — corpus, manas, kalai, kural, witness, the orchestrator — reads
# ``current_store()`` instead of the module global so a per-user store bound by the
# request flows through the WHOLE call graph (incl. the deep reads in corpus.py and
# manas.learn) without threading a ``store=`` param through a dozen functions.
# Unset (the default, and every one of the 135 demo tests) → the global file STORE,
# so demo behaviour is byte-identical. contextvars propagate across ``await``,
# ``asyncio.gather`` and ``asyncio.to_thread``, so the manas ingest threads inherit it.
_CURRENT_STORE: contextvars.ContextVar = contextvars.ContextVar("saakshe_current_store", default=None)


def current_store():
    """The store bound to the current request/context, else the global default."""
    return _CURRENT_STORE.get() or STORE


def set_current_store(s):
    """Bind ``s`` as the current store; returns a token to pass to
    :func:`reset_current_store` (use try/finally so a request never leaks its store)."""
    return _CURRENT_STORE.set(s)


def reset_current_store(token) -> None:
    _CURRENT_STORE.reset(token)

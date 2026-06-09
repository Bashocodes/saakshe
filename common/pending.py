"""saakshe.common.pending — manas live-edits persisted as IMMUTABLE pending changes.

When the founder asks manas to edit something (the company profile, a fact, a voice
rule), manas produces a STRUCTURED diff that is charged and written here as a
``pending_changes`` row with an immutable payload (old/new/diff) and a status
lifecycle: ``pending → applied | rejected | superseded``. saakshe does NOT execute
the change — this row IS the durable reminder for the later code-exec wired
elsewhere. The payload is never UPDATEd: a revision supersedes with a NEW row.

SECURITY/CORRECTNESS: every row is owner-scoped (user_id), idempotent on
``(user_id, idem_key)`` (a retried edit returns the same row, never a duplicate
charge), error text is capped, and soft-delete keeps the audit trail. apply/reject
only move a row that is still ``pending`` (a status filter in the patch), so a
double-apply or apply-after-reject is a no-op.

CLIENT: anything exposing the PostgREST trio ``_get/_insert/_patch`` — by default a
``supastore.SupabaseStore(user_id)`` (the service-role backend); in tests a fake.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

_ERR_CAP = 500  # cap stored error text so a stack trace can't bloat the row


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PendingChanges:
    """Owner-scoped store over the ``pending_changes`` table."""

    def __init__(self, user_id: str, client: Optional[Any] = None) -> None:
        self.user_id = user_id
        if client is not None:
            self.client = client
        else:  # import lazily so tests never construct the real (network) store
            from common import supastore

            self.client = supastore.SupabaseStore(user_id)

    def create(self, *, entity_type: str, old_json: dict, new_json: dict, diff_json: dict,
               changed_fields: list, idem_key: str, source_run_id: str = "",
               ai_model: str = "", cost_credits: int = 0, error_text: str = "") -> dict:
        """Write an immutable pending row. Idempotent on idem_key — a retry returns
        the SAME row (so the charge upstream is never duplicated)."""
        existing = self.client._get(
            "pending_changes", user_id=f"eq.{self.user_id}",
            idem_key=f"eq.{idem_key}", select="*", limit=1)
        if existing:
            return existing[0]
        return self.client._insert("pending_changes", {
            "user_id": self.user_id, "entity_type": entity_type,
            "old_json": old_json or {}, "new_json": new_json or {}, "diff_json": diff_json or {},
            "changed_fields": list(changed_fields or []), "source_run_id": source_run_id,
            "ai_model": ai_model, "cost_credits": int(cost_credits), "idem_key": idem_key,
            "error_text": (error_text or "")[:_ERR_CAP],
            "status": "pending", "review_status": "unreviewed", "deleted": False,
        })

    def get(self, pid: str) -> Optional[dict]:
        rows = self.client._get("pending_changes", user_id=f"eq.{self.user_id}",
                                id=f"eq.{pid}", select="*", limit=1)
        return rows[0] if rows else None

    def list_open(self) -> list[dict]:
        return self.client._get("pending_changes", user_id=f"eq.{self.user_id}",
                                status="eq.pending", deleted="eq.false",
                                select="*", order="created_at.desc")

    # ── lifecycle (NEVER touches the payload) ─────────────────────────────────
    def _move(self, pid: str, status: str, *, stamp_applied: bool = False) -> dict:
        patch: dict[str, Any] = {"status": status}
        if stamp_applied:
            patch["applied_at"] = _now_iso()
        # match on status='pending' → apply/reject only ever moves a live row once.
        return self.client._patch(
            "pending_changes",
            {"user_id": self.user_id, "id": pid, "status": "pending"}, patch)

    def apply(self, pid: str) -> dict:
        return self._move(pid, "applied", stamp_applied=True)

    def reject(self, pid: str) -> dict:
        return self._move(pid, "rejected")

    def supersede(self, pid: str) -> dict:
        """Retire a row in favour of a newer one — the payload is never edited."""
        return self._move(pid, "superseded")

    def soft_delete(self, pid: str) -> dict:
        return self.client._patch(
            "pending_changes", {"user_id": self.user_id, "id": pid}, {"deleted": True})

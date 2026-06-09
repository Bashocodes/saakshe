"""saakshe.tests.test_pending — the immutable pending-changes lifecycle.

A fake PostgREST client (lists + minimal 'eq.' matching) stands in for the store so
the immutability, idempotency, owner-scoping, status lifecycle and soft-delete are
exercised offline.
"""

from __future__ import annotations

import pytest

from common.pending import PendingChanges, _ERR_CAP


class FakeClient:
    def __init__(self) -> None:
        self.rows: list[dict] = []
        self._id = 0

    @staticmethod
    def _match(row, key, spec) -> bool:
        if isinstance(spec, str) and "." in spec:
            op, val = spec.split(".", 1)
            if op == "eq":
                return str(row.get(key)).lower() == val.lower()
            raise AssertionError(f"unsupported op {op}")
        return str(row.get(key)) == str(spec)

    def _get(self, table, **params):
        params.pop("select", None); params.pop("order", None)
        limit = params.pop("limit", None)
        out = [dict(r) for r in self.rows if all(self._match(r, k, v) for k, v in params.items())]
        return out[: int(limit)] if limit else out

    def _insert(self, table, row):
        self._id += 1
        stored = dict(row); stored["id"] = str(self._id); stored["created_at"] = self._id
        stored.setdefault("applied_at", None)
        self.rows.append(stored)
        return stored

    def _patch(self, table, match, patch):
        out = {}
        for r in self.rows:
            if all(str(r.get(k)) == str(v) for k, v in match.items()):
                r.update(patch); out = dict(r)
        return out


@pytest.fixture
def pc():
    return PendingChanges("u_alice", client=FakeClient())


def _make(pc, idem="e1", **kw):
    return pc.create(entity_type="company_profile", old_json={"tagline": "old"},
                     new_json={"tagline": "new"}, diff_json={"tagline": ["old", "new"]},
                     changed_fields=["tagline"], idem_key=idem, cost_credits=10,
                     ai_model="gemini-flash", source_run_id="run1", **kw)


def test_create_writes_immutable_pending_row(pc):
    row = _make(pc)
    assert row["status"] == "pending" and row["review_status"] == "unreviewed"
    assert row["deleted"] is False and row["cost_credits"] == 10
    assert row["old_json"] == {"tagline": "old"} and row["new_json"] == {"tagline": "new"}
    assert row["changed_fields"] == ["tagline"]


def test_create_is_idempotent_on_idem_key(pc):
    a = _make(pc, idem="dup")
    b = _make(pc, idem="dup")
    assert a["id"] == b["id"]                      # same row, no duplicate charge
    assert len(pc.client.rows) == 1


def test_error_text_is_capped(pc):
    row = _make(pc, idem="big", error_text="x" * 5000)
    assert len(row["error_text"]) == _ERR_CAP


def test_apply_moves_to_applied_and_stamps(pc):
    row = _make(pc)
    applied = pc.apply(row["id"])
    assert applied["status"] == "applied" and applied["applied_at"] is not None
    # payload untouched
    assert applied["old_json"] == {"tagline": "old"} and applied["new_json"] == {"tagline": "new"}


def test_reject_moves_to_rejected(pc):
    row = _make(pc)
    assert pc.reject(row["id"])["status"] == "rejected"


def test_apply_after_reject_is_noop(pc):
    row = _make(pc)
    pc.reject(row["id"])
    pc.apply(row["id"])                            # status no longer 'pending' → no move
    assert pc.get(row["id"])["status"] == "rejected"


def test_list_open_filters_pending_and_not_deleted(pc):
    a = _make(pc, idem="a")
    b = _make(pc, idem="b")
    pc.apply(a["id"])
    pc.soft_delete(b["id"])
    c = _make(pc, idem="c")
    assert [r["id"] for r in pc.list_open()] == [c["id"]]


def test_owner_scoped(pc):
    _make(pc, idem="mine")
    other = PendingChanges("u_bob", client=pc.client)   # shares the table
    assert other.list_open() == []                       # never sees u_alice's row
    assert other.get(pc.client.rows[0]["id"]) is None


def test_supersede_never_edits_payload(pc):
    row = _make(pc)
    superseded = pc.supersede(row["id"])
    assert superseded["status"] == "superseded"
    assert superseded["new_json"] == {"tagline": "new"}  # payload intact

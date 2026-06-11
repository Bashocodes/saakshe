"""The Brand Pack — aikizi-depth extraction schema invariants + the deep-grasp
flag + public-repo manners (no logo/ownership questions about a repo the
founder is merely exploring)."""
from __future__ import annotations

import importlib

from manas import doubts, grasp_schema


# ─── Schema invariants ───────────────────────────────────────────────────────
def test_at_least_120_leaf_fields():
    assert grasp_schema.field_count() >= 120, grasp_schema.field_count()


def test_keys_unique_and_shaped():
    fields = grasp_schema.all_fields()
    keys = [f["key"] for f in fields]
    assert len(set(keys)) == len(keys), "duplicate field keys"
    for f in fields:
        assert f["tier"] in (1, 2)
        assert f["kind"] in ("fact", "voice_rule", "brand_rule", "asset", "channel")
        assert f["ask"].strip().endswith("?")
        if f["kind"] != "asset":
            assert len(f["stems"]) >= 1, f["key"]


def test_empty_corpus_misses_every_tier1():
    missing = grasp_schema.missing_fields("", has_logo=False, tier=1)
    assert {f["key"] for f in missing} == {f["key"] for f in grasp_schema.tier1_fields()}


def test_stems_actually_cover():
    text = "We charge $10/mo for the Pro plan. Logo rules live in the brand kit."
    missing_keys = {f["key"] for f in grasp_schema.missing_fields(text, has_logo=True)}
    assert "price_points" not in missing_keys
    assert "logo_marks" not in missing_keys  # asset kind → has_logo covers it


def test_public_skips_owned_only_and_assets():
    missing = grasp_schema.missing_fields("", has_logo=False, owned=False)
    for f in missing:
        assert not f["owned_only"], f["key"]
        assert f["kind"] != "asset", f["key"]


def test_coverage_shape():
    cov = grasp_schema.coverage("", has_logo=False)
    assert set(cov) == {s["key"] for s in grasp_schema.SECTIONS}
    for sec in cov.values():
        assert 0 <= sec["covered"] <= sec["total"]


# ─── doubts wiring ───────────────────────────────────────────────────────────
def test_flag_off_is_classic_flow(monkeypatch):
    monkeypatch.delenv("SAAKSHE_DEEP_GRASP", raising=False)
    qs = doubts.detect([], [], [], has_logo_asset=False, max_questions=10)
    ids = {q.id for q in qs}
    # the classic four dimensions + the logo doubt, nothing schema-flavored
    assert len(qs) == 5
    assert any(q.trigger == "missing_asset" for q in qs)
    assert all("deep grasp" not in q.blocks for q in qs)
    # deterministic ids (hash of trigger+key)
    assert ids == {q.id for q in doubts.detect([], [], [], has_logo_asset=False, max_questions=10)}


def test_flag_on_uses_brand_pack(monkeypatch):
    monkeypatch.setenv("SAAKSHE_DEEP_GRASP", "1")
    qs = doubts.detect([], [], [], has_logo_asset=False, max_questions=4)
    assert len(qs) == 8  # capped, deeper than the classic 4
    assert all(q.trigger in ("missing_field", "missing_asset") for q in qs)
    assert any("deep grasp" in q.blocks for q in qs)
    again = doubts.detect([], [], [], has_logo_asset=False, max_questions=4)
    assert [q.id for q in qs] == [q.id for q in again]  # deterministic


def test_public_repo_never_asks_for_logo(monkeypatch):
    # The founder's rule: a public repository is not interrogated about brand
    # assets — classic flow AND deep flow.
    monkeypatch.delenv("SAAKSHE_DEEP_GRASP", raising=False)
    qs = doubts.detect([], [], [], has_logo_asset=False, max_questions=10, owned=False)
    assert not any(q.trigger == "missing_asset" for q in qs)

    monkeypatch.setenv("SAAKSHE_DEEP_GRASP", "1")
    qs = doubts.detect([], [], [], has_logo_asset=False, max_questions=10, owned=False)
    assert not any(q.trigger == "missing_asset" for q in qs)


def test_owned_still_gets_logo_doubt(monkeypatch):
    monkeypatch.delenv("SAAKSHE_DEEP_GRASP", raising=False)
    qs = doubts.detect([], [], [], has_logo_asset=False, max_questions=10, owned=True)
    assert any(q.trigger == "missing_asset" for q in qs)


def test_module_reimport_stays_pure():
    importlib.reload(grasp_schema)
    assert grasp_schema.field_count() >= 120

"""media_crew — router, pricer, receipt. All prices live in one module."""
import pytest

from kalai import media_crew as mc


def test_quote_compute_path_fits_dollar():
    q = mc.quote(seconds=8, budget_usd=1.0, has_source_image=True, wants_hdr=True)
    assert q["path"] == "B"  # source exists -> no generation needed
    assert q["total_usd"] < 0.10
    assert q["fits_budget"] is True
    assert q["rationale"]


def test_quote_chain_when_no_source():
    q = mc.quote(seconds=4, budget_usd=1.0, has_source_image=False, wants_hdr=True)
    assert q["path"] == "A->B"  # must generate a still first
    assert q["lines"][0]["item"] == "imagen_still"


def test_refusal_when_over_budget():
    q = mc.quote(seconds=8, budget_usd=0.001, has_source_image=True, wants_hdr=True)
    assert q["fits_budget"] is False
    assert q["counter_offer"] is None or q["counter_offer"]["seconds"] < 8


def test_counter_offer_picks_largest_fitting_duration():
    q = mc.quote(seconds=8, budget_usd=0.0015, has_source_image=True, wants_hdr=True)
    assert q["fits_budget"] is False
    co = q["counter_offer"]
    assert co is not None and co["total_usd"] <= 0.0015


def test_seconds_clamped_to_max():
    q = mc.quote(seconds=99, budget_usd=10.0, has_source_image=True, wants_hdr=True)
    assert q["seconds"] == mc.MAX_SECONDS


def test_receipt_reconciles_measured_seconds():
    q = mc.quote(seconds=2, budget_usd=1.0, has_source_image=True, wants_hdr=True)
    r = mc.receipt(q, measured_vcpu_sec=19.5, vertex_usd=0.0)
    assert r["cpu_usd"] == pytest.approx(19.5 * mc.CPU_USD_PER_VCPU_SEC)
    assert r["total_usd"] == pytest.approx(r["cpu_usd"])
    assert r["estimated_usd"] == q["total_usd"]

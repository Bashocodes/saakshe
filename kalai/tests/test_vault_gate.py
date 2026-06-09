# kalai/tests/test_vault_gate.py
"""The byte-identical gate: an empty served-asset list leaves kalai's prompt EXACTLY
as today; a non-empty list grounds the designer on the assets. This is what keeps the
264 baseline byte-identical while the vault is live."""
from __future__ import annotations

import inspect
from kalai import runner, sub_agents


def test_make_accepts_optional_assets_default_none():
    sig = inspect.signature(runner.make)
    assert "assets" in sig.parameters
    assert sig.parameters["assets"].default is None     # default → empty → today's behavior


def test_empty_assets_render_no_brand_block_change():
    # the designer's BRAND_BLOCK rendering is byte-identical for [] vs the pre-vault path
    empty = sub_agents.render_brand_block(assets=[])
    none_ = sub_agents.render_brand_block(assets=None)
    assert empty == none_ == ""                          # nothing served → nothing added


def test_nonempty_assets_appear_in_brand_block():
    block = sub_agents.render_brand_block(assets=[
        {"kind": "logo", "filename": "logo.png", "uri": "vault://abc", "provenance": "repo"}])
    assert "logo.png" in block and "logo" in block.lower()

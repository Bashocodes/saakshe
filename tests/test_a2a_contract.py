from common import a2a


def test_creative_master_carries_caption_and_media():
    m = a2a.CreativeMaster(
        asset_id="a1", brief="b", caption="the one caption kalai authored",
        formats={"x": "x", "ig": "ig", "linkedin": "li"},
        media={"image_ref": "vertex://imagen/placeholder", "video_ref": ""},
        fidelity_score=9.1, compliance="cleared", spend_usd=1.2,
    )
    d = m.as_dict()
    assert d["caption"] == "the one caption kalai authored"
    assert d["media"]["image_ref"].startswith("vertex://")
    assert set(d["formats"]) == {"x", "ig", "linkedin"}


def test_creative_master_defaults_keep_old_callers_working():
    m = a2a.CreativeMaster(asset_id="a1", brief="b")
    assert m.caption == "" and m.media == {}

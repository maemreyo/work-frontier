from scripts.check_setup_assets import assets_are_current


def test_packaged_setup_assets_match_frontend_source() -> None:
    assert assets_are_current()

from spoolmanscale_pro import settings


def test_scale_address_forms():
    clean, refused = settings.clean_update({"scale_address": " http://spoolmanscale.local/ "})
    assert clean == {"scale_address": "spoolmanscale.local"} and refused == []
    clean, _ = settings.clean_update({"scale_address": "192.168.4.37:80"})
    assert clean["scale_address"] == "192.168.4.37:80"
    clean, _ = settings.clean_update({"scale_address": ""})
    assert clean["scale_address"] == ""


def test_scale_address_refuses_anything_that_is_not_a_host():
    for bad in ("evil.com/path", "a b", "x" * 65, "host:port", "user@host"):
        _, refused = settings.clean_update({"scale_address": bad})
        assert refused == ["scale_address"], bad


def test_scale_password_is_four_to_eight_digits_or_empty():
    assert settings.clean_update({"scale_password": "1234"})[0] == {"scale_password": "1234"}
    assert settings.clean_update({"scale_password": ""})[0] == {"scale_password": ""}
    for bad in ("123", "123456789", "12ab"):
        assert settings.clean_update({"scale_password": bad})[1] == ["scale_password"]


def test_unknown_fields_are_ignored():
    assert settings.clean_update({"active_backend": "spoolman"}) == ({}, [])


def test_public_view_hides_the_scale_password():
    view = settings.public_view({**settings.DEFAULTS, "scale_password": "1234"})
    assert "scale_password" not in view and view["scale_password_set"] is True


def test_update_round_trip():
    settings.update({"scale_address": "scale.local"})
    assert settings.load()["scale_address"] == "scale.local"


def test_include_prereleases_must_be_a_real_boolean():
    assert settings.clean_update({"include_prereleases": True})[0] == {"include_prereleases": True}
    assert settings.clean_update({"include_prereleases": "yes"})[1] == ["include_prereleases"]


def test_backend_versions_cannot_be_set_through_the_settings_route():
    assert settings.clean_update({"backend_versions": {"spoolman": "latest"}}) == ({}, [])

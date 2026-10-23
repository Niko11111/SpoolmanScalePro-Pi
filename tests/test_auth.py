import secrets

from spoolmanscale_pro import auth


def test_verify_needs_name_and_password():
    salt = secrets.token_bytes(16)
    record = {"user": "Nikolai", "salt": salt.hex(), "hash": auth.hash_password("correct horse", salt)}
    assert auth.verify("Nikolai", "correct horse", record)
    assert auth.verify(" nikolai ", "correct horse", record)   # as a password manager may send it
    assert not auth.verify("admin", "correct horse", record)
    assert not auth.verify("Nikolai", "wrong horse", record)
    assert not auth.verify("x", "x", {"salt": "zz"})


def test_usernames():
    assert auth.clean_username("  admin ") == "admin"
    assert auth.clean_username("me@example.com") == "me@example.com"
    for bad in ("", "   ", None, "a\nb", "x" * 65):
        assert auth.clean_username(bad) is None, repr(bad)


def test_modes():
    assert auth.mode_of(None) == "unset"
    assert auth.mode_of({"open": True}) == "open"
    assert auth.mode_of({"user": "a", "salt": "00", "hash": "00"}) == "password"
    # A broken file is a locked door, never an open one.
    assert auth.mode_of({"broken": True}) == "password"


def test_password_length():
    assert not auth.password_acceptable("short")
    assert auth.password_acceptable("12345678")
    assert not auth.password_acceptable(None)


def test_origin_matches():
    assert auth.origin_matches(None, "pi.local")
    assert auth.origin_matches("http://pi.local", "pi.local")
    assert auth.origin_matches("http://192.168.4.1:8090", "192.168.4.1:8090")
    assert not auth.origin_matches("http://evil.example", "pi.local")
    assert not auth.origin_matches("null", "pi.local")

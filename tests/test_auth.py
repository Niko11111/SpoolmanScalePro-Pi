import secrets

from spoolmanscale_pro import auth


def test_hash_and_verify():
    salt = secrets.token_bytes(16)
    record = {"salt": salt.hex(), "hash": auth.hash_password("correct horse", salt)}
    assert auth.verify_password("correct horse", record)
    assert not auth.verify_password("wrong horse", record)
    assert not auth.verify_password("x", {"salt": "zz"})


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

from __future__ import annotations

from app.core.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    h = hash_password("hunter22-strong")
    assert h != "hunter22-strong"
    assert verify_password("hunter22-strong", h)
    assert not verify_password("nope", h)


def test_jwt_roundtrip():
    token = create_access_token(subject="abc-123", extra_claims={"foo": "bar"})
    payload = decode_token(token)
    assert payload["sub"] == "abc-123"
    assert payload["foo"] == "bar"
    assert payload["type"] == "access"

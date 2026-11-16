import jwt
import pytest

from app.core.security import (
    create_access_token, decode_access_token, hash_password, verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_token_roundtrip():
    token = create_access_token(43)
    assert decode_access_token(token)["sub"] == "42"


def test_tampered_token_is_rejected():
    token = create_access_token(42)
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token + "x")
"""Tests for app.core.security — JWT + password hashing."""

import sys
from datetime import timedelta

import pytest

from app.core.security import (
    create_access_token,
    decode_access_token,
)

# passlib+bcrypt is broken on Windows with Python 3.14 + bcrypt>=4.2
_bcrypt_broken = sys.platform == "win32"


class TestPasswordHashing:
    @pytest.mark.skipif(_bcrypt_broken, reason="passlib+bcrypt incompatible on Windows/Py3.14")
    def test_hash_and_verify(self):
        from app.core.security import hash_password, verify_password
        plain = "my-secret-password"
        hashed = hash_password(plain)
        assert hashed != plain
        assert verify_password(plain, hashed)

    @pytest.mark.skipif(_bcrypt_broken, reason="passlib+bcrypt incompatible on Windows/Py3.14")
    def test_wrong_password_fails(self):
        from app.core.security import hash_password, verify_password
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)


class TestJWT:
    def test_create_and_decode(self):
        token = create_access_token({"sub": 42})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "42"

    def test_custom_expiry(self):
        token = create_access_token({"sub": 1}, expires_delta=timedelta(seconds=5))
        payload = decode_access_token(token)
        assert payload is not None

    def test_invalid_token_returns_none(self):
        assert decode_access_token("garbage.token.here") is None

    def test_empty_token_returns_none(self):
        assert decode_access_token("") is None

    def test_expired_token_returns_none(self):
        token = create_access_token({"sub": 1}, expires_delta=timedelta(seconds=-10))
        assert decode_access_token(token) is None

    def test_payload_preserves_extra_claims(self):
        token = create_access_token({"sub": 1, "role": "admin"})
        payload = decode_access_token(token)
        assert payload["role"] == "admin"

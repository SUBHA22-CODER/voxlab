"""Tests for password hashing, JWT tokens, and credential encryption."""


from app.core.security import (
    create_access_token,
    decode_access_token,
    decrypt_credentials,
    encrypt_credentials,
    hash_password,
    verify_password,
)


class TestPasswords:
    def test_hash_and_verify_roundtrip(self):
        stored = hash_password("s3cret-password")
        assert stored != "s3cret-password"
        assert verify_password("s3cret-password", stored) is True

    def test_wrong_password_fails(self):
        stored = hash_password("s3cret-password")
        assert verify_password("wrong-password", stored) is False

    def test_salts_are_unique(self):
        assert hash_password("same") != hash_password("same")

    def test_corrupt_stored_hash_fails_cleanly(self):
        assert verify_password("x", "not-a-valid-hash") is False


class TestTokens:
    def test_token_roundtrip(self):
        token, _jti = create_access_token("42")
        assert decode_access_token(token) == "42"

    def test_garbage_token_is_rejected(self):
        assert decode_access_token("not.a.jwt") is None

    def test_tampered_token_is_rejected(self):
        token, _jti = create_access_token("42")
        assert decode_access_token(token + "x") is None


class TestCredentialEncryption:
    def test_roundtrip(self):
        blob = encrypt_credentials({"type": "bearer", "token": "sk-secret"})
        assert "sk-secret" not in blob
        assert decrypt_credentials(blob) == {"type": "bearer", "token": "sk-secret"}

    def test_none_passthrough(self):
        assert encrypt_credentials(None) is None
        assert decrypt_credentials(None) is None

    def test_empty_dict_passthrough(self):
        assert encrypt_credentials({}) is None

    def test_corrupt_blob_returns_none(self):
        assert decrypt_credentials("garbage-blob") is None

"""
Tests for core/security.py — encryption, hashing, HMAC tokens, masking.
"""

import pytest

from core.security import (
    build_card_payload,
    decrypt_payload,
    encrypt_payload,
    generate_api_token,
    generate_auth_code,
    hash_payload,
    mask_card,
    validate_api_key,
    validate_api_token,
)


class TestEncryption:
    def test_encrypt_returns_string(self):
        cipher = encrypt_payload("test data")
        assert isinstance(cipher, str)
        assert len(cipher) > 0

    def test_decrypt_round_trip(self):
        original = "card_last4=1234|card_type=VISA|terminal_id=T1"
        cipher = encrypt_payload(original)
        assert decrypt_payload(cipher) == original

    def test_encrypt_produces_different_ciphertexts(self):
        """Fernet adds a timestamp/nonce so the same plaintext gives different cipher-texts."""
        c1 = encrypt_payload("hello")
        c2 = encrypt_payload("hello")
        assert c1 != c2

    def test_decrypt_tampered_token_raises(self):
        with pytest.raises(ValueError, match="Invalid or tampered"):
            decrypt_payload("not-a-valid-fernet-token")


class TestHashing:
    def test_hash_is_hex_string(self):
        digest = hash_payload("some data")
        assert isinstance(digest, str)
        assert len(digest) == 64  # SHA-256 hex = 64 chars

    def test_same_input_same_hash(self):
        assert hash_payload("abc") == hash_payload("abc")

    def test_different_input_different_hash(self):
        assert hash_payload("abc") != hash_payload("def")


class TestHMACToken:
    def test_generated_token_is_valid(self):
        token = generate_api_token("client-123")
        assert validate_api_token(token)

    def test_tampered_token_is_invalid(self):
        token = generate_api_token("client-123")
        bad_token = token[:-1] + ("X" if token[-1] != "X" else "Y")
        assert not validate_api_token(bad_token)

    def test_token_without_dot_is_invalid(self):
        assert not validate_api_token("nodottoken")

    def test_empty_token_is_invalid(self):
        assert not validate_api_token("")


class TestApiKeyValidation:
    def test_correct_key_is_valid(self):
        from config.settings import get_settings
        settings = get_settings()
        assert validate_api_key(settings.API_KEY)

    def test_wrong_key_is_invalid(self):
        assert not validate_api_key("completely-wrong-key")


class TestCardMasking:
    def test_mask_replaces_leading_digits(self):
        assert mask_card("4111111111111234") == "****-****-****-1234"

    def test_mask_short_string_uses_tail(self):
        assert mask_card("1234") == "****-****-****-1234"

    def test_mask_preserves_last4(self):
        result = mask_card("9999888877776543")
        assert result.endswith("6543")


class TestAuthCode:
    def test_auth_code_length(self):
        code = generate_auth_code()
        assert len(code) == 6

    def test_auth_code_is_uppercase_hex(self):
        code = generate_auth_code()
        assert code == code.upper()
        int(code, 16)  # should not raise

    def test_auth_codes_are_unique(self):
        codes = {generate_auth_code() for _ in range(100)}
        assert len(codes) > 1  # extremely unlikely to collide


class TestBuildCardPayload:
    def test_payload_contains_all_fields(self):
        p = build_card_payload("1234", "VISA", "TERM-1")
        assert "card_last4=1234" in p
        assert "card_type=VISA" in p
        assert "terminal_id=TERM-1" in p

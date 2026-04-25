from __future__ import annotations

from decimal import Decimal

import pytest

from manifold.security.encryption import EncryptionService
from manifold.security.types import EncryptedJSON, EncryptedText


def test_encrypt_decrypt_bytes() -> None:
    enc = EncryptionService("test-secret-key")
    dek = enc.generate_dek()
    plaintext = b"hello world"

    ciphertext = enc.encrypt_bytes(plaintext, dek)

    assert ciphertext != plaintext
    assert enc.decrypt_bytes(ciphertext, dek) == plaintext


def test_encrypt_decrypt_text_with_type_decorator() -> None:
    enc = EncryptionService("test-secret-key")
    dek = enc.generate_dek()
    field = EncryptedText()

    with enc.user_dek_context(dek):
        encrypted = field.process_bind_param("secret text", None)
        assert encrypted != b"secret text"
        assert field.process_result_value(encrypted, None) == "secret text"


def test_encrypt_dek_round_trip() -> None:
    enc = EncryptionService("test-secret-key")
    dek = enc.generate_dek()

    encrypted = enc.encrypt_dek(dek)

    assert enc.decrypt_dek(encrypted) == dek


def test_jwt_signing_key_deterministic() -> None:
    enc1 = EncryptionService("same-key")
    enc2 = EncryptionService("same-key")

    assert enc1.jwt_signing_key == enc2.jwt_signing_key


def test_different_secret_different_key() -> None:
    enc1 = EncryptionService("key-a")
    enc2 = EncryptionService("key-b")

    assert enc1.dek_master_key != enc2.dek_master_key


def test_nonce_uniqueness() -> None:
    enc = EncryptionService("test-key")
    dek = enc.generate_dek()

    first = enc.encrypt_bytes(b"same", dek)
    second = enc.encrypt_bytes(b"same", dek)

    assert first != second


def test_context_var_missing_raises() -> None:
    enc = EncryptionService("test-key")

    with pytest.raises(RuntimeError, match="No encryption context set"):
        enc.dumps_json({"key": "value"})


def test_json_round_trip_in_context() -> None:
    enc = EncryptionService("test-key")
    dek = enc.generate_dek()
    payload = {"amount": "123.45", "items": [1, 2, 3]}

    with enc.user_dek_context(dek):
        encrypted = enc.dumps_json(payload)
        assert enc.loads_json(encrypted) == payload


def test_encrypted_json_type_round_trip() -> None:
    enc = EncryptionService("test-key")
    dek = enc.generate_dek()
    field = EncryptedJSON()
    payload = {"enabled": True, "threshold": 5}

    with enc.user_dek_context(dek):
        encrypted = field.process_bind_param(payload, None)
        assert isinstance(encrypted, bytes)
        assert field.process_result_value(encrypted, None) == payload


def test_decimal_round_trip_in_context() -> None:
    enc = EncryptionService("test-key")
    dek = enc.generate_dek()

    with enc.user_dek_context(dek):
        encrypted = enc.dump_decimal(Decimal("42.50"))
        assert enc.load_decimal(encrypted) == Decimal("42.50")

from __future__ import annotations

import base64
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from decimal import Decimal
from hashlib import sha256

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from manifold.config import settings

_current_dek: ContextVar[bytes | None] = ContextVar("current_dek", default=None)


class EncryptionService:
    def __init__(self, secret_key: str | None = None) -> None:
        self._secret_key = (secret_key or settings.secret_key).encode("utf-8")

    def _derive(self, info: bytes) -> bytes:
        hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info)
        return hkdf.derive(self._secret_key)

    @property
    def jwt_signing_key(self) -> bytes:
        return self._derive(b"manifold-jwt-signing")

    @property
    def dek_master_key(self) -> bytes:
        return self._derive(b"manifold-dek-master")

    def generate_dek(self) -> bytes:
        return os.urandom(32)

    def encrypt_dek(self, dek: bytes) -> bytes:
        return self.encrypt_bytes(dek, self.dek_master_key)

    def decrypt_dek(self, encrypted_dek: bytes) -> bytes:
        return self.decrypt_bytes(encrypted_dek, self.dek_master_key)

    def encrypt_bytes(self, value: bytes, key: bytes) -> bytes:
        nonce = os.urandom(12)
        ciphertext = AESGCM(key).encrypt(nonce, value, None)
        return nonce + ciphertext

    def decrypt_bytes(self, value: bytes, key: bytes) -> bytes:
        nonce, ciphertext = value[:12], value[12:]
        return AESGCM(key).decrypt(nonce, ciphertext, None)

    def encrypt_text(self, value: str, dek: bytes) -> bytes:
        return self.encrypt_bytes(value.encode("utf-8"), dek)

    def decrypt_text(self, value: bytes, dek: bytes) -> str:
        return self.decrypt_bytes(value, dek).decode("utf-8")

    def hash_token(self, token: str) -> str:
        return sha256(token.encode("utf-8")).hexdigest()

    @contextmanager
    def user_dek_context(self, dek: bytes) -> Iterator[None]:
        token: Token[bytes | None] = _current_dek.set(dek)
        try:
            yield
        finally:
            _current_dek.reset(token)

    def dumps_json(self, value: object) -> bytes:
        dek = _current_dek.get()
        if dek is None:
            raise RuntimeError("No encryption context set")
        return self.encrypt_text(json.dumps(value), dek)

    def loads_json(self, value: bytes) -> object:
        dek = _current_dek.get()
        if dek is None:
            raise RuntimeError("No encryption context set")
        return json.loads(self.decrypt_text(value, dek))

    def dump_decimal(self, value: Decimal) -> bytes:
        dek = _current_dek.get()
        if dek is None:
            raise RuntimeError("No encryption context set")
        return self.encrypt_text(str(value), dek)

    def load_decimal(self, value: bytes) -> Decimal:
        dek = _current_dek.get()
        if dek is None:
            raise RuntimeError("No encryption context set")
        return Decimal(self.decrypt_text(value, dek))

    def encode_token_payload(self, raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).decode("utf-8")

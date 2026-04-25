from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import LargeBinary, TypeDecorator

from manifold.security.encryption import EncryptionService, _current_dek


class _EncryptedBase(TypeDecorator[Any]):
    impl = LargeBinary
    cache_ok = True

    @staticmethod
    def _require_dek() -> bytes:
        dek = _current_dek.get()
        if dek is None:
            raise RuntimeError("No encryption context set")
        return dek


class EncryptedText(_EncryptedBase):
    def process_bind_param(self, value: str | None, _dialect: Any) -> bytes | None:
        if value is None:
            return None
        return EncryptionService().encrypt_text(value, self._require_dek())

    def process_result_value(self, value: bytes | None, _dialect: Any) -> str | None:
        if value is None:
            return None
        return EncryptionService().decrypt_text(value, self._require_dek())


class EncryptedJSON(_EncryptedBase):
    def process_bind_param(self, value: object | None, _dialect: Any) -> bytes | None:
        if value is None:
            return None
        self._require_dek()
        return EncryptionService().dumps_json(value)

    def process_result_value(self, value: bytes | None, _dialect: Any) -> object | None:
        if value is None:
            return None
        self._require_dek()
        return EncryptionService().loads_json(value)


class EncryptedDecimal(_EncryptedBase):
    def process_bind_param(self, value: Decimal | None, _dialect: Any) -> bytes | None:
        if value is None:
            return None
        self._require_dek()
        return EncryptionService().dump_decimal(value)

    def process_result_value(self, value: bytes | None, _dialect: Any) -> Decimal | None:
        if value is None:
            return None
        self._require_dek()
        return EncryptionService().load_decimal(value)

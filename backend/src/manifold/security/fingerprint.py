from __future__ import annotations

import hmac

from manifold.security.encryption import EncryptionService

# Info label used in HKDF derivation — must never change (changing it orphans all stored HMACs).
_HKDF_INFO = b"manifold-fingerprint"


def _derive_fingerprint_key(secret_key: str | None = None) -> bytes:
    """Derive a 32-byte key dedicated to identifier HMACs via HKDF.

    Uses the same HKDF primitive as the rest of EncryptionService so the
    fingerprint key is cryptographically independent from the DEK master key
    and the JWT signing key, yet anchored to the same application secret.
    """
    return EncryptionService(secret_key)._derive(_HKDF_INFO)


def compute_identifier_hmac(
    user_id: str,
    id_type: str,
    normalized_value: str,
    secret_key: str | None = None,
) -> str:
    """Return a 64-char hex HMAC-SHA256 for an account identifier.

    Preimage: ``user_id + ':' + id_type + ':' + normalized_value``

    Including ``user_id`` makes cross-user comparison impossible by construction.
    Including ``id_type`` prevents a SCAN value that happens to match an ABA
    shape from colliding even before the column filter applies.

    The key is derived via HKDF (info=``manifold-fingerprint``) from the
    application secret, never from a raw DEK.
    """
    key = _derive_fingerprint_key(secret_key)
    preimage = f"{user_id}:{id_type}:{normalized_value}".encode()
    digest = hmac.new(key, preimage, "sha256").hexdigest()
    return digest


__all__ = ["compute_identifier_hmac"]

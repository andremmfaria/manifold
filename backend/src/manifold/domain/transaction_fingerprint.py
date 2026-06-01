"""Transaction deduplication fingerprint helpers (Phase 5).

Two-tier dedup design:

  Tier 1 — identity-scoped provider id (always active when account.identity_id is set).
    HMAC(manifold-txn-dedup, identity_id + ':' + normalized_provider_transaction_id)
    provider_transaction_id is plaintext — no DEK needed.

  Tier 2 — content hash fallback (DISABLED BY DEFAULT; opt-in per identity pair).
    HMAC(manifold-txn-content, identity_id + ':' + amount + ':' + date + ':' + desc)
    Computed from decrypted values at sync time (DEK must be in context).
    Returns None when inputs are ineligible or DEK is absent — never silently hashes garbage.

HKDF label separation:
    'manifold-txn-dedup'    → Tier 1 key  (provider id hash)
    'manifold-txn-content'  → Tier 2 key  (content hash)

Both labels are application-level keys (not per-user DEK): the HMAC is what
makes the hash opaque; identity_id in the preimage provides user-scoped isolation.
"""

from __future__ import annotations

import hmac
import logging
import re
from decimal import Decimal

from manifold.security.encryption import EncryptionService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# HKDF-derived key cache — computed once per process per label.
# ---------------------------------------------------------------------------
_LABEL_TXN_DEDUP = b"manifold-txn-dedup"
_LABEL_TXN_CONTENT = b"manifold-txn-content"

_MIN_DESCRIPTION_LENGTH = 4   # reject descriptions shorter than this after normalization
_DESCRIPTION_TRUNCATE = 128   # truncate normalized description to this length

# Patterns stripped from the tail of a normalized description before hashing.
# These vary per bank and add no discriminating signal.
# Applied iteratively on the original-case string before lowercasing.
#
# Important: the reference-number pattern requires at least one digit so that
# plain English words (e.g. "LONDON") are not accidentally stripped.
_SUFFIX_PATTERNS = [
    # Trailing reference/token that MUST contain at least one digit (prevents
    # stripping plain merchant words like "LONDON" or "DIRECT").
    # Requires 6+ total chars with at least one digit: e.g. " REF123456", " TXN001234".
    re.compile(r"\s+[A-Z0-9]*\d[A-Z0-9]{5,}$"),
    # Trailing location codes: 1-3 uppercase letters followed by 1+ digits.
    # e.g. " E1", " GB1", " SW1A" — must end with digits to avoid stripping words.
    re.compile(r"\s+[A-Z]{1,3}\d+$"),
]


def _derive_key(label: bytes, secret_key: str | None = None) -> bytes:
    """Derive a 32-byte HMAC key via HKDF for the given label."""
    return EncryptionService(secret_key)._derive(label)


def _hmac_hex(key: bytes, preimage: str) -> str:
    """Return 64-char hex HMAC-SHA256 of *preimage* under *key*."""
    return hmac.new(key, preimage.encode(), "sha256").hexdigest()


# ---------------------------------------------------------------------------
# Description normalization (§4.3)
# ---------------------------------------------------------------------------


def normalize_description(raw: str | None) -> str | None:
    """Normalize a transaction description for content-hash dedup.

    Returns the normalized string, or None if the result is too short to be a
    meaningful discriminator (fewer than _MIN_DESCRIPTION_LENGTH characters).

    Steps:
    1. Strip leading/trailing whitespace.
    2. Collapse internal whitespace runs to a single space.
    3. Lowercase.
    4. Strip common merchant-suffix patterns (reference numbers, location codes).
    5. Truncate to _DESCRIPTION_TRUNCATE chars.
    6. Reject if result is blank or shorter than _MIN_DESCRIPTION_LENGTH.
    """
    if not raw:
        return None

    s = raw.strip()
    s = re.sub(r"\s+", " ", s)

    # Strip suffix patterns on the original-case string (patterns match uppercase).
    # Apply iteratively because stripping a ref number may expose a location code.
    for _ in range(3):
        prev = s
        for pattern in _SUFFIX_PATTERNS:
            s = pattern.sub("", s).strip()
        if s == prev:
            break

    s = s.lower()
    s = s[:_DESCRIPTION_TRUNCATE]
    s = s.strip()

    if len(s) < _MIN_DESCRIPTION_LENGTH:
        return None

    return s


# ---------------------------------------------------------------------------
# Tier 1 — identity-scoped provider id hash
# ---------------------------------------------------------------------------


def compute_tier1_hash(
    identity_id: str,
    provider_transaction_id: str,
    secret_key: str | None = None,
) -> str | None:
    """Compute the Tier 1 identity-scoped dedup hash.

    Returns a 64-char hex HMAC-SHA256, or None if either input is blank/null.

    No DEK required — provider_transaction_id is plaintext.

    Preimage: ``identity_id + ':' + normalized_provider_transaction_id``
    """
    if not identity_id or not provider_transaction_id:
        return None

    normalized_txn_id = provider_transaction_id.strip().lower()
    if not normalized_txn_id:
        return None

    key = _derive_key(_LABEL_TXN_DEDUP, secret_key)
    preimage = f"{identity_id}:{normalized_txn_id}"
    return _hmac_hex(key, preimage)


# ---------------------------------------------------------------------------
# Tier 2 — content hash fallback (opt-in; disabled by default)
# ---------------------------------------------------------------------------


def compute_content_hash(
    identity_id: str,
    amount: Decimal | None,
    transaction_date: str | None,
    description: str | None,
    secret_key: str | None = None,
) -> str | None:
    """Compute the Tier 2 content-hash fingerprint.

    Returns a 64-char hex HMAC-SHA256, or None if any required field is
    ineligible:
      - identity_id blank/null
      - amount None
      - transaction_date blank/null
      - normalized description is None (too short or blank after normalization)

    The caller must ensure the DEK context is active before calling — these
    values must already be decrypted (they are passed as Python objects, not
    ciphertext).  This function does NOT access the DEK itself; it operates
    on the already-decrypted plaintext values the caller provides.

    Preimage: ``identity_id + ':' + str(amount) + ':' + date + ':' + desc``

    HKDF label 'manifold-txn-content' is distinct from Tier 1's label so the
    two hash spaces are structurally disjoint even before the column separation.
    """
    if not identity_id:
        return None
    if amount is None:
        return None
    if not transaction_date or not transaction_date.strip():
        return None

    norm_desc = normalize_description(description)
    if norm_desc is None:
        return None

    # Normalize date: take only the date part (ISO 8601 YYYY-MM-DD) in case
    # the provider includes a time component.
    date_part = transaction_date.strip()[:10]

    key = _derive_key(_LABEL_TXN_CONTENT, secret_key)
    preimage = f"{identity_id}:{amount!s}:{date_part}:{norm_desc}"
    return _hmac_hex(key, preimage)


__all__ = [
    "normalize_description",
    "compute_tier1_hash",
    "compute_content_hash",
]

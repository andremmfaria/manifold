from __future__ import annotations

from hashlib import md5


def compute_dedup_hash(connection_id: str, provider_transaction_id: str) -> str:
    return md5(
        f"{connection_id}:{provider_transaction_id}".encode(),
        usedforsecurity=False,
    ).hexdigest()


def test_dedup_hash_deterministic() -> None:
    h1 = compute_dedup_hash("conn-001", "txn-001")
    h2 = compute_dedup_hash("conn-001", "txn-001")

    assert h1 == h2


def test_dedup_hash_different_connections() -> None:
    h1 = compute_dedup_hash("conn-001", "txn-001")
    h2 = compute_dedup_hash("conn-002", "txn-001")

    assert h1 != h2


def test_dedup_hash_different_transactions() -> None:
    h1 = compute_dedup_hash("conn-001", "txn-001")
    h2 = compute_dedup_hash("conn-001", "txn-002")

    assert h1 != h2


def test_dedup_hash_is_hex_string() -> None:
    h = compute_dedup_hash("conn-001", "txn-001")

    assert isinstance(h, str)
    assert len(h) == 32
    assert all(c in "0123456789abcdef" for c in h)

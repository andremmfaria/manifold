from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures" / "truelayer_responses"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_map_account_returns_account_data() -> None:
    from manifold.providers.truelayer.mappers import map_account

    raw = load_fixture("accounts.json")

    account = map_account(raw["results"][0])

    assert account.provider_account_id == "tl-account-001"
    assert account.currency == "GBP"
    assert account.account_type == "TRANSACTION"
    assert account.iban == "GB29NWBK60161331926819"


def test_map_account_preserves_display_name() -> None:
    from manifold.providers.truelayer.mappers import map_account

    raw = load_fixture("accounts.json")

    account = map_account(raw["results"][0])

    assert account.display_name == "Current Account"
    assert account.sort_code == "601613"
    assert account.account_number == "31926819"


def test_map_transaction_returns_transaction_data() -> None:
    from manifold.providers.truelayer.mappers import map_transaction

    raw = load_fixture("transactions.json")

    transaction = map_transaction(raw["results"][0])

    assert transaction.provider_transaction_id == "tl-txn-001"
    assert transaction.currency == "GBP"
    assert transaction.transaction_type == "debit"
    assert transaction.transaction_category == "ENTERTAINMENT"
    assert transaction.amount == Decimal("-9.99")
    assert transaction.transaction_date == "2025-01-15T12:00:00Z"


def test_map_transaction_pending_returns_pending_transaction_data() -> None:
    from manifold.providers.truelayer.mappers import map_transaction
    from manifold.providers.types import PendingTransactionData

    raw = load_fixture("transactions.json")

    transaction = map_transaction(raw["results"][0], pending=True)

    assert isinstance(transaction, PendingTransactionData)
    assert transaction.provider_transaction_id == "tl-txn-001"
    assert transaction.amount == Decimal("-9.99")
    assert transaction.currency == "GBP"

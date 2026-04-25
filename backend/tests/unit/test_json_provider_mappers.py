from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures" / "json_provider_responses"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_map_account_with_default_mapping() -> None:
    from manifold.providers.json_provider.mappers import map_account

    raw = load_fixture("manifold-canonical.json")

    account = map_account(raw["accounts"][0], {})

    assert account.provider_account_id == "json-acc-001"
    assert account.display_name == "Savings"
    assert account.currency == "GBP"
    assert account.account_type == "current"


def test_map_balance_with_default_mapping() -> None:
    from manifold.providers.json_provider.mappers import map_balance

    raw = load_fixture("manifold-canonical.json")

    balance = map_balance(raw["balances"][0], {"account_id": "account_id"})

    assert balance.account_id == "json-acc-001"
    assert balance.current == Decimal("1500.0")
    assert balance.available == Decimal("1500.0")
    assert balance.currency == "GBP"


def test_map_transaction_with_default_mapping() -> None:
    from manifold.providers.json_provider.mappers import map_transaction

    raw = load_fixture("manifold-canonical.json")

    transaction = map_transaction(raw["transactions"][0], {})

    assert transaction.provider_transaction_id == "json-txn-001"
    assert transaction.currency == "GBP"
    assert transaction.transaction_type == "debit"
    assert transaction.description == "Supermarket"
    assert transaction.transaction_date == "2025-01-20"
    assert transaction.amount == Decimal("-50.0")

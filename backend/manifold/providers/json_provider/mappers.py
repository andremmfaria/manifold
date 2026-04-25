from __future__ import annotations

from decimal import Decimal

from manifold.providers.types import AccountData, BalanceData, TransactionData


def _get(payload: dict, key: str, default=None):
    return payload.get(key, default)


def map_account(payload: dict, mapping: dict) -> AccountData:
    return AccountData(
        provider_account_id=str(_get(payload, mapping.get("account_id", "id"))),
        account_type=str(_get(payload, mapping.get("account_type", "type"), "current")),
        currency=str(_get(payload, mapping.get("currency", "currency"), "GBP")),
        display_name=_get(payload, mapping.get("display_name", "name")),
        iban=_get(payload, mapping.get("iban", "iban")),
        sort_code=_get(payload, mapping.get("sort_code", "sort_code")),
        account_number=_get(payload, mapping.get("account_number", "account_number")),
        raw_payload={},
    )


def map_balance(payload: dict, mapping: dict) -> BalanceData:
    current = _get(payload, mapping.get("balance", "balance"), _get(payload, "current"))
    return BalanceData(
        account_id=str(_get(payload, mapping.get("account_id", "id"))),
        available=Decimal(str(_get(payload, mapping.get("available", "available"), current)))
        if current is not None
        else None,
        current=Decimal(str(current)) if current is not None else None,
        currency=str(_get(payload, mapping.get("currency", "currency"), "GBP")),
        raw_payload={},
    )


def map_transaction(payload: dict, mapping: dict) -> TransactionData:
    amount = Decimal(str(_get(payload, mapping.get("amount", "amount"), 0)))
    return TransactionData(
        provider_transaction_id=str(
            _get(payload, mapping.get("transaction_id", "txn_id"), _get(payload, "id"))
        ),
        amount=amount,
        currency=str(_get(payload, mapping.get("currency", "currency"), "GBP")),
        transaction_type="credit" if amount >= 0 else "debit",
        description=_get(payload, mapping.get("description", "description")),
        transaction_date=str(
            _get(payload, mapping.get("date", "posted_at"), _get(payload, "date", ""))
        ),
        running_balance=Decimal(str(_get(payload, mapping.get("balance", "balance"))))
        if _get(payload, mapping.get("balance", "balance")) is not None
        else None,
        raw_payload=payload,
    )

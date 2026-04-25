from __future__ import annotations

from decimal import Decimal

from manifold.providers.types import (
    AccountData,
    BalanceData,
    CardData,
    DirectDebitData,
    PendingTransactionData,
    StandingOrderData,
    TransactionData,
)


def map_account(payload: dict) -> AccountData:
    account_number = payload.get("account_number") or {}
    return AccountData(
        provider_account_id=str(payload["account_id"]),
        account_type=str(payload.get("account_type") or "account"),
        currency=str(payload.get("currency") or "GBP"),
        display_name=payload.get("display_name"),
        iban=account_number.get("iban"),
        sort_code=account_number.get("sort_code"),
        account_number=account_number.get("number"),
        raw_payload=payload,
    )


def map_balance(account_id: str, payload: dict) -> BalanceData:
    return BalanceData(
        account_id=account_id,
        available=Decimal(str(payload.get("available")))
        if payload.get("available") is not None
        else None,
        current=Decimal(str(payload.get("current")))
        if payload.get("current") is not None
        else None,
        currency=str(payload.get("currency") or "GBP"),
        overdraft=Decimal(str(payload.get("overdraft")))
        if payload.get("overdraft") is not None
        else None,
        credit_limit=Decimal(str(payload.get("credit_limit")))
        if payload.get("credit_limit") is not None
        else None,
        raw_payload=payload,
    )


def map_transaction(
    payload: dict, *, pending: bool = False
) -> TransactionData | PendingTransactionData:
    amount = Decimal(str(payload.get("amount") or 0))
    if pending:
        return PendingTransactionData(
            provider_transaction_id=payload.get("transaction_id"),
            amount=amount,
            currency=payload.get("currency"),
            description=payload.get("description"),
            merchant_name=payload.get("merchant_name"),
            transaction_date=payload.get("timestamp"),
            raw_payload=payload,
        )
    return TransactionData(
        provider_transaction_id=str(payload["transaction_id"]),
        amount=amount,
        currency=str(payload.get("currency") or "GBP"),
        transaction_type="credit" if amount >= 0 else "debit",
        transaction_category=payload.get("transaction_category"),
        description=payload.get("description"),
        merchant_name=payload.get("merchant_name"),
        merchant_category=payload.get("merchant_category"),
        transaction_date=str(payload.get("timestamp") or ""),
        settled_date=payload.get("update_timestamp"),
        running_balance=Decimal(str(payload.get("running_balance")))
        if payload.get("running_balance") is not None
        else None,
        raw_payload=payload,
    )


def map_card(payload: dict) -> CardData:
    return CardData(
        provider_card_id=str(payload["account_id"]),
        display_name=payload.get("display_name"),
        card_network=payload.get("card_network"),
        partial_card_number=payload.get("partial_card_number"),
        currency=payload.get("currency"),
        credit_limit=Decimal(str(payload.get("credit_limit")))
        if payload.get("credit_limit") is not None
        else None,
        raw_payload=payload,
    )


def map_direct_debit(payload: dict) -> DirectDebitData:
    return DirectDebitData(
        provider_mandate_id=payload.get("mandate_id"),
        name=str(payload.get("name") or payload.get("merchant_name") or "Direct debit"),
        status=payload.get("status"),
        amount=Decimal(str(payload.get("previous_payment_amount")))
        if payload.get("previous_payment_amount") is not None
        else None,
        currency=payload.get("currency"),
        frequency=payload.get("frequency"),
        reference=payload.get("reference"),
        last_payment_date=payload.get("previous_payment_timestamp"),
        next_payment_date=payload.get("next_payment_date"),
        next_payment_amount=Decimal(str(payload.get("next_payment_amount")))
        if payload.get("next_payment_amount") is not None
        else None,
        raw_payload=payload,
    )


def map_standing_order(payload: dict) -> StandingOrderData:
    return StandingOrderData(
        provider_standing_order_id=payload.get("standing_order_id"),
        reference=payload.get("reference"),
        status=payload.get("status"),
        currency=payload.get("currency"),
        frequency=payload.get("frequency"),
        first_payment_date=payload.get("first_payment_date"),
        first_payment_amount=Decimal(str(payload.get("first_payment_amount")))
        if payload.get("first_payment_amount") is not None
        else None,
        next_payment_date=payload.get("next_payment_date"),
        next_payment_amount=Decimal(str(payload.get("next_payment_amount")))
        if payload.get("next_payment_amount") is not None
        else None,
        final_payment_date=payload.get("final_payment_date"),
        final_payment_amount=Decimal(str(payload.get("final_payment_amount")))
        if payload.get("final_payment_amount") is not None
        else None,
        previous_payment_date=payload.get("previous_payment_date"),
        previous_payment_amount=Decimal(str(payload.get("previous_payment_amount")))
        if payload.get("previous_payment_amount") is not None
        else None,
        raw_payload=payload,
    )

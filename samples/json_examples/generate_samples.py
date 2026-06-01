#!/usr/bin/env python3
"""Generate bogus JSON fixture files for testing Manifold's JSON file connection provider.

Each file conforms to the schema consumed by
``manifold.providers.json_provider.adapter.JsonProvider`` (adapter.py + mappers.py):
  - ``accounts[]``     – id, type, currency, name, iban, sort_code, account_number
  - ``balances[]``     – id, balance, available, currency  (id matches account id)
  - ``transactions[]`` – txn_id, account_id, amount, currency, description,
                         posted_at, balance

Usage:
    python samples/generate_samples.py
    python samples/generate_samples.py --seed 42 --out-dir /tmp/manifold-fixtures
    python samples/generate_samples.py --help
"""

from __future__ import annotations

import argparse
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Data pools
# ---------------------------------------------------------------------------

ACCOUNT_TYPES = ["current", "savings", "credit"]

CURRENCIES = ["GBP", "EUR", "USD", "CHF", "JPY"]

SORT_CODES = ["60-16-13", "20-00-00", "30-99-99", "40-47-84", "77-66-55"]

SALARY_DESCS = [
    "SALARY PAYMENT - {company}",
    "BACS CREDIT {company}",
    "WAGES {company}",
    "{company} PAYROLL",
]

COMPANIES = [
    "ACME LTD", "GLOBAL FINTECH LTD", "NOVA CAPITAL INC", "HARTLEY SOLUTIONS LTD",
    "MERIDIAN GROUP PLC", "BRENTWOOD RETAIL LTD", "KEYSTONE PROPERTY",
    "OAKFIELD TRADING LTD", "PINNACLE TECH", "VERTEX SYSTEMS",
]

MERCHANTS = [
    "TESCO STORES 3914", "SAINSBURYS SUPERMARKETS", "WAITROSE 0412",
    "LIDL SUPERMARKT", "ALDI STORES UK", "MARKS & SPENCER",
    "AMAZON UK MARKETPLACE", "AMAZON PRIME MEMBERSHIP", "NETFLIX.COM",
    "SPOTIFY AB", "APPLE ONE SUBSCRIPTION", "GOOGLE ONE STORAGE",
    "BRITISH GAS ENERGY", "EDF ENERGY PAYMENTS", "THAMES WATER",
    "TFL TRAVEL CHARGE", "NATIONAL RAIL TICKETS", "TRAINLINE.COM",
    "SHELL FORECOURT 0421", "BP FUEL STATION", "COSTA COFFEE",
    "PRET A MANGER", "WAHACA RESTAURANT LONDON", "DISHOOM LONDON",
    "BOOTS PHARMACY 0047", "SPECSAVERS OPTICIANS", "SUPERDRUG STORES",
    "IKEA LIMITED", "JOHN LEWIS PLC", "ARGOS LIMITED",
    "ATM WITHDRAWAL LLOYDS 00241", "ATM WITHDRAWAL BARCLAYS 1042",
    "AWS CLOUD SERVICES", "GITHUB ENTERPRISE ANNUAL", "DIGITALOCEAN LLC",
    # Unicode / international merchants for edge-case variety
    "MÜLLER BÄCKEREI GMBH", "CAFÉ LE MARCHÉ PARIS", "東京 CONVENIENCE 東京",
    "SØREN'S FISK & CHIPS", "NAÏVE CAFÉ & CRÊPERIE",
]

DIRECT_DEBIT_DESCS = [
    "DD COUNCIL TAX REF {ref}",
    "DIRECTDEBIT {company}",
    "RECURRING PMT {company}",
    "INSURANCE PREMIUM {company}",
    "MORTGAGE PMT REF {ref}",
]

CREDIT_PAYMENT_DESCS = [
    "PAYMENT RECEIVED - THANK YOU",
    "CREDIT CARD PAYMENT",
    "BALANCE PAYMENT",
]

TRANSFER_DESCS = [
    "TRANSFER TO SAVINGS",
    "TRANSFER FROM CURRENT",
    "INTERNAL TRANSFER REF {ref}",
    "FX TRANSFER TO EUR ACCOUNT",
    "FX TRANSFER TO USD ACCOUNT",
]

INTEREST_DESCS = [
    "INTEREST PAYMENT",
    "SAVINGS INTEREST APR",
    "CREDIT INTEREST",
]

TAX_DESCS = [
    "HMRC TAX REFUND",
    "VAT PAYMENT HMRC",
    "CORPORATION TAX INSTALMENT HMRC",
    "PAYE TAX REF {ref}",
]


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _rnd_account_number(rng: random.Random) -> str:
    return str(rng.randint(10_000_000, 99_999_999))


def _rnd_iban(sort_code: str, acct: str) -> str:
    digits = sort_code.replace("-", "") + acct
    return f"GB{digits[:2]}MANI{digits}"


def _rnd_amount(rng: random.Random, is_debit: bool, scale: float = 1.0) -> float:
    """Return a signed float; debit < 0, credit > 0."""
    base = round(rng.uniform(1.0, 2000.0) * scale, 2)
    return -base if is_debit else base


def _fmt_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _pick(rng: random.Random, lst: list):
    return lst[rng.randrange(len(lst))]


def _fill(template: str, rng: random.Random) -> str:
    ref = str(rng.randint(100000, 999999))
    company = _pick(rng, COMPANIES)
    return template.format(ref=ref, company=company)


# ---------------------------------------------------------------------------
# Account / balance / transaction generators
# ---------------------------------------------------------------------------

def _make_account(idx: int, acc_type: str, currency: str, rng: random.Random) -> dict:
    acct_num = _rnd_account_number(rng)
    sort_code = _pick(rng, SORT_CODES)
    has_iban = acc_type != "credit" and currency in {"GBP", "EUR"}
    return {
        "id": f"acc-{acc_type[:3]}-{idx:04d}",
        "type": acc_type,
        "currency": currency,
        "name": f"{_pick(rng, COMPANIES)} {acc_type.title()} {idx}",
        "iban": _rnd_iban(sort_code, acct_num) if has_iban else None,
        "sort_code": sort_code if has_iban else None,
        "account_number": acct_num,
    }


def _make_balance(account: dict, balance: float) -> dict:
    available = round(balance * random.uniform(0.85, 1.0), 2) if balance > 0 else balance
    return {
        "id": account["id"],
        "balance": round(balance, 2),
        "available": round(available, 2),
        "currency": account["currency"],
    }


def _make_transactions(
    account: dict,
    count: int,
    start_date: datetime,
    end_date: datetime,
    rng: random.Random,
    txn_counter: list,  # mutable counter shared across accounts
) -> tuple[list[dict], float]:
    """Return (transactions, final_running_balance)."""
    transactions = []
    running = 0.0
    acc_type = account["type"]

    for _ in range(count):
        txn_counter[0] += 1
        n = txn_counter[0]

        # Spread dates uniformly across the range
        span_seconds = int((end_date - start_date).total_seconds())
        offset = rng.randint(0, max(span_seconds, 1))
        posted = start_date + timedelta(seconds=offset)

        # Decide what kind of transaction
        roll = rng.random()
        if acc_type == "savings":
            if roll < 0.6:
                # transfer in
                desc = _fill(_pick(rng, TRANSFER_DESCS), rng)
                amount = _rnd_amount(rng, is_debit=False, scale=0.5)
            elif roll < 0.85:
                # interest
                desc = _pick(rng, INTEREST_DESCS)
                amount = round(rng.uniform(0.01, 150.0), 2)
            else:
                # withdrawal
                desc = _fill(_pick(rng, TRANSFER_DESCS), rng)
                amount = _rnd_amount(rng, is_debit=True, scale=0.3)
        elif acc_type == "credit":
            if roll < 0.7:
                desc = _fill(_pick(rng, MERCHANTS), rng)
                amount = _rnd_amount(rng, is_debit=True, scale=0.3)
            elif roll < 0.85:
                desc = _pick(rng, CREDIT_PAYMENT_DESCS)
                amount = _rnd_amount(rng, is_debit=False, scale=0.4)
            else:
                desc = _fill(_pick(rng, DIRECT_DEBIT_DESCS), rng)
                amount = _rnd_amount(rng, is_debit=True, scale=0.2)
        else:  # current / checking
            if roll < 0.15:
                # salary credit
                desc = _fill(_pick(rng, SALARY_DESCS), rng)
                amount = round(rng.uniform(1500.0, 8000.0), 2)
            elif roll < 0.25:
                desc = _fill(_pick(rng, TAX_DESCS), rng)
                amount = _rnd_amount(rng, is_debit=rng.random() < 0.4)
            elif roll < 0.45:
                desc = _fill(_pick(rng, DIRECT_DEBIT_DESCS), rng)
                amount = _rnd_amount(rng, is_debit=True, scale=0.4)
            elif roll < 0.6:
                desc = _fill(_pick(rng, TRANSFER_DESCS), rng)
                amount = _rnd_amount(rng, is_debit=rng.random() < 0.5, scale=0.3)
            else:
                desc = _fill(_pick(rng, MERCHANTS), rng)
                amount = _rnd_amount(rng, is_debit=True, scale=0.2)

        running = round(running + amount, 2)
        transactions.append({
            "txn_id": f"txn-{n:06d}",
            "account_id": account["id"],
            "amount": amount,
            "currency": account["currency"],
            "description": desc,
            "posted_at": _fmt_date(posted),
            "balance": running,
        })

    # Sort chronologically so the file looks natural
    transactions.sort(key=lambda t: t["posted_at"])
    return transactions, running


# ---------------------------------------------------------------------------
# File-level builders
# ---------------------------------------------------------------------------

def _build_dataset(
    rng: random.Random,
    num_accounts: int,
    txns_per_account: int,
    account_type_mix: list[str] | None = None,
    currency_mix: list[str] | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> dict:
    if account_type_mix is None:
        account_type_mix = ACCOUNT_TYPES
    if currency_mix is None:
        currency_mix = ["GBP"]
    if end_date is None:
        end_date = datetime(2026, 5, 31, 23, 59, 59, tzinfo=timezone.utc)
    if start_date is None:
        start_date = end_date - timedelta(days=365)

    accounts = []
    for i in range(num_accounts):
        acc_type = _pick(rng, account_type_mix)
        currency = _pick(rng, currency_mix)
        accounts.append(_make_account(i + 1, acc_type, currency, rng))

    txn_counter = [0]
    all_transactions = []
    balances = []

    for account in accounts:
        txns, final_balance = _make_transactions(
            account, txns_per_account, start_date, end_date, rng, txn_counter
        )
        all_transactions.extend(txns)
        balances.append(_make_balance(account, final_balance))

    return {
        "accounts": accounts,
        "balances": balances,
        "transactions": all_transactions,
    }


def _build_edge_cases(rng: random.Random) -> dict:
    """File targeting parser edge cases: zero amounts, null optionals, unicode, extremes."""
    now = datetime(2026, 5, 31, tzinfo=timezone.utc)
    old_date = datetime(2000, 1, 1, tzinfo=timezone.utc)

    accounts = [
        # No IBAN / sort_code (credit-style)
        {
            "id": "edge-credit-001",
            "type": "credit",
            "currency": "GBP",
            "name": "No-IBAN Credit Card",
            "iban": None,
            "sort_code": None,
            "account_number": "00000001",
        },
        # Non-ASCII name
        {
            "id": "edge-cur-002",
            "type": "current",
            "currency": "EUR",
            "name": "Ñoño Café & Crêperie Account",
            "iban": "GB29MANI60161300000002",
            "sort_code": "60-16-13",
            "account_number": "00000002",
        },
        # JPY (no decimals in practice, but parser uses Decimal so it's fine)
        {
            "id": "edge-jpy-003",
            "type": "savings",
            "currency": "JPY",
            "name": "日本円 Savings 口座",
            "iban": None,
            "sort_code": None,
            "account_number": "00000003",
        },
    ]

    balances = [
        {"id": "edge-credit-001", "balance": 0.0, "available": 5000.0, "currency": "GBP"},
        {"id": "edge-cur-002", "balance": -0.01, "available": -0.01, "currency": "EUR"},
        {"id": "edge-jpy-003", "balance": 100000, "available": 100000, "currency": "JPY"},
    ]

    transactions = [
        # Zero-amount (e.g. fee reversal)
        {
            "txn_id": "edge-txn-000001",
            "account_id": "edge-credit-001",
            "amount": 0.0,
            "currency": "GBP",
            "description": "FEE REVERSAL - ZERO AMOUNT",
            "posted_at": _fmt_date(now - timedelta(days=10)),
            "balance": 0.0,
        },
        # Very old date
        {
            "txn_id": "edge-txn-000002",
            "account_id": "edge-cur-002",
            "amount": 999.99,
            "currency": "EUR",
            "description": "OPENING BALANCE CIRCA Y2K",
            "posted_at": _fmt_date(old_date),
            "balance": 999.99,
        },
        # Very recent (today)
        {
            "txn_id": "edge-txn-000003",
            "account_id": "edge-cur-002",
            "amount": -1000.0,
            "currency": "EUR",
            "description": "CAFÉ LE MARCHÉ PARIS — unicode & special chars: <>&\"'",
            "posted_at": _fmt_date(now),
            "balance": -0.01,
        },
        # Large JPY amount
        {
            "txn_id": "edge-txn-000004",
            "account_id": "edge-jpy-003",
            "amount": 100000,
            "currency": "JPY",
            "description": "東京 CONVENIENCE 東京 — deposit",
            "posted_at": _fmt_date(now - timedelta(days=1)),
            "balance": 100000,
        },
        # Minimal description (single char)
        {
            "txn_id": "edge-txn-000005",
            "account_id": "edge-credit-001",
            "amount": -1.0,
            "currency": "GBP",
            "description": "X",
            "posted_at": _fmt_date(now - timedelta(days=5)),
            "balance": -1.0,
        },
        # Very large credit
        {
            "txn_id": "edge-txn-000006",
            "account_id": "edge-credit-001",
            "amount": 1.0,
            "currency": "GBP",
            "description": "SMALL CREDIT TO CLEAR BALANCE",
            "posted_at": _fmt_date(now - timedelta(days=3)),
            "balance": 0.0,
        },
        # Recurring direct-debit pattern (same desc, multiple dates)
        *[
            {
                "txn_id": f"edge-txn-dd-{i:04d}",
                "account_id": "edge-cur-002",
                "amount": -12.99,
                "currency": "EUR",
                "description": "DD STREAMING SERVICE REF 654321",
                "posted_at": _fmt_date(
                    datetime(2025, m, 1, 3, 0, 0, tzinfo=timezone.utc)
                ),
                "balance": round(999.99 - (12.99 * i), 2),
            }
            for i, m in enumerate(range(1, 13), start=1)
        ],
    ]

    return {
        "accounts": accounts,
        "balances": balances,
        "transactions": transactions,
    }


def _build_empty() -> dict:
    """Completely empty dataset — tests graceful handling of no data."""
    return {"accounts": [], "balances": [], "transactions": []}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

PROFILES: dict[str, dict] = {
    "tiny": dict(num_accounts=2, txns_per_account=5),
    "small": dict(num_accounts=3, txns_per_account=30),
    "medium": dict(
        num_accounts=5,
        txns_per_account=200,
        account_type_mix=ACCOUNT_TYPES,
        currency_mix=["GBP", "EUR", "USD"],
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 5, 31, tzinfo=timezone.utc),
    ),
    "large": dict(
        num_accounts=10,
        txns_per_account=500,
        account_type_mix=ACCOUNT_TYPES,
        currency_mix=["GBP", "EUR", "USD", "CHF"],
        start_date=datetime(2022, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2026, 5, 31, tzinfo=timezone.utc),
    ),
}


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _summary(path: Path, data: dict) -> str:
    size_kb = path.stat().st_size / 1024
    n_acc = len(data.get("accounts", []))
    n_txn = len(data.get("transactions", []))
    return f"  {path.name:<22}  {size_kb:>8.1f} KB   {n_acc:>4} accounts   {n_txn:>6} transactions"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate bogus JSON fixture files for Manifold's JSON file provider.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--seed", type=int, default=1337, help="Random seed for reproducibility (default: 1337)"
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).parent / "generated",
        help="Output directory (default: samples/generated/)",
    )
    args = parser.parse_args()

    out_dir: Path = args.out_dir
    seed: int = args.seed

    print(f"Generating samples → {out_dir}  (seed={seed})")
    print()

    results: list[str] = []

    # Standard size profiles
    for name, profile in PROFILES.items():
        rng = random.Random(seed)
        data = _build_dataset(rng, **profile)
        path = out_dir / f"{name}.json"
        _write(path, data)
        results.append(_summary(path, data))

    # Edge cases
    rng = random.Random(seed + 1)
    ec_data = _build_edge_cases(rng)
    ec_path = out_dir / "edge_cases.json"
    _write(ec_path, ec_data)
    results.append(_summary(ec_path, ec_data))

    # Empty dataset
    empty_data = _build_empty()
    empty_path = out_dir / "empty.json"
    _write(empty_path, empty_data)
    results.append(_summary(empty_path, empty_data))

    print(f"  {'File':<22}  {'Size':>9}   {'Accounts':>8}   {'Transactions':>13}")
    print("  " + "-" * 68)
    for line in results:
        print(line)
    print()
    print("Done.")


if __name__ == "__main__":
    main()

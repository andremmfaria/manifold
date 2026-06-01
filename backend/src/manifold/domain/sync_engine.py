from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.config import settings
from manifold.database import db_session
from manifold.models.account import Account
from manifold.models.balance import Balance
from manifold.models.card import Card
from manifold.models.direct_debit import DirectDebit
from manifold.models.event import Event
from manifold.models.pending_transaction import PendingTransaction
from manifold.models.provider_connection import ProviderConnection
from manifold.models.standing_order import StandingOrder
from manifold.models.sync_run import SyncRun
from manifold.models.transaction import Transaction
from manifold.models.user import User
from manifold.providers import ProviderAuthError, ProviderRateLimitError, SyncError, registry
from manifold.providers.registry import register_all
from manifold.providers.types import ProviderConnectionContext
from manifold.security.encryption import EncryptionService
from manifold.tasks._locks import acquire_lock, release_lock

from ._upsert import insert_row, upsert_and_fetch
from .account_identity import extract_identifiers, resolve_account_identity
from .sync_schedule import interval_to_minutes
from .transaction_fingerprint import compute_content_hash, compute_tier1_hash

logger = logging.getLogger(__name__)


class SyncEngine:
    def __init__(self, session: AsyncSession | None = None) -> None:
        register_all()
        self._session = session

    async def sync_connection(
        self, connection: ProviderConnection, existing_run_id: str | None = None
    ) -> SyncRun:
        if self._session is None:
            raise RuntimeError("SyncEngine requires bound session")
        session = self._session
        owner = await session.get(User, str(connection.user_id))
        if owner is None:
            raise RuntimeError("owner missing")
        dek = EncryptionService().decrypt_dek(owner.encrypted_dek)
        with EncryptionService().user_dek_context(dek):
            run = await self._adopt_or_create_run(session, connection, existing_run_id)
            run.started_at = datetime.now(UTC)
            run.status = "running"
            await session.flush()
            try:
                provider = registry.get(connection.provider_type)
                context = ProviderConnectionContext(
                    id=str(connection.id),
                    user_id=str(connection.user_id),
                    provider_type=connection.provider_type,
                    credentials=dict(connection.credentials_encrypted or {}),
                    config=dict(connection.config or {}),
                )
                refreshed = await provider.refresh_if_needed(context)
                if refreshed != context.credentials:
                    connection.credentials_encrypted = refreshed
                    context.credentials = refreshed
                accounts = await provider.get_accounts(context)
                balances = await provider.get_balances(context, accounts)
                cards = await provider.get_cards(context) if provider.supports_cards else []
                account_rows = await self._sync_accounts(session, connection, accounts)
                await self._sync_balances(session, account_rows, balances)
                await self._sync_cards(session, connection, account_rows, cards)
                tx_count = 0
                new_tx = 0
                for account_data in accounts:
                    account = account_rows[account_data.provider_account_id]
                    transactions = await provider.get_transactions(context, account_data)
                    inserted = await self._sync_transactions(
                        session,
                        connection_id=str(connection.id),
                        account=account,
                        transactions=transactions,
                    )
                    tx_count += len(transactions)
                    new_tx += inserted
                    await self._sync_pending(provider, context, account, account_data)
                    await self._sync_direct_debits(provider, context, account, account_data)
                    await self._sync_standing_orders(provider, context, account, account_data)
                connection.last_sync_at = datetime.now(UTC)
                connection.status = "active"
                connection.auth_status = "connected"
                if context.credentials.get("expires_at"):
                    connection.consent_expires_at = datetime.fromisoformat(
                        str(context.credentials["expires_at"]).replace("Z", "+00:00")
                    )
                run.accounts_synced = len(account_rows)
                run.transactions_synced = tx_count
                run.new_transactions = new_tx
                run.status = "success"
                await session.commit()
                return run
            except ProviderAuthError as exc:
                connection.auth_status = "refresh_failed"
                connection.status = "error"
                await self._fail_run(session, run, exc)
                return run
            except ProviderRateLimitError as exc:
                await self._fail_run(session, run, exc)
                return run
            except SyncError as exc:
                if connection.consent_expires_at and connection.consent_expires_at <= datetime.now(
                    UTC
                ):
                    connection.auth_status = "consent_expired"
                    connection.status = "expired"
                else:
                    connection.status = "error"
                await self._fail_run(session, run, exc)
                return run

    async def sync_connection_by_id(
        self, connection_id: str, existing_run_id: str | None = None
    ) -> SyncRun:
        if self._session is None:
            raise RuntimeError("SyncEngine requires bound session")
        connection = await self._load_connection_for_owner_context(
            self._session,
            connection_id,
        )
        return await self.sync_connection(connection, existing_run_id)

    async def sync_all_active(self) -> list[SyncRun]:
        runs: list[SyncRun] = []
        async with db_session() as session:
            result = await session.execute(
                select(
                    ProviderConnection.__table__.c.id,
                    ProviderConnection.__table__.c.user_id,
                    ProviderConnection.__table__.c.last_sync_at,
                ).where(ProviderConnection.__table__.c.status.in_(["active", "inactive"]))
            )
            engine = SyncEngine(session)
            now = datetime.now(UTC)
            for connection_id, _owner_user_id, last_sync_at in result.all():
                lock_key = f"sync:{connection_id}"
                if not await acquire_lock(lock_key):
                    continue
                try:
                    connection = await engine._load_connection_for_owner_context(
                        session,
                        connection_id,
                    )
                    sync_interval = str((connection.config or {}).get("sync_interval") or "")
                    interval_mins = interval_to_minutes(sync_interval)
                    # manual connections (interval_mins is None) are never auto-synced
                    if interval_mins is None:
                        continue
                    # skip if synced more recently than the interval
                    if last_sync_at is not None:
                        # DB drivers may return naive datetimes; coerce to UTC-aware
                        if last_sync_at.tzinfo is None:
                            last_sync_at = last_sync_at.replace(tzinfo=UTC)
                        elapsed = (now - last_sync_at).total_seconds() / 60
                        if elapsed < interval_mins:
                            continue
                    runs.append(await engine.sync_connection(connection))
                finally:
                    await release_lock(lock_key)
        return runs

    async def _load_connection_for_owner_context(
        self, session: AsyncSession, connection_id: str
    ) -> ProviderConnection:
        result = await session.execute(
            select(ProviderConnection.__table__.c.user_id).where(
                ProviderConnection.__table__.c.id == connection_id
            )
        )
        owner_user_id = result.scalar_one_or_none()
        if owner_user_id is None:
            raise RuntimeError("connection missing")
        owner = await session.get(User, owner_user_id)
        if owner is None:
            raise RuntimeError("owner missing")
        dek = EncryptionService().decrypt_dek(owner.encrypted_dek)
        with EncryptionService().user_dek_context(dek):
            connection = await session.get(ProviderConnection, connection_id)
            if connection is None:
                raise RuntimeError("connection missing")
            return connection

    async def _adopt_or_create_run(
        self, session: AsyncSession, connection: ProviderConnection, existing_run_id: str | None
    ) -> SyncRun:
        if existing_run_id:
            existing = await session.get(SyncRun, existing_run_id)
            if existing is not None:
                return existing
        run = SyncRun(provider_connection_id=connection.id, status="queued")
        session.add(run)
        await session.flush()
        return run

    async def _sync_accounts(
        self, session: AsyncSession, connection: ProviderConnection, accounts: list
    ) -> dict[str, Account]:
        rows: dict[str, Account] = {}
        for item in accounts:
            insert_vals = {
                "user_id": connection.user_id,
                "provider_connection_id": connection.id,
                "provider_account_id": item.provider_account_id,
                "account_type": item.account_type,
                "currency": item.currency,
                "display_name": item.display_name,
                "iban": item.iban,
                "sort_code": item.sort_code,
                "account_number": item.account_number,
                "is_active": True,
                "raw_payload": item.raw_payload,
            }
            # §13.1 guard: created_at must NOT be updated on conflict so that
            # the oldest-account-wins master selection remains stable across
            # re-syncs.  Pass only the mutable fields in update_values.
            update_vals = {k: v for k, v in insert_vals.items() if k != "created_at"}
            row = await upsert_and_fetch(
                session,
                Account,
                insert_vals,
                ["provider_connection_id", "provider_account_id"],
                update_values=update_vals,
            )
            rows[item.provider_account_id] = row

            # --- Phase 3: identity matching ---
            identifier_rows = extract_identifiers(
                item,
                str(connection.user_id),
                connection.provider_type,
                secret_key=settings.secret_key,
            )
            await resolve_account_identity(
                session,
                row,
                identifier_rows,
                user_id=str(connection.user_id),
            )

        return rows

    async def _sync_balances(
        self, session: AsyncSession, account_rows: dict[str, Account], balances: list
    ) -> None:
        for item in balances:
            account = account_rows.get(item.account_id)
            if account is None:
                continue
            await insert_row(
                session,
                Balance,
                {
                    "account_id": account.id,
                    "available": item.available,
                    "current": item.current,
                    "currency": item.currency,
                    "overdraft": item.overdraft,
                    "credit_limit": item.credit_limit,
                    "as_of": item.as_of,
                    "raw_payload": item.raw_payload,
                },
            )

    async def _sync_cards(
        self,
        session: AsyncSession,
        connection: ProviderConnection,
        account_rows: dict[str, Account],
        cards: list,
    ) -> dict[str, Card]:
        rows: dict[str, Card] = {}
        for item in cards:
            account = account_rows.get(item.account_provider_id or "")
            row = await upsert_and_fetch(
                session,
                Card,
                {
                    "provider_connection_id": connection.id,
                    "provider_card_id": item.provider_card_id,
                    "account_id": account.id if account else None,
                    "display_name": item.display_name,
                    "card_network": item.card_network,
                    "partial_card_number": item.partial_card_number,
                    "currency": item.currency,
                    "credit_limit": item.credit_limit,
                    "raw_payload": item.raw_payload,
                },
                ["provider_connection_id", "provider_card_id"],
            )
            rows[item.provider_card_id] = row
        return rows

    async def _sync_transactions(
        self, session: AsyncSession, connection_id: str, account: Account, transactions: list
    ) -> int:
        """Sync a list of provider transactions for *account*.

        Dedup strategy (Phase 5):

        Tier 1 — identity-scoped key (primary, always active when identity_id is set):
            HMAC(manifold-txn-dedup, identity_id + ':' + normalized_provider_transaction_id)
            Upsert conflict key: identity_dedup_hash.
            Prevents the same physical transaction from being double-inserted when two
            connections both fetch it under the same identity.

        Fallback — connection-scoped key (when account.identity_id is null):
            MD5(connection_id:provider_transaction_id) — existing behavior, unchanged.
            Upsert conflict key: dedup_hash.
            Preserves full backward compatibility for accounts not yet matched to an identity.

        Tier 2 — content-hash fallback (DISABLED BY DEFAULT):
            Computed and stored in content_hash for future use, but NOT used as a match
            key unless the identity pair has explicitly opted in (Phase 6 / §3.3 Option C).
            When Tier 2 would have matched, a DEBUG log is emitted to measure opportunity.

        Both legacy dedup_hash and identity_dedup_hash are written on every upsert
        so the uq_transactions_dedup_hash constraint remains satisfied during transition.
        """
        inserted = 0
        identity_id: str | None = str(account.identity_id) if account.identity_id else None

        for item in transactions:
            # --- Compute hashes ---
            legacy_dedup_hash = hashlib.md5(
                f"{connection_id}:{item.provider_transaction_id}".encode(), usedforsecurity=False
            ).hexdigest()

            tier1_hash: str | None = None
            content_hash_val: str | None = None

            if identity_id:
                tier1_hash = compute_tier1_hash(
                    identity_id,
                    item.provider_transaction_id,
                    secret_key=settings.secret_key,
                )
                # Tier 2: compute content hash from already-decrypted plaintext values.
                # The DEK context is active (sync_connection sets it before calling us).
                content_hash_val = compute_content_hash(
                    identity_id,
                    item.amount,
                    item.transaction_date,
                    item.description,
                    secret_key=settings.secret_key,
                )

            # --- Determine dedup/upsert key ---
            if tier1_hash is not None:
                # Identity-scoped Tier 1 path.
                # Primary lookup: row already stored with this identity_dedup_hash
                # (covers the normal cross-connection dedup case).
                check_result = await session.execute(
                    select(Transaction).where(
                        Transaction.identity_dedup_hash == tier1_hash
                    )
                )
                existing_row = check_result.scalar_one_or_none()

                if existing_row is None:
                    # Secondary lookup: row stored before the account had an identity_id
                    # (identity_dedup_hash is NULL on that row).  Without this check an
                    # INSERT would violate uq_transactions_account_provider_txn because
                    # ON CONFLICT (identity_dedup_hash) never fires for NULL values.
                    legacy_check_result = await session.execute(
                        select(Transaction).where(
                            Transaction.account_id == account.id,
                            Transaction.provider_transaction_id
                            == item.provider_transaction_id,
                        )
                    )
                    existing_row = legacy_check_result.scalar_one_or_none()

                if existing_row is None:
                    inserted += 1

                if existing_row is not None:
                    # Tier 1 hit (either via identity_dedup_hash or legacy key) —
                    # update mutable fields in Python to avoid any ON CONFLICT ambiguity
                    # across the three backends.
                    # Guard: the existing row's account must belong to the same identity.
                    # If not, this is a hash collision or an identity mis-merge — log and skip.
                    if existing_row.account_id != account.id:
                        existing_account_result = await session.execute(
                            select(Account).where(Account.id == existing_row.account_id)
                        )
                        existing_account = existing_account_result.scalar_one_or_none()
                        if (
                            existing_account is None
                            or str(existing_account.identity_id) != identity_id
                        ):
                            logger.warning(
                                "tier1_identity_mismatch_skipped",
                                extra={
                                    "tier1_hash": tier1_hash,
                                    "incoming_account_id": str(account.id),
                                    "existing_account_id": str(existing_row.account_id),
                                    "identity_id": identity_id,
                                },
                            )
                            # existing_row was not None so inserted was not incremented above.
                            continue

                    # Backfill identity hashes and refresh mutable fields on the existing row.
                    existing_row.identity_dedup_hash = tier1_hash
                    existing_row.dedup_hash = legacy_dedup_hash
                    existing_row.content_hash = content_hash_val
                    existing_row.status = "booked"
                    existing_row.amount = item.amount
                    existing_row.currency = item.currency
                    existing_row.transaction_type = item.transaction_type
                    existing_row.transaction_category = item.transaction_category
                    existing_row.description = item.description
                    existing_row.merchant_name = item.merchant_name
                    existing_row.merchant_category = item.merchant_category
                    existing_row.transaction_date = item.transaction_date
                    existing_row.settled_date = item.settled_date
                    existing_row.running_balance = item.running_balance
                    existing_row.raw_payload = item.raw_payload
                    await session.flush()
                else:
                    # Genuinely new row — no existing record under either unique key.
                    await upsert_and_fetch(
                        session,
                        Transaction,
                        {
                            "account_id": account.id,
                            "card_id": None,
                            "provider_transaction_id": item.provider_transaction_id,
                            "status": "booked",
                            "amount": item.amount,
                            "currency": item.currency,
                            "transaction_type": item.transaction_type,
                            "transaction_category": item.transaction_category,
                            "description": item.description,
                            "merchant_name": item.merchant_name,
                            "merchant_category": item.merchant_category,
                            "transaction_date": item.transaction_date,
                            "settled_date": item.settled_date,
                            "running_balance": item.running_balance,
                            "dedup_hash": legacy_dedup_hash,
                            "identity_dedup_hash": tier1_hash,
                            "content_hash": content_hash_val,
                            "raw_payload": item.raw_payload,
                        },
                        ["identity_dedup_hash"],
                    )

            else:
                # --- Legacy fallback path (account.identity_id is null) ---
                # Behavior identical to pre-Phase 5 sync so existing accounts are unaffected.
                check_result = await session.execute(
                    select(Transaction).where(Transaction.dedup_hash == legacy_dedup_hash)
                )
                if check_result.scalar_one_or_none() is None:
                    inserted += 1

                    # Tier 2 opportunity log: if there is an identity and content_hash matches
                    # an existing row, Tier 2 would have collapsed this.  Not applicable here
                    # (no identity_id) — no log needed.

                await upsert_and_fetch(
                    session,
                    Transaction,
                    {
                        "account_id": account.id,
                        "card_id": None,
                        "provider_transaction_id": item.provider_transaction_id,
                        "status": "booked",
                        "amount": item.amount,
                        "currency": item.currency,
                        "transaction_type": item.transaction_type,
                        "transaction_category": item.transaction_category,
                        "description": item.description,
                        "merchant_name": item.merchant_name,
                        "merchant_category": item.merchant_category,
                        "transaction_date": item.transaction_date,
                        "settled_date": item.settled_date,
                        "running_balance": item.running_balance,
                        "dedup_hash": legacy_dedup_hash,
                        "identity_dedup_hash": None,
                        "content_hash": None,
                        "raw_payload": item.raw_payload,
                    },
                    ["dedup_hash"],
                )

            await insert_row(
                session,
                Event,
                {
                    "event_type": "transaction_detected",
                    "source_type": "observed",
                    "account_id": account.id,
                    "user_id": account.user_id,
                    "payload": {
                        "provider_transaction_id": item.provider_transaction_id,
                        "amount": str(item.amount),
                    },
                    "explanation": item.description,
                },
            )
        return inserted

    async def _sync_pending(self, provider, context, account: Account, account_data) -> None:
        if not provider.supports_pending:
            return
        assert self._session is not None
        await self._session.execute(
            delete(PendingTransaction).where(PendingTransaction.account_id == account.id)
        )
        items = await provider.get_pending_transactions(context, account_data)
        for item in items:
            await insert_row(
                self._session,
                PendingTransaction,
                {
                    "account_id": account.id,
                    "provider_transaction_id": item.provider_transaction_id,
                    "amount": item.amount,
                    "currency": item.currency,
                    "description": item.description,
                    "merchant_name": item.merchant_name,
                    "transaction_date": item.transaction_date,
                    "raw_payload": item.raw_payload,
                },
            )

    async def _sync_direct_debits(self, provider, context, account: Account, account_data) -> None:
        if not provider.supports_direct_debits:
            return
        assert self._session is not None
        items = await provider.get_direct_debits(context, account_data)
        for item in items:
            await upsert_and_fetch(
                self._session,
                DirectDebit,
                {
                    "account_id": account.id,
                    "provider_mandate_id": item.provider_mandate_id,
                    "name": item.name,
                    "status": item.status,
                    "amount": item.amount,
                    "currency": item.currency,
                    "frequency": item.frequency,
                    "reference": item.reference,
                    "last_payment_date": item.last_payment_date,
                    "next_payment_date": item.next_payment_date,
                    "next_payment_amount": item.next_payment_amount,
                    "raw_payload": item.raw_payload,
                },
                ["account_id", "provider_mandate_id"],
                lookup={"account_id": account.id, "provider_mandate_id": item.provider_mandate_id},
            )

    async def _sync_standing_orders(
        self, provider, context, account: Account, account_data
    ) -> None:
        if not provider.supports_standing_orders:
            return
        assert self._session is not None
        items = await provider.get_standing_orders(context, account_data)
        for item in items:
            await upsert_and_fetch(
                self._session,
                StandingOrder,
                {
                    "account_id": account.id,
                    "provider_standing_order_id": item.provider_standing_order_id,
                    "reference": item.reference,
                    "status": item.status,
                    "currency": item.currency,
                    "frequency": item.frequency,
                    "first_payment_date": item.first_payment_date,
                    "first_payment_amount": item.first_payment_amount,
                    "next_payment_date": item.next_payment_date,
                    "next_payment_amount": item.next_payment_amount,
                    "final_payment_date": item.final_payment_date,
                    "final_payment_amount": item.final_payment_amount,
                    "previous_payment_date": item.previous_payment_date,
                    "previous_payment_amount": item.previous_payment_amount,
                    "raw_payload": item.raw_payload,
                },
                ["account_id", "provider_standing_order_id"],
                lookup={
                    "account_id": account.id,
                    "provider_standing_order_id": item.provider_standing_order_id,
                },
            )

    async def _fail_run(self, session: AsyncSession, run: SyncRun, exc: SyncError) -> None:
        run.status = "failed"
        run.error_code = exc.error_code
        run.error_detail = exc.detail
        run.completed_at = datetime.now(UTC)
        await session.commit()

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select

from manifold.models.account import Account
from manifold.models.alarm import AlarmAccountAssignment, AlarmDefinition
from manifold.models.balance import Balance
from manifold.models.card import Card
from manifold.models.direct_debit import DirectDebit
from manifold.models.event import Event
from manifold.models.pending_transaction import PendingTransaction
from manifold.models.provider_connection import ProviderConnection
from manifold.models.recurrence_profile import RecurrenceProfile
from manifold.models.standing_order import StandingOrder
from manifold.models.sync_run import SyncRun
from manifold.models.transaction import Transaction
from manifold.security.encryption import EncryptionService


async def _login(client, username: str, password: str):
    return await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )


async def _build_connection_with_data(db_session, user):
    """Create a connection with an account, transaction, balance, card, sync_run,
    and alarm account assignment.  Returns (connection, account, ...) for assertions."""
    enc = EncryptionService()
    dek = enc.decrypt_dek(user.encrypted_dek)
    with enc.user_dek_context(dek):
        connection = ProviderConnection(
            user_id=str(user.id),
            provider_type="test-provider",
            display_name="Test connection",
            status="active",
            auth_status="connected",
        )
        db_session.add(connection)
        await db_session.flush()

        account = Account(
            user_id=str(user.id),
            provider_connection_id=str(connection.id),
            provider_account_id="prov-acc-delete-1",
            account_type="current",
            currency="GBP",
            display_name="Delete account",
            is_active=True,
            raw_payload={"source": "test"},
        )
        db_session.add(account)
        await db_session.flush()

        # Card linked to account AND connection.
        card = Card(
            provider_connection_id=str(connection.id),
            account_id=str(account.id),
            provider_card_id="prov-card-1",
            display_name="Test card",
        )
        db_session.add(card)
        await db_session.flush()

        # Transaction linked to account (and card).
        txn = Transaction(
            account_id=str(account.id),
            card_id=str(card.id),
            provider_transaction_id="ptxn-1",
            status="settled",
            dedup_hash="hash-delete-1",
        )
        db_session.add(txn)

        # Pending transaction.
        pending = PendingTransaction(
            account_id=str(account.id),
            provider_transaction_id="pending-1",
            amount=Decimal("9.99"),
            currency="GBP",
        )
        db_session.add(pending)

        # Balance linked to account.
        balance = Balance(
            account_id=str(account.id),
            available=Decimal("100.00"),
            current=Decimal("100.00"),
            currency="GBP",
        )
        db_session.add(balance)

        # Balance linked to card.
        card_balance = Balance(
            card_id=str(card.id),
            available=Decimal("500.00"),
            current=Decimal("500.00"),
            currency="GBP",
        )
        db_session.add(card_balance)

        # DirectDebit.
        direct_debit = DirectDebit(
            account_id=str(account.id),
            provider_mandate_id="mandate-1",
            name="Netflix",
        )
        db_session.add(direct_debit)

        # StandingOrder.
        standing_order = StandingOrder(
            account_id=str(account.id),
            provider_standing_order_id="so-1",
            reference="Rent",
        )
        db_session.add(standing_order)

        # RecurrenceProfile.
        recurrence = RecurrenceProfile(
            account_id=str(account.id),
            label="Coffee",
        )
        db_session.add(recurrence)

        # Event.
        event = Event(
            event_type="balance_update",
            source_type="sync",
            account_id=str(account.id),
            user_id=str(user.id),
            payload={"amount": "100.00"},
        )
        db_session.add(event)

        # SyncRun at account level.
        sync_run_account = SyncRun(
            provider_connection_id=str(connection.id),
            account_id=str(account.id),
            status="completed",
        )
        db_session.add(sync_run_account)

        # SyncRun at connection level (no account).
        sync_run_conn = SyncRun(
            provider_connection_id=str(connection.id),
            status="completed",
        )
        db_session.add(sync_run_conn)

        # Alarm definition + account assignment.
        alarm = AlarmDefinition(
            user_id=str(user.id),
            name="Low balance",
            status="active",
        )
        db_session.add(alarm)
        await db_session.flush()

        assignment = AlarmAccountAssignment(
            alarm_id=str(alarm.id),
            account_id=str(account.id),
        )
        db_session.add(assignment)

        await db_session.commit()

        return (
            connection,
            account,
            card,
            txn,
            pending,
            balance,
            card_balance,
            direct_debit,
            standing_order,
            recurrence,
            event,
            sync_run_account,
            sync_run_conn,
            alarm,
            assignment,
        )


async def _build_unrelated_connection(db_session, user):
    """A second connection with minimal data — must survive the first delete."""
    enc = EncryptionService()
    dek = enc.decrypt_dek(user.encrypted_dek)
    with enc.user_dek_context(dek):
        connection = ProviderConnection(
            user_id=str(user.id),
            provider_type="test-provider",
            display_name="Unrelated connection",
            status="active",
            auth_status="connected",
        )
        db_session.add(connection)
        await db_session.flush()

        account = Account(
            user_id=str(user.id),
            provider_connection_id=str(connection.id),
            provider_account_id="prov-acc-unrelated-1",
            account_type="current",
            currency="GBP",
            display_name="Unrelated account",
            is_active=True,
            raw_payload={},
        )
        db_session.add(account)
        await db_session.flush()

        txn = Transaction(
            account_id=str(account.id),
            provider_transaction_id="ptxn-unrelated-1",
            status="settled",
            dedup_hash="hash-unrelated-1",
        )
        db_session.add(txn)
        await db_session.commit()

        return connection, account, txn


@pytest.mark.asyncio
async def test_delete_connection_cascades_all_children(client, test_user, db_session):
    """DELETE /connections/{id} → 204, all dependent rows gone."""
    user, password = test_user
    await _login(client, user.username, password)

    (
        connection,
        account,
        card,
        txn,
        pending,
        balance,
        card_balance,
        direct_debit,
        standing_order,
        recurrence,
        event,
        sync_run_account,
        sync_run_conn,
        alarm,
        assignment,
    ) = await _build_connection_with_data(db_session, user)

    # Capture all IDs as plain strings BEFORE the HTTP call — after expire_all()
    # accessing .id on a stale ORM object triggers a sync lazy-load which fails in
    # an async context.
    connection_id = str(connection.id)
    account_id = str(account.id)
    card_id = str(card.id)
    txn_id = str(txn.id)
    pending_id = str(pending.id)
    balance_id = str(balance.id)
    card_balance_id = str(card_balance.id)
    direct_debit_id = str(direct_debit.id)
    standing_order_id = str(standing_order.id)
    recurrence_id = str(recurrence.id)
    event_id = str(event.id)
    sync_run_account_id = str(sync_run_account.id)
    sync_run_conn_id = str(sync_run_conn.id)
    alarm_id = str(alarm.id)
    assignment_id = str(assignment.id)

    response = await client.delete(f"/api/v1/connections/{connection_id}")
    assert response.status_code == 204

    # The test db_session and the HTTP client use separate AsyncSession instances.
    # expire_all() drops the identity-map cache so subsequent queries go to the DB.
    # Select only unencrypted primary-key columns — avoids needing a DEK context
    # in this assertion-only code path.
    async def exists(model, pk_value: str) -> bool:
        result = await db_session.execute(
            select(model.__table__.c.id).where(model.__table__.c.id == pk_value)
        )
        return result.scalar_one_or_none() is not None

    # Connection gone.
    assert not await exists(ProviderConnection, connection_id)
    # Account gone.
    assert not await exists(Account, account_id)
    # Card gone.
    assert not await exists(Card, card_id)
    # Transaction gone.
    assert not await exists(Transaction, txn_id)
    # PendingTransaction gone.
    assert not await exists(PendingTransaction, pending_id)
    # Balance (account-linked) gone.
    assert not await exists(Balance, balance_id)
    # Balance (card-linked) gone.
    assert not await exists(Balance, card_balance_id)
    # DirectDebit gone.
    assert not await exists(DirectDebit, direct_debit_id)
    # StandingOrder gone.
    assert not await exists(StandingOrder, standing_order_id)
    # RecurrenceProfile gone.
    assert not await exists(RecurrenceProfile, recurrence_id)
    # Event gone.
    assert not await exists(Event, event_id)
    # Both SyncRuns gone.
    assert not await exists(SyncRun, sync_run_account_id)
    assert not await exists(SyncRun, sync_run_conn_id)
    # AlarmAccountAssignment gone.
    assert not await exists(AlarmAccountAssignment, assignment_id)
    # AlarmDefinition preserved (user-level, not connection-level).
    assert await exists(AlarmDefinition, alarm_id)


@pytest.mark.asyncio
async def test_delete_connection_does_not_touch_unrelated_connection(client, test_user, db_session):
    """Deleting one connection must not affect a second connection's data."""
    user, password = test_user
    await _login(client, user.username, password)

    (connection, *_) = await _build_connection_with_data(db_session, user)
    unrelated_conn, unrelated_account, unrelated_txn = await _build_unrelated_connection(
        db_session, user
    )

    # Capture IDs before HTTP call (see note in test above).
    connection_id = str(connection.id)
    unrelated_conn_id = str(unrelated_conn.id)
    unrelated_account_id = str(unrelated_account.id)
    unrelated_txn_id = str(unrelated_txn.id)

    response = await client.delete(f"/api/v1/connections/{connection_id}")
    assert response.status_code == 204

    async def exists(model, pk_value: str) -> bool:
        result = await db_session.execute(
            select(model.__table__.c.id).where(model.__table__.c.id == pk_value)
        )
        return result.scalar_one_or_none() is not None

    # Unrelated connection data intact.
    assert await exists(ProviderConnection, unrelated_conn_id)
    assert await exists(Account, unrelated_account_id)
    assert await exists(Transaction, unrelated_txn_id)


@pytest.mark.asyncio
async def test_delete_connection_403_for_other_user(client, test_user, another_user, db_session):
    """A different user must get 403 when trying to delete someone else's connection."""
    user, _ = test_user
    other_user, other_password = another_user

    enc = EncryptionService()
    dek = enc.decrypt_dek(user.encrypted_dek)
    with enc.user_dek_context(dek):
        connection = ProviderConnection(
            user_id=str(user.id),
            provider_type="test-provider",
            display_name="Owned by user1",
            status="active",
            auth_status="connected",
        )
        db_session.add(connection)
        await db_session.commit()

    await _login(client, other_user.username, other_password)

    response = await client.delete(f"/api/v1/connections/{connection.id}")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_connection_404_for_missing_id(client, test_user):
    """Deleting a non-existent connection id returns 404."""
    user, password = test_user
    await _login(client, user.username, password)

    response = await client.delete("/api/v1/connections/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404

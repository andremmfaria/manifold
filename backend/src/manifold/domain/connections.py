from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.models.account import Account
from manifold.models.alarm import AlarmAccountAssignment
from manifold.models.balance import Balance
from manifold.models.card import Card
from manifold.models.direct_debit import DirectDebit
from manifold.models.event import Event
from manifold.models.oauth_state import OAuthState
from manifold.models.pending_transaction import PendingTransaction
from manifold.models.provider_connection import ProviderConnection
from manifold.models.recurrence_profile import RecurrenceProfile
from manifold.models.standing_order import StandingOrder
from manifold.models.sync_run import SyncRun
from manifold.models.transaction import Transaction


async def delete_connection_cascade(
    session: AsyncSession,
    connection: ProviderConnection,
) -> None:
    """Delete a provider connection and all dependent rows in dependency order.

    Operates entirely within the caller's transaction — does NOT commit.
    The caller is responsible for committing or rolling back.

    Deletion order (deepest grandchildren first):
    1. AlarmAccountAssignment  (FK → accounts.id)
    2. Balance                 (FK → accounts.id  +  FK → cards.id)
    3. Transaction             (FK → accounts.id, with nullable card_id → cards.id)
    4. PendingTransaction      (FK → accounts.id)
    5. DirectDebit             (FK → accounts.id)
    6. StandingOrder           (FK → accounts.id)
    7. RecurrenceProfile       (FK → accounts.id)
    8. Event                   (nullable FK → accounts.id)
    9. SyncRun by account_id   (nullable FK → accounts.id)
    10. Card                   (FK → provider_connections.id, nullable FK → accounts.id)
    11. Account                (FK → provider_connections.id)
    --- connection-level rows ---
    12. SyncRun by connection  (FK → provider_connections.id)
    13. OAuthState             (FK → provider_connections.id, ondelete=CASCADE — explicit anyway)
    14. session.delete(connection)
    """
    connection_id = connection.id

    # Collect account ids belonging to this connection.
    account_id_rows = await session.execute(
        select(Account.id).where(Account.provider_connection_id == connection_id)
    )
    account_ids = list(account_id_rows.scalars().all())

    # Collect card ids belonging to this connection (for balance cleanup).
    card_id_rows = await session.execute(
        select(Card.id).where(Card.provider_connection_id == connection_id)
    )
    card_ids = list(card_id_rows.scalars().all())

    if account_ids:
        # 1. AlarmAccountAssignment — links alarms to accounts being removed.
        await session.execute(
            delete(AlarmAccountAssignment).where(AlarmAccountAssignment.account_id.in_(account_ids))
        )

        # 2. Balance by account_id.
        await session.execute(delete(Balance).where(Balance.account_id.in_(account_ids)))

        # 3. Transaction by account_id (covers transactions referencing cards of these accounts).
        await session.execute(delete(Transaction).where(Transaction.account_id.in_(account_ids)))

        # 4. PendingTransaction by account_id.
        await session.execute(
            delete(PendingTransaction).where(PendingTransaction.account_id.in_(account_ids))
        )

        # 5. DirectDebit by account_id.
        await session.execute(delete(DirectDebit).where(DirectDebit.account_id.in_(account_ids)))

        # 6. StandingOrder by account_id.
        await session.execute(
            delete(StandingOrder).where(StandingOrder.account_id.in_(account_ids))
        )

        # 7. RecurrenceProfile by account_id.
        await session.execute(
            delete(RecurrenceProfile).where(RecurrenceProfile.account_id.in_(account_ids))
        )

        # 8. Event by account_id (nullable — only rows scoped to these accounts).
        await session.execute(delete(Event).where(Event.account_id.in_(account_ids)))

        # 9. SyncRun rows scoped to individual accounts.
        await session.execute(delete(SyncRun).where(SyncRun.account_id.in_(account_ids)))

    # 2b. Balance by card_id for cards with no account_id (connection-level cards).
    # Cards without an account_id won't have been covered by the account_ids pass above.
    if card_ids:
        await session.execute(delete(Balance).where(Balance.card_id.in_(card_ids)))

    # 10. Card by provider_connection_id (covers all cards regardless of account linkage).
    await session.execute(delete(Card).where(Card.provider_connection_id == connection_id))

    # 11. Account by provider_connection_id.
    await session.execute(delete(Account).where(Account.provider_connection_id == connection_id))

    # 12. SyncRun by provider_connection_id (connection-level / pre-account sync runs).
    await session.execute(delete(SyncRun).where(SyncRun.provider_connection_id == connection_id))

    # 13. OAuthState — has ondelete=CASCADE on the FK but delete explicitly for clarity.
    await session.execute(delete(OAuthState).where(OAuthState.connection_id == connection_id))

    # 14. Finally remove the connection itself.
    await session.delete(connection)

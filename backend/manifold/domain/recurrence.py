from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from statistics import mean, stdev

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from manifold.models.account import Account
from manifold.models.event import Event
from manifold.models.recurrence_profile import RecurrenceProfile
from manifold.models.transaction import Transaction
from manifold.models.user import User
from manifold.security.encryption import EncryptionService

LOOKBACK_DAYS = 90
PREDICTION_WINDOW_DAYS = 7
MIN_OCCURRENCES = 3
CV_THRESHOLD = 0.15
CADENCE_BASES = (7, 14, 28, 29, 30, 31, 90, 365)


@dataclass(slots=True)
class TransactionObservation:
    transaction: Transaction
    merchant_pattern: str
    merchant_label: str | None
    amount: Decimal | None
    transaction_at: datetime


@dataclass(slots=True)
class RecurrenceMatch:
    observations: list[TransactionObservation]
    amount_mean: Decimal | None
    amount_stddev: Decimal | None
    cadence_days: int
    cadence_stddev: float
    confidence: float
    first_seen: datetime
    last_seen: datetime
    next_predicted_at: datetime


class RecurrenceDetector:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def detect_for_all_users(self) -> None:
        result = await self._session.execute(
            select(Account.__table__.c.user_id).distinct().order_by(Account.__table__.c.user_id.asc())
        )
        for user_id in result.scalars().all():
            await self.detect_for_user(str(user_id))

    async def detect_for_user(self, user_id: str) -> None:
        owner = await self._session.get(User, user_id)
        if owner is None:
            return
        dek = EncryptionService().decrypt_dek(owner.encrypted_dek)
        now = datetime.now(UTC)
        cutoff = now - timedelta(days=LOOKBACK_DAYS)
        prediction_window_end = now + timedelta(days=PREDICTION_WINDOW_DAYS)
        with EncryptionService().user_dek_context(dek):
            accounts = await self._load_accounts(user_id)
            for account in accounts:
                await self._detect_account_recurrence(
                    account=account,
                    now=now,
                    cutoff=cutoff,
                    prediction_window_end=prediction_window_end,
                )
            await self._session.commit()

    async def _detect_account_recurrence(
        self,
        *,
        account: Account,
        now: datetime,
        cutoff: datetime,
        prediction_window_end: datetime,
    ) -> None:
        transactions = await self._load_booked_transactions(str(account.id))
        groups: dict[str, list[TransactionObservation]] = defaultdict(list)
        for transaction in transactions:
            observation = self._build_observation(transaction, cutoff)
            if observation is None:
                continue
            groups[observation.merchant_pattern].append(observation)

        profiles = await self._load_profiles_for_account(str(account.id))
        for merchant_pattern, observations in groups.items():
            if len(observations) < MIN_OCCURRENCES:
                continue
            match = self._analyze_group(observations)
            if match is None:
                continue
            profile = await self._upsert_profile(
                account=account,
                merchant_pattern=merchant_pattern,
                match=match,
                profiles=profiles,
            )
            self._mark_transactions(profile, match.observations)
            await self._create_prediction_event_if_needed(
                account=account,
                profile=profile,
                now=now,
                prediction_window_end=prediction_window_end,
            )

    async def _load_accounts(self, user_id: str) -> list[Account]:
        result = await self._session.execute(
            select(Account).where(Account.user_id == user_id).order_by(Account.created_at.asc())
        )
        return list(result.scalars().all())

    async def _load_booked_transactions(self, account_id: str) -> list[Transaction]:
        result = await self._session.execute(
            select(Transaction)
            .where(Transaction.account_id == account_id)
            .where(Transaction.status == "booked")
            .order_by(Transaction.created_at.asc())
        )
        return list(result.scalars().all())

    async def _load_profiles_for_account(self, account_id: str) -> dict[str, RecurrenceProfile]:
        result = await self._session.execute(
            select(RecurrenceProfile)
            .where(RecurrenceProfile.account_id == account_id)
            .order_by(RecurrenceProfile.created_at.asc())
        )
        profiles: dict[str, RecurrenceProfile] = {}
        for profile in result.scalars().all():
            key = (profile.merchant_pattern or "").strip().lower()
            profiles.setdefault(key, profile)
        return profiles

    def _build_observation(
        self, transaction: Transaction, cutoff: datetime
    ) -> TransactionObservation | None:
        transaction_at = self._parse_datetime(transaction.transaction_date)
        if transaction_at is None or transaction_at < cutoff:
            return None
        merchant_name = (transaction.merchant_name or "").strip()
        return TransactionObservation(
            transaction=transaction,
            merchant_pattern=merchant_name.lower(),
            merchant_label=merchant_name or None,
            amount=transaction.amount,
            transaction_at=transaction_at,
        )

    def _analyze_group(
        self, observations: list[TransactionObservation]
    ) -> RecurrenceMatch | None:
        ordered = sorted(observations, key=lambda item: item.transaction_at)
        inter_arrivals = self._compute_inter_arrivals(ordered)
        if not inter_arrivals:
            return None

        mean_cadence = float(mean(inter_arrivals))
        if mean_cadence <= 0 or not self._matches_supported_cadence(mean_cadence):
            return None

        cadence_stddev = 0.0
        if len(inter_arrivals) >= 2:
            cadence_stddev = float(stdev(inter_arrivals))
        cv = 0.0 if len(inter_arrivals) == 1 else cadence_stddev / mean_cadence
        if cv >= CV_THRESHOLD:
            return None

        amounts = [item.amount for item in ordered if item.amount is not None]
        amount_mean: Decimal | None = None
        amount_stddev: Decimal | None = None
        if amounts:
            amount_mean = mean(amounts)
            amount_stddev = Decimal("0") if len(amounts) == 1 else stdev(amounts)

        confidence = min(1.0, (len(ordered) / 10) * (1 - cv))
        first_seen = ordered[0].transaction_at
        last_seen = ordered[-1].transaction_at
        next_predicted_at = last_seen + timedelta(days=mean_cadence)
        return RecurrenceMatch(
            observations=ordered,
            amount_mean=amount_mean,
            amount_stddev=amount_stddev,
            cadence_days=max(1, round(mean_cadence)),
            cadence_stddev=cadence_stddev,
            confidence=max(0.0, confidence),
            first_seen=first_seen,
            last_seen=last_seen,
            next_predicted_at=next_predicted_at,
        )

    def _compute_inter_arrivals(self, observations: list[TransactionObservation]) -> list[int]:
        inter_arrivals: list[int] = []
        for previous, current in zip(observations, observations[1:], strict=False):
            delta_days = (current.transaction_at.date() - previous.transaction_at.date()).days
            if delta_days > 0:
                inter_arrivals.append(delta_days)
        return inter_arrivals

    def _matches_supported_cadence(self, mean_cadence: float) -> bool:
        for base in CADENCE_BASES:
            lower = base * 0.8
            upper = base * 1.2
            if lower <= mean_cadence <= upper:
                return True
        return False

    async def _upsert_profile(
        self,
        *,
        account: Account,
        merchant_pattern: str,
        match: RecurrenceMatch,
        profiles: dict[str, RecurrenceProfile],
    ) -> RecurrenceProfile:
        profile = profiles.get(merchant_pattern)
        if profile is None:
            profile = RecurrenceProfile(
                account_id=str(account.id),
                merchant_pattern=merchant_pattern,
            )
            self._session.add(profile)
            await self._session.flush()
            profiles[merchant_pattern] = profile

        profile.label = self._select_label(match.observations)
        profile.merchant_pattern = merchant_pattern
        profile.amount_mean = match.amount_mean
        profile.amount_stddev = match.amount_stddev
        profile.cadence_days = match.cadence_days
        profile.cadence_stddev = match.cadence_stddev
        profile.confidence = match.confidence
        profile.first_seen = match.first_seen
        profile.last_seen = match.last_seen
        profile.next_predicted_at = match.next_predicted_at
        profile.next_predicted_amount = match.amount_mean
        profile.status = "active"
        profile.data_source = "observed"
        await self._session.flush()
        return profile

    def _select_label(self, observations: list[TransactionObservation]) -> str | None:
        for observation in reversed(observations):
            if observation.merchant_label:
                return observation.merchant_label
        return None

    def _mark_transactions(
        self, profile: RecurrenceProfile, observations: list[TransactionObservation]
    ) -> None:
        for observation in observations:
            observation.transaction.is_recurring_candidate = True
            observation.transaction.recurrence_profile_id = str(profile.id)

    async def _create_prediction_event_if_needed(
        self,
        *,
        account: Account,
        profile: RecurrenceProfile,
        now: datetime,
        prediction_window_end: datetime,
    ) -> None:
        predicted_at = profile.next_predicted_at
        if predicted_at is None or predicted_at < now or predicted_at > prediction_window_end:
            return

        existing_events = await self._load_prediction_events(str(account.id), predicted_at)
        for event in existing_events:
            if str((event.payload or {}).get("profile_id") or "") == str(profile.id):
                return

        event = Event(
            event_type="debit_predicted",
            source_type="predicted",
            user_id=str(account.user_id),
            account_id=str(account.id),
            occurred_at=predicted_at,
            recorded_at=now,
            confidence=profile.confidence,
            payload={
                "profile_id": str(profile.id),
                "predicted_at": predicted_at.isoformat(),
                "amount_mean": (
                    str(profile.amount_mean) if profile.amount_mean is not None else None
                ),
            },
        )
        self._session.add(event)
        await self._session.flush()

    async def _load_prediction_events(self, account_id: str, occurred_at: datetime) -> list[Event]:
        result = await self._session.execute(
            select(Event)
            .where(Event.account_id == account_id)
            .where(Event.event_type == "debit_predicted")
            .where(Event.source_type == "predicted")
            .where(Event.occurred_at == occurred_at)
            .order_by(Event.recorded_at.desc())
        )
        return list(result.scalars().all())

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)


__all__ = ["RecurrenceDetector"]

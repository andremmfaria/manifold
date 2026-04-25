from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from manifold.domain.recurrence import RecurrenceDetector, TransactionObservation


def _observation(day: int) -> TransactionObservation:
    when = datetime(2025, 1, day, tzinfo=UTC)
    return TransactionObservation(
        transaction=SimpleNamespace(),
        merchant_pattern="gym membership",
        merchant_label="Gym Membership",
        amount=Decimal("12.50"),
        transaction_at=when,
    )


def test_cadence_detection_monthly() -> None:
    detector = RecurrenceDetector(session=None)
    observations = [
        _observation(1),
        TransactionObservation(
            SimpleNamespace(),
            "gym membership",
            "Gym Membership",
            Decimal("12.50"),
            datetime(2025, 2, 1, tzinfo=UTC),
        ),
        TransactionObservation(
            SimpleNamespace(),
            "gym membership",
            "Gym Membership",
            Decimal("12.50"),
            datetime(2025, 3, 1, tzinfo=UTC),
        ),
        TransactionObservation(
            SimpleNamespace(),
            "gym membership",
            "Gym Membership",
            Decimal("12.50"),
            datetime(2025, 4, 1, tzinfo=UTC),
        ),
    ]

    match = detector._analyze_group(observations)

    assert match is not None
    assert 28 <= match.cadence_days <= 31
    assert match.cadence_stddev / ((31 + 28 + 31) / 3) < 0.15


def test_cadence_detection_weekly() -> None:
    detector = RecurrenceDetector(session=None)
    observations = [
        TransactionObservation(
            SimpleNamespace(),
            "salary",
            "Salary",
            Decimal("100.00"),
            datetime(2025, 1, 1, tzinfo=UTC),
        ),
        TransactionObservation(
            SimpleNamespace(),
            "salary",
            "Salary",
            Decimal("100.00"),
            datetime(2025, 1, 8, tzinfo=UTC),
        ),
        TransactionObservation(
            SimpleNamespace(),
            "salary",
            "Salary",
            Decimal("100.00"),
            datetime(2025, 1, 15, tzinfo=UTC),
        ),
        TransactionObservation(
            SimpleNamespace(),
            "salary",
            "Salary",
            Decimal("100.00"),
            datetime(2025, 1, 22, tzinfo=UTC),
        ),
    ]

    match = detector._analyze_group(observations)

    assert match is not None
    assert match.cadence_days == 7
    assert match.confidence > 0


def test_irregular_cadence_high_cv() -> None:
    detector = RecurrenceDetector(session=None)
    observations = [
        TransactionObservation(
            SimpleNamespace(), "rent", "Rent", Decimal("1000.00"), datetime(2025, 1, 1, tzinfo=UTC)
        ),
        TransactionObservation(
            SimpleNamespace(), "rent", "Rent", Decimal("1000.00"), datetime(2025, 1, 8, tzinfo=UTC)
        ),
        TransactionObservation(
            SimpleNamespace(), "rent", "Rent", Decimal("1000.00"), datetime(2025, 2, 20, tzinfo=UTC)
        ),
        TransactionObservation(
            SimpleNamespace(), "rent", "Rent", Decimal("1000.00"), datetime(2025, 4, 30, tzinfo=UTC)
        ),
    ]

    assert detector._analyze_group(observations) is None


def test_confidence_scales_with_count() -> None:
    detector = RecurrenceDetector(session=None)
    four = [
        TransactionObservation(
            SimpleNamespace(),
            "netflix",
            "Netflix",
            Decimal("9.99"),
            datetime(2025, 1, 1, tzinfo=UTC),
        ),
        TransactionObservation(
            SimpleNamespace(),
            "netflix",
            "Netflix",
            Decimal("9.99"),
            datetime(2025, 2, 1, tzinfo=UTC),
        ),
        TransactionObservation(
            SimpleNamespace(),
            "netflix",
            "Netflix",
            Decimal("9.99"),
            datetime(2025, 3, 1, tzinfo=UTC),
        ),
        TransactionObservation(
            SimpleNamespace(),
            "netflix",
            "Netflix",
            Decimal("9.99"),
            datetime(2025, 4, 1, tzinfo=UTC),
        ),
    ]
    six = four + [
        TransactionObservation(
            SimpleNamespace(),
            "netflix",
            "Netflix",
            Decimal("9.99"),
            datetime(2025, 5, 1, tzinfo=UTC),
        ),
        TransactionObservation(
            SimpleNamespace(),
            "netflix",
            "Netflix",
            Decimal("9.99"),
            datetime(2025, 6, 1, tzinfo=UTC),
        ),
    ]

    four_match = detector._analyze_group(four)
    six_match = detector._analyze_group(six)

    assert four_match is not None
    assert six_match is not None
    assert six_match.confidence > four_match.confidence

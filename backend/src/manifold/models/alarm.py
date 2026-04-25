from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from manifold.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from manifold.security.types import EncryptedJSON, EncryptedText


class AlarmDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "alarm_definitions"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(EncryptedText(), nullable=False)
    condition: Mapped[object | None] = mapped_column(EncryptedJSON(), nullable=True)
    condition_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    repeat_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    for_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    notify_on_resolve: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class AlarmState(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "alarm_states"
    __table_args__ = (UniqueConstraint("alarm_id", name="uq_alarm_states_alarm_id"),)

    alarm_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("alarm_definitions.id"), nullable=False
    )
    state: Mapped[str] = mapped_column(Text, nullable=False)
    mute_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_true: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class AlarmEvaluationResult(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "alarm_evaluation_results"

    alarm_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("alarm_definitions.id"), nullable=False
    )
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    result: Mapped[bool] = mapped_column(Boolean, nullable=False)
    previous_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    condition_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_snapshot: Mapped[object | None] = mapped_column(EncryptedJSON(), nullable=True)
    explanation: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class AlarmFiringEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "alarm_firing_events"

    alarm_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("alarm_definitions.id"), nullable=False
    )
    fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    explanation: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    condition_snapshot: Mapped[object | None] = mapped_column(EncryptedJSON(), nullable=True)
    context_snapshot: Mapped[object | None] = mapped_column(EncryptedJSON(), nullable=True)
    notifications_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class AlarmAccountAssignment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "alarm_account_assignments"
    __table_args__ = (
        UniqueConstraint("alarm_id", "account_id", name="uq_alarm_account_assignments_pair"),
    )

    alarm_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("alarm_definitions.id"), nullable=False
    )
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("accounts.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class AlarmNotifierAssignment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "alarm_notifier_assignments"
    __table_args__ = (
        UniqueConstraint("alarm_id", "notifier_id", name="uq_alarm_notifier_assignments_pair"),
    )

    alarm_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("alarm_definitions.id"), nullable=False
    )
    notifier_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("notifier_configs.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


class AlarmDefinitionVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "alarm_definition_versions"
    __table_args__ = (
        UniqueConstraint(
            "alarm_definition_id",
            "version",
            name="uq_alarm_definition_versions_definition_version",
        ),
    )

    alarm_definition_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("alarm_definitions.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    condition: Mapped[object] = mapped_column(EncryptedJSON(), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )


__all__ = [
    "AlarmAccountAssignment",
    "AlarmDefinition",
    "AlarmDefinitionVersion",
    "AlarmEvaluationResult",
    "AlarmFiringEvent",
    "AlarmNotifierAssignment",
    "AlarmState",
]

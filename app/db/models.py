"""Empat tabel Postgres (Architecture.md 7). Semua kunci UUID dengan gen_random_uuid()."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JOB_STATUSES = (
    "queued", "running", "planning", "retrieving", "ranking", "generating", "validating",
    "completed", "blocked", "insufficient", "handoff", "failed", "cancelled",
)


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


def _now() -> datetime:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)  # type: ignore[return-value]


class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = (CheckConstraint("role = 'owner'", name="ck_app_user_role"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    clerk_user_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default="owner")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = _now()

    holdings: Mapped[list["Holding"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Holding(Base):
    __tablename__ = "holding"
    __table_args__ = (UniqueConstraint("user_id", "ticker", name="uq_holding_user_ticker"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    # Divalidasi terhadap universe di aplikasi, bukan di database (Architecture.md 7).
    ticker: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(30, 10), nullable=False)
    avg_cost: Mapped[Decimal | None] = mapped_column(Numeric(30, 10), nullable=True)
    updated_at: Mapped[datetime] = _now()

    user: Mapped[AppUser] = relationship(back_populates="holdings")


class ChatSession(Base):
    __tablename__ = "chat_session"
    __table_args__ = (Index("ix_chat_session_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = _now()


class ChatJob(Base):
    __tablename__ = "chat_job"
    __table_args__ = (
        CheckConstraint("kind IN ('chat', 'daily_brief')", name="ck_chat_job_kind"),
        CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in JOB_STATUSES) + ")",
            name="ck_chat_job_status",
        ),
        Index("ix_chat_job_user_created", "user_id", "created_at", postgresql_ops={"created_at": "DESC"}),
        Index(
            "ix_chat_job_kind_hash_created",
            "kind", "holdings_hash", "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
        Index("ix_chat_job_status_updated", "status", "updated_at"),
        Index("ix_chat_job_session_created", "session_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_session.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="queued")
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    holdings_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(Text, nullable=False, server_default="id")
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    llm_calls: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    guardrail_log: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    handoff_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    handoff_resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = _now()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

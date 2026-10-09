"""initial schema: app_user, holding, chat_session, chat_job (Architecture.md 7)

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JOB_STATUSES = (
    "queued", "running", "planning", "retrieving", "ranking", "generating", "validating",
    "completed", "blocked", "insufficient", "handoff", "failed", "cancelled",
)


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("clerk_user_id", sa.Text(), nullable=False, unique=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default="owner"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint("role = 'owner'", name="ck_app_user_role"),
    )

    op.create_table(
        "holding",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticker", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(30, 10), nullable=False),
        sa.Column("avg_cost", sa.Numeric(30, 10), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "ticker", name="uq_holding_user_ticker"),
    )

    op.create_table(
        "chat_session",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_chat_session_user_created", "chat_session", ["user_id", "created_at"])

    status_check = "status IN (" + ", ".join(f"'{s}'" for s in JOB_STATUSES) + ")"
    op.create_table(
        "chat_job",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("chat_session.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("holdings_hash", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=False, server_default="id"),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("llm_calls", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("guardrail_log", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("handoff_reason", sa.Text(), nullable=True),
        sa.Column("handoff_resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('chat', 'daily_brief')", name="ck_chat_job_kind"),
        sa.CheckConstraint(status_check, name="ck_chat_job_status"),
    )
    op.create_index("ix_chat_job_user_created", "chat_job", ["user_id", "created_at"],
                    postgresql_ops={"created_at": "DESC"})
    op.create_index("ix_chat_job_kind_hash_created", "chat_job",
                    ["kind", "holdings_hash", "created_at"],
                    postgresql_ops={"created_at": "DESC"})
    op.create_index("ix_chat_job_status_updated", "chat_job", ["status", "updated_at"])
    op.create_index("ix_chat_job_session_created", "chat_job", ["session_id", "created_at"])


def downgrade() -> None:
    op.drop_table("chat_job")
    op.drop_table("chat_session")
    op.drop_table("holding")
    op.drop_table("app_user")

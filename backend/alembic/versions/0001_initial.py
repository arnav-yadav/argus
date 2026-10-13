"""Create services and heartbeats

Revision ID: 0001
Revises:
Create Date: 2026-10-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("heartbeat_interval_s", sa.Integer(), nullable=False),
        sa.Column("slo_target", sa.Float(), nullable=False),
        sa.Column("ingest_token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_services_slug", "services", ["slug"], unique=True)

    op.create_table(
        "heartbeats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "service_id",
            sa.Integer(),
            sa.ForeignKey("services.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
    )
    # Every uptime query filters by service and time range, so this index does the work.
    op.create_index("ix_heartbeats_service_received", "heartbeats", ["service_id", "received_at"])


def downgrade() -> None:
    op.drop_index("ix_heartbeats_service_received", table_name="heartbeats")
    op.drop_table("heartbeats")
    op.drop_index("ix_services_slug", table_name="services")
    op.drop_table("services")

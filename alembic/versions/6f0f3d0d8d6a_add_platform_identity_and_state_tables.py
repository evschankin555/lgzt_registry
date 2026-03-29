"""add platform identity and state tables

Revision ID: 6f0f3d0d8d6a
Revises: 9e38cee59d4c
Create Date: 2026-03-30 00:00:00.000000

"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6f0f3d0d8d6a"
down_revision: Union[str, Sequence[str], None] = "9e38cee59d4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_identity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("external_user_id", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "external_user_id", name="uq_user_identity_provider_external"),
    )
    op.create_table(
        "volunteer_identity",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("volunteer_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("external_user_id", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["volunteer_id"], ["user_volunteer.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "external_user_id", name="uq_volunteer_identity_provider_external"),
    )
    op.create_table(
        "platform_role",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("external_user_id", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("granted_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "external_user_id", "role", name="uq_platform_role"),
    )
    op.create_table(
        "blocked_identity_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("external_user_id", sa.String(length=255), nullable=False),
        sa.Column("blocked_at", sa.DateTime(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "conversation_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("external_user_id", sa.String(length=255), nullable=False),
        sa.Column("chat_id", sa.String(length=255), nullable=False),
        sa.Column("business_connection_id", sa.String(length=255), nullable=True),
        sa.Column("message_thread_id", sa.BigInteger(), nullable=True),
        sa.Column("bot_id", sa.BigInteger(), nullable=True),
        sa.Column("state", sa.String(length=255), nullable=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_conversation_state_storage_key"),
    )

    bind = op.get_bind()
    now = datetime.utcnow()

    user_identity_table = sa.table(
        "user_identity",
        sa.column("user_id", sa.Integer()),
        sa.column("provider", sa.String()),
        sa.column("external_user_id", sa.String()),
        sa.column("payload", sa.JSON()),
        sa.column("created_at", sa.DateTime()),
        sa.column("last_seen_at", sa.DateTime()),
    )
    volunteer_identity_table = sa.table(
        "volunteer_identity",
        sa.column("volunteer_id", sa.Integer()),
        sa.column("provider", sa.String()),
        sa.column("external_user_id", sa.String()),
        sa.column("payload", sa.JSON()),
        sa.column("created_at", sa.DateTime()),
        sa.column("last_seen_at", sa.DateTime()),
    )
    blocked_identity_event_table = sa.table(
        "blocked_identity_event",
        sa.column("user_id", sa.Integer()),
        sa.column("provider", sa.String()),
        sa.column("external_user_id", sa.String()),
        sa.column("blocked_at", sa.DateTime()),
        sa.column("payload", sa.JSON()),
    )
    platform_role_table = sa.table(
        "platform_role",
        sa.column("provider", sa.String()),
        sa.column("external_user_id", sa.String()),
        sa.column("role", sa.String()),
        sa.column("payload", sa.JSON()),
        sa.column("granted_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )

    user_rows = bind.execute(sa.text('SELECT id, tg_id FROM "user" WHERE tg_id IS NOT NULL')).fetchall()
    if user_rows:
        op.bulk_insert(
            user_identity_table,
            [
                {
                    "user_id": row.id,
                    "provider": "telegram",
                    "external_user_id": str(row.tg_id),
                    "payload": None,
                    "created_at": now,
                    "last_seen_at": now,
                }
                for row in user_rows
            ],
        )

    volunteer_rows = bind.execute(sa.text('SELECT id, tg_id, name FROM user_volunteer WHERE tg_id IS NOT NULL')).fetchall()
    if volunteer_rows:
        op.bulk_insert(
            volunteer_identity_table,
            [
                {
                    "volunteer_id": row.id,
                    "provider": "telegram",
                    "external_user_id": str(row.tg_id),
                    "payload": {"name": row.name} if row.name else None,
                    "created_at": now,
                    "last_seen_at": now,
                }
                for row in volunteer_rows
            ],
        )

    blocked_rows = bind.execute(
        sa.text('SELECT tg_id, blocked_at FROM user_who_blocked WHERE tg_id IS NOT NULL')
    ).fetchall()
    if blocked_rows:
        op.bulk_insert(
            blocked_identity_event_table,
            [
                {
                    "user_id": None,
                    "provider": "telegram",
                    "external_user_id": str(row.tg_id),
                    "blocked_at": row.blocked_at or now,
                    "payload": {"source": "user_who_blocked"},
                }
                for row in blocked_rows
            ],
        )

    role_rows = []
    for role_name, external_ids in {
        "admin": {9958633101, 2693757140, 1632759029, 269375714, 6472120438},
        "superadmin": {995863310, 2693757140, 1632759029, 269375714},
        "developer": {1632759029},
    }.items():
        for external_id in external_ids:
            role_rows.append(
                {
                    "provider": "telegram",
                    "external_user_id": str(external_id),
                    "role": role_name,
                    "payload": {"source": "legacy_vars"},
                    "granted_at": now,
                    "updated_at": now,
                }
            )

    if role_rows:
        op.bulk_insert(platform_role_table, role_rows)


def downgrade() -> None:
    op.drop_table("conversation_state")
    op.drop_table("blocked_identity_event")
    op.drop_table("platform_role")
    op.drop_table("volunteer_identity")
    op.drop_table("user_identity")

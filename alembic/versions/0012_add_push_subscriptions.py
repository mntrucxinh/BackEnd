"""add push subscriptions table

Revision ID: 0012_add_push_subscriptions
Revises: 0011_add_facebook_fields
Create Date: 2026-01-07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0012_add_push_subscriptions"
down_revision = "0011_add_facebook_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("endpoint", sa.Text(), nullable=False, unique=True),
        sa.Column("p256dh", sa.Text(), nullable=False),
        sa.Column("auth", sa.Text(), nullable=False),
        sa.Column("expiration_time", sa.BigInteger(), nullable=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "push_subscriptions_created_at_idx",
        "push_subscriptions",
        [sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("push_subscriptions_created_at_idx", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")

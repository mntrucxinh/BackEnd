"""add_local_to_embed_provider

Revision ID: 0013_add_local_to_embed_provider
Revises: 0012_add_push_subscriptions
Create Date: 2026-01-XX XX:XX:XX.XXXXXX

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0013_add_local_to_embed_provider'
down_revision = '0012_add_push_subscriptions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add 'local' value to embed_provider enum
    op.execute("ALTER TYPE embed_provider ADD VALUE IF NOT EXISTS 'local'")


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing enum values directly
    # This would require recreating the enum, which is complex
    # For now, we'll leave it as is
    pass


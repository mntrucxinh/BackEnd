"""Add Facebook integration fields to users."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0011_add_facebook_fields"
down_revision: Union[str, None] = "0010_store_app_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Facebook User Token (Long-lived, 60 days)
    op.add_column("users", sa.Column("facebook_user_access_token", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "facebook_user_token_expires_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    
    # Facebook Page Token
    op.add_column("users", sa.Column("facebook_page_id", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("facebook_access_token", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "facebook_token_expires_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column("users", sa.Column("facebook_page_name", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "facebook_page_name")
    op.drop_column("users", "facebook_token_expires_at")
    op.drop_column("users", "facebook_access_token")
    op.drop_column("users", "facebook_page_id")
    op.drop_column("users", "facebook_user_token_expires_at")
    op.drop_column("users", "facebook_user_access_token")


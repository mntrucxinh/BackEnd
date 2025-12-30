"""Add Google access token fields to users."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0008_google_access_token"
down_revision: Union[str, None] = "0007_drop_role_lastlogin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_access_token", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("google_access_token_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "google_access_token_expires_at")
    op.drop_column("users", "google_access_token")

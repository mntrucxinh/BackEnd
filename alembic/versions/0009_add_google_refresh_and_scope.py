"""Add Google refresh token and scope fields to users."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0009_google_refresh_scope"
down_revision: Union[str, None] = "0008_google_access_token"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_refresh_token", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("google_token_scope", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "google_token_scope")
    op.drop_column("users", "google_refresh_token")

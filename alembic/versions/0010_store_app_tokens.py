"""Store app access/refresh tokens and drop unused Google refresh/scope."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0010_store_app_tokens"
down_revision: Union[str, None] = "0009_google_refresh_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("users", "google_refresh_token")
    op.drop_column("users", "google_token_scope")
    op.add_column("users", sa.Column("access_token", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("refresh_token", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "refresh_token")
    op.drop_column("users", "access_token")
    op.add_column("users", sa.Column("google_token_scope", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("google_refresh_token", sa.Text(), nullable=True))

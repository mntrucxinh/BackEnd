"""Add Google auth fields to users (sub, id_token, expiry)."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0006_google_auth_fields"
down_revision: Union[str, None] = "0005_user_cols_trim"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_sub", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("google_id_token", sa.Text(), nullable=True))
    op.add_column(
        "users",
        sa.Column("google_id_token_expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_unique_constraint("uq_users_google_sub", "users", ["google_sub"])


def downgrade() -> None:
    op.drop_constraint("uq_users_google_sub", "users", type_="unique")
    op.drop_column("users", "google_id_token_expires_at")
    op.drop_column("users", "google_id_token")
    op.drop_column("users", "google_sub")

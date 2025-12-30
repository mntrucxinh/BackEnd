"""Drop login_attempts table."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0003_drop_login_attempts"
down_revision: Union[str, None] = "0002_add_post_assets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop indexes first to be explicit, then drop the table
    op.drop_index("login_attempts_ip_time_idx", table_name="login_attempts")
    op.drop_index("login_attempts_email_time_idx", table_name="login_attempts")
    op.drop_table("login_attempts")


def downgrade() -> None:
    op.create_table(
        "login_attempts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("email", postgresql.CITEXT()),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("ip", postgresql.INET()),
        sa.Column("user_agent", sa.Text()),
        sa.Column(
            "success",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "login_attempts_email_time_idx",
        "login_attempts",
        ["email", sa.text("created_at DESC")],
    )
    op.create_index(
        "login_attempts_ip_time_idx",
        "login_attempts",
        ["ip", sa.text("created_at DESC")],
    )

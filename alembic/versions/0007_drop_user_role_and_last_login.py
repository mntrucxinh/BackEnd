"""Drop role and last_login_at from users; remove user_role enum."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0007_drop_role_lastlogin"
down_revision: Union[str, None] = "0006_google_auth_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("users", "role")
    op.drop_column("users", "last_login_at")
    # Drop enum type no longer used
    op.execute("DROP TYPE IF EXISTS user_role")


def downgrade() -> None:
    # Recreate enum and columns
    op.execute("CREATE TYPE user_role AS ENUM ('admin')")

    op.add_column(
        "users",
        sa.Column(
            "role",
            postgresql.ENUM("admin", name="user_role", create_type=False),
            nullable=False,
            server_default=sa.text("'admin'::user_role"),
        ),
    )
    op.add_column(
        "users",
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

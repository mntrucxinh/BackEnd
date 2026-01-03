"""Remove editor role from user_role enum (only admin remains)."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0004_remove_editor_role"
down_revision: Union[str, None] = "0003_drop_login_attempts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Ensure no editor role remains
    op.execute("UPDATE users SET role = 'admin' WHERE role = 'editor'")

    # Recreate enum without editor
    op.execute("ALTER TYPE user_role RENAME TO user_role_old")
    op.execute("CREATE TYPE user_role AS ENUM ('admin')")

    op.execute("ALTER TABLE users ALTER COLUMN role DROP DEFAULT")
    op.execute(
        "ALTER TABLE users ALTER COLUMN role TYPE user_role USING role::text::user_role"
    )
    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'admin'::user_role")

    op.execute("DROP TYPE user_role_old")


def downgrade() -> None:
    # Recreate enum with editor value restored
    op.execute("ALTER TYPE user_role RENAME TO user_role_old")
    op.execute("CREATE TYPE user_role AS ENUM ('admin', 'editor')")

    op.execute("ALTER TABLE users ALTER COLUMN role DROP DEFAULT")
    op.execute(
        "ALTER TABLE users ALTER COLUMN role TYPE user_role USING role::text::user_role"
    )
    op.execute("ALTER TABLE users ALTER COLUMN role SET DEFAULT 'editor'::user_role")

    op.execute("DROP TYPE user_role_old")

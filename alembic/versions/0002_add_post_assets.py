"""Add post_assets table for multiple images in posts."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_add_post_assets"
down_revision: Union[str, None] = "0001_init"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "post_assets",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "post_id",
            sa.BigInteger(),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            sa.BigInteger(),
            sa.ForeignKey("assets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "position",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("caption", sa.Text()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "post_id", "position", name="uq_post_assets_post_pos"
        ),
        sa.UniqueConstraint(
            "post_id", "asset_id", name="uq_post_assets_post_asset"
        ),
    )
    op.create_index(
        "post_assets_post_pos_idx", "post_assets", ["post_id", "position"]
    )


def downgrade() -> None:
    op.drop_index("post_assets_post_pos_idx", table_name="post_assets")
    op.drop_table("post_assets")


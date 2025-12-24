"""Initial schema for preschool website."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0001_init"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # Create enums using DO block to check existence first
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE user_role AS ENUM ('admin', 'editor');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE post_type AS ENUM ('news', 'announcement');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE content_status AS ENUM ('draft', 'published', 'archived');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE job_type AS ENUM ('post_to_facebook');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE job_status AS ENUM ('queued', 'processing', 'succeeded', 'failed', 'dead');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE embed_provider AS ENUM ('youtube', 'facebook');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE contact_status AS ENUM ('new', 'handled', 'spam');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
    """)

    # Define enum types for SQLAlchemy to use in table definitions
    user_role = postgresql.ENUM("admin", "editor", name="user_role", create_type=False)
    post_type = postgresql.ENUM("news", "announcement", name="post_type", create_type=False)
    content_status = postgresql.ENUM("draft", "published", "archived", name="content_status", create_type=False)
    job_type = postgresql.ENUM("post_to_facebook", name="job_type", create_type=False)
    job_status = postgresql.ENUM(
        "queued", "processing", "succeeded", "failed", "dead", name="job_status", create_type=False
    )
    embed_provider = postgresql.ENUM("youtube", "facebook", name="embed_provider", create_type=False)
    contact_status = postgresql.ENUM("new", "handled", "spam", name="contact_status", create_type=False)

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column(
            "role",
            user_role,
            nullable=False,
            server_default=sa.text("'editor'::user_role"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("public_id", name="uq_users_public_id"),
    )

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

    op.create_table(
        "assets",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("storage", sa.Text(), nullable=False),
        sa.Column("bucket", sa.Text()),
        sa.Column("object_key", sa.Text()),
        sa.Column("url", sa.Text()),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.BigInteger()),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("checksum", sa.Text()),
        sa.Column(
            "uploaded_by",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True)),
        sa.UniqueConstraint("public_id", name="uq_assets_public_id"),
    )
    op.create_index(
        "assets_created_at_idx", "assets", [sa.text("created_at DESC")]
    )

    op.create_table(
        "blocks",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("TRUE"),
        ),
        sa.UniqueConstraint("code", name="uq_blocks_code"),
    )

    op.create_table(
        "posts",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("type", post_type, nullable=False),
        sa.Column(
            "status",
            content_status,
            nullable=False,
            server_default=sa.text("'draft'::content_status"),
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("excerpt", sa.Text()),
        sa.Column("content_html", sa.Text(), nullable=False),
        sa.Column(
            "cover_asset_id",
            sa.BigInteger(),
            sa.ForeignKey("assets.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "og_image_asset_id",
            sa.BigInteger(),
            sa.ForeignKey("assets.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "block_id",
            sa.BigInteger(),
            sa.ForeignKey("blocks.id", ondelete="RESTRICT"),
        ),
        sa.Column("meta_title", sa.Text()),
        sa.Column("meta_description", sa.Text()),
        sa.Column(
            "author_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("published_at", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("search_tsv", postgresql.TSVECTOR()),
        sa.CheckConstraint(
            "((type = 'announcement') AND (block_id IS NOT NULL)) OR "
            "((type = 'news') AND (block_id IS NULL))",
            name="ck_posts_block_id_by_type",
        ),
        sa.UniqueConstraint("public_id", name="uq_posts_public_id"),
    )
    op.create_index(
        "uq_posts_type_slug_active",
        "posts",
        ["type", "slug"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "posts_list_news_idx",
        "posts",
        ["type", "status", sa.text("published_at DESC")],
        postgresql_where=sa.text("type='news' AND deleted_at IS NULL"),
    )
    op.create_index(
        "posts_list_announcement_idx",
        "posts",
        ["type", "block_id", "status", sa.text("published_at DESC")],
        postgresql_where=sa.text("type='announcement' AND deleted_at IS NULL"),
    )
    op.create_index(
        "posts_search_tsv_gin",
        "posts",
        ["search_tsv"],
        postgresql_using="gin",
    )

    op.create_table(
        "post_revisions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "post_id",
            sa.BigInteger(),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "editor_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("excerpt", sa.Text()),
        sa.Column("content_html", sa.Text(), nullable=False),
        sa.Column(
            "cover_asset_id",
            sa.BigInteger(),
            sa.ForeignKey("assets.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "post_revisions_post_time_idx",
        "post_revisions",
        ["post_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "albums",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column(
            "cover_asset_id",
            sa.BigInteger(),
            sa.ForeignKey("assets.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "status",
            content_status,
            nullable=False,
            server_default=sa.text("'published'::content_status"),
        ),
        sa.Column(
            "created_by",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True)),
        sa.UniqueConstraint("public_id", name="uq_albums_public_id"),
    )
    op.create_index(
        "uq_albums_slug_active",
        "albums",
        ["slug"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "albums_list_idx",
        "albums",
        ["status", sa.text("created_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "album_items",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "album_id",
            sa.BigInteger(),
            sa.ForeignKey("albums.id", ondelete="CASCADE"),
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
            "album_id", "position", name="uq_album_items_album_pos"
        ),
        sa.UniqueConstraint(
            "album_id", "asset_id", name="uq_album_items_album_asset"
        ),
    )
    op.create_index(
        "album_items_album_pos_idx", "album_items", ["album_id", "position"]
    )

    op.create_table(
        "video_embeds",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "public_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("provider", embed_provider, nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("thumbnail_url", sa.Text()),
        sa.Column(
            "created_by",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("public_id", name="uq_video_embeds_public_id"),
    )

    op.create_table(
        "album_videos",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "album_id",
            sa.BigInteger(),
            sa.ForeignKey("albums.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "video_id",
            sa.BigInteger(),
            sa.ForeignKey("video_embeds.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "position",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.UniqueConstraint(
            "album_id", "position", name="uq_album_videos_album_pos"
        ),
        sa.UniqueConstraint(
            "album_id", "video_id", name="uq_album_videos_album_vid"
        ),
    )
    op.create_index(
        "album_videos_album_pos_idx", "album_videos", ["album_id", "position"]
    )

    op.create_table(
        "jobs_outbox",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "type",
            job_type,
            nullable=False,
            server_default=sa.text("'post_to_facebook'::job_type"),
        ),
        sa.Column(
            "status",
            job_status,
            nullable=False,
            server_default=sa.text("'queued'::job_status"),
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "run_after",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("locked_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("locked_by", sa.Text()),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_error", sa.Text()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "jobs_outbox_pick_idx",
        "jobs_outbox",
        ["status", "run_after", "id"],
        postgresql_where=sa.text("status IN ('queued','failed')"),
    )

    op.create_table(
        "facebook_post_log",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "post_id",
            sa.BigInteger(),
            sa.ForeignKey("posts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            job_status,
            nullable=False,
            server_default=sa.text("'queued'::job_status"),
        ),
        sa.Column("fb_post_id", sa.Text()),
        sa.Column("request_payload", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("response_payload", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("error_message", sa.Text()),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_attempt_at", sa.TIMESTAMP(timezone=True)),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("post_id", name="uq_facebook_post_log_post_id"),
    )
    op.create_index(
        "facebook_post_log_status_idx",
        "facebook_post_log",
        ["status", sa.text("updated_at DESC")],
    )

    op.create_table(
        "contact_messages",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text()),
        sa.Column("email", postgresql.CITEXT()),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "status",
            contact_status,
            nullable=False,
            server_default=sa.text("'new'::contact_status"),
        ),
        sa.Column("ip", postgresql.INET()),
        sa.Column("user_agent", sa.Text()),
        sa.Column("spam_score", sa.REAL()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "contact_messages_status_time_idx",
        "contact_messages",
        ["status", sa.text("created_at DESC")],
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "actor_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.BigInteger()),
        sa.Column("diff", postgresql.JSONB(astext_type=sa.Text())),
        sa.Column("ip", postgresql.INET()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "audit_log_entity_idx",
        "audit_log",
        ["entity_type", "entity_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("audit_log_entity_idx", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index(
        "contact_messages_status_time_idx", table_name="contact_messages"
    )
    op.drop_table("contact_messages")

    op.drop_index("facebook_post_log_status_idx", table_name="facebook_post_log")
    op.drop_table("facebook_post_log")

    op.drop_index("jobs_outbox_pick_idx", table_name="jobs_outbox")
    op.drop_table("jobs_outbox")

    op.drop_index("album_videos_album_pos_idx", table_name="album_videos")
    op.drop_table("album_videos")

    op.drop_table("video_embeds")

    op.drop_index("album_items_album_pos_idx", table_name="album_items")
    op.drop_table("album_items")

    op.drop_index("albums_list_idx", table_name="albums")
    op.drop_table("albums")

    op.drop_index(
        "post_revisions_post_time_idx", table_name="post_revisions"
    )
    op.drop_table("post_revisions")

    op.drop_index("posts_search_tsv_gin", table_name="posts")
    op.drop_index("posts_list_announcement_idx", table_name="posts")
    op.drop_index("posts_list_news_idx", table_name="posts")
    op.drop_table("posts")

    op.drop_table("blocks")

    op.drop_index("assets_created_at_idx", table_name="assets")
    op.drop_table("assets")

    op.drop_index("login_attempts_ip_time_idx", table_name="login_attempts")
    op.drop_index("login_attempts_email_time_idx", table_name="login_attempts")
    op.drop_table("login_attempts")

    op.drop_table("users")

    contact_status = sa.Enum("new", "handled", "spam", name="contact_status")
    embed_provider = sa.Enum("youtube", "facebook", name="embed_provider")
    job_status = sa.Enum(
        "queued", "processing", "succeeded", "failed", "dead", name="job_status"
    )
    job_type = sa.Enum("post_to_facebook", name="job_type")
    content_status = sa.Enum("draft", "published", "archived", name="content_status")
    post_type = sa.Enum("news", "announcement", name="post_type")
    user_role = sa.Enum("admin", "editor", name="user_role")

    bind = op.get_bind()
    contact_status.drop(bind, checkfirst=True)
    embed_provider.drop(bind, checkfirst=True)
    job_status.drop(bind, checkfirst=True)
    job_type.drop(bind, checkfirst=True)
    content_status.drop(bind, checkfirst=True)
    post_type.drop(bind, checkfirst=True)
    user_role.drop(bind, checkfirst=True)

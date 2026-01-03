import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import CITEXT, INET, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .enums import (
    ContactStatus,
    ContentStatus,
    EmbedProvider,
    JobStatus,
    JobType,
    PostType,
)

post_type_enum = sa.Enum(
    PostType,
    name="post_type",
    values_callable=lambda enum_cls: [e.value for e in enum_cls],
)
content_status_enum = sa.Enum(
    ContentStatus,
    name="content_status",
    values_callable=lambda enum_cls: [e.value for e in enum_cls],
)
job_type_enum = sa.Enum(
    JobType,
    name="job_type",
    values_callable=lambda enum_cls: [e.value for e in enum_cls],
)
job_status_enum = sa.Enum(
    JobStatus,
    name="job_status",
    values_callable=lambda enum_cls: [e.value for e in enum_cls],
)
embed_provider_enum = sa.Enum(
    EmbedProvider,
    name="embed_provider",
    values_callable=lambda enum_cls: [e.value for e in enum_cls],
)
contact_status_enum = sa.Enum(
    ContactStatus,
    name="contact_status",
    values_callable=lambda enum_cls: [e.value for e in enum_cls],
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(CITEXT(), unique=True, nullable=False)
    google_sub: Mapped[Optional[str]] = mapped_column(
        sa.Text, unique=True, nullable=True
    )
    google_id_token: Mapped[Optional[str]] = mapped_column(sa.Text)
    google_id_token_expires_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True)
    )
    google_access_token: Mapped[Optional[str]] = mapped_column(sa.Text)
    google_access_token_expires_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True)
    )
    google_refresh_token: Mapped[Optional[str]] = mapped_column(sa.Text)
    google_token_scope: Mapped[Optional[str]] = mapped_column(sa.Text)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (sa.Index("assets_created_at_idx", sa.text("created_at DESC")),)

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    storage: Mapped[str] = mapped_column(sa.Text, nullable=False)
    bucket: Mapped[Optional[str]] = mapped_column(sa.Text)
    object_key: Mapped[Optional[str]] = mapped_column(sa.Text)
    url: Mapped[Optional[str]] = mapped_column(sa.Text)
    mime_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    byte_size: Mapped[Optional[int]] = mapped_column(sa.BigInteger)
    width: Mapped[Optional[int]] = mapped_column(sa.Integer)
    height: Mapped[Optional[int]] = mapped_column(sa.Integer)
    checksum: Mapped[Optional[str]] = mapped_column(sa.Text)
    uploaded_by: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    deleted_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True)
    )


class Block(Base):
    __tablename__ = "blocks"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    code: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=text("0")
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default=text("TRUE")
    )


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        sa.Index(
            "uq_posts_type_slug_active",
            "type",
            "slug",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        sa.CheckConstraint(
            "((type = 'announcement') AND (block_id IS NOT NULL)) OR "
            "((type = 'news') AND (block_id IS NULL))",
            name="ck_posts_block_id_by_type",
        ),
        sa.Index(
            "posts_list_news_idx",
            "type",
            "status",
            sa.text("published_at DESC"),
            postgresql_where=text("type='news' AND deleted_at IS NULL"),
        ),
        sa.Index(
            "posts_list_announcement_idx",
            "type",
            "block_id",
            "status",
            sa.text("published_at DESC"),
            postgresql_where=text("type='announcement' AND deleted_at IS NULL"),
        ),
        sa.Index(
            "posts_search_tsv_gin",
            "search_tsv",
            postgresql_using="gin",
        ),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    post_type: Mapped[PostType] = mapped_column(
        "type",
        post_type_enum,
        nullable=False,
    )
    status: Mapped[ContentStatus] = mapped_column(
        content_status_enum, nullable=False, server_default=ContentStatus.DRAFT.value
    )
    title: Mapped[str] = mapped_column(sa.Text, nullable=False)
    slug: Mapped[str] = mapped_column(sa.Text, nullable=False)
    excerpt: Mapped[Optional[str]] = mapped_column(sa.Text)
    content_html: Mapped[str] = mapped_column(sa.Text, nullable=False)
    cover_asset_id: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("assets.id", ondelete="SET NULL")
    )
    og_image_asset_id: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("assets.id", ondelete="SET NULL")
    )
    block_id: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("blocks.id", ondelete="RESTRICT")
    )
    meta_title: Mapped[Optional[str]] = mapped_column(sa.Text)
    meta_description: Mapped[Optional[str]] = mapped_column(sa.Text)
    author_id: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL")
    )
    published_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True)
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    deleted_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True)
    )
    search_tsv: Mapped[Optional[str]] = mapped_column(TSVECTOR)


class PostRevision(Base):
    __tablename__ = "post_revisions"
    __table_args__ = (
        sa.Index(
            "post_revisions_post_time_idx",
            "post_id",
            sa.text("created_at DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    post_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    editor_id: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(sa.Text, nullable=False)
    excerpt: Mapped[Optional[str]] = mapped_column(sa.Text)
    content_html: Mapped[str] = mapped_column(sa.Text, nullable=False)
    cover_asset_id: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("assets.id", ondelete="SET NULL")
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class PostAsset(Base):
    __tablename__ = "post_assets"
    __table_args__ = (
        sa.UniqueConstraint("post_id", "position", name="uq_post_assets_post_pos"),
        sa.UniqueConstraint("post_id", "asset_id", name="uq_post_assets_post_asset"),
        sa.Index("post_assets_post_pos_idx", "post_id", "position"),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    post_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False
    )
    position: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=text("0")
    )
    caption: Mapped[Optional[str]] = mapped_column(sa.Text)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class Album(Base):
    __tablename__ = "albums"
    __table_args__ = (
        sa.Index(
            "uq_albums_slug_active",
            "slug",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        sa.Index(
            "albums_list_idx",
            "status",
            sa.text("created_at DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    title: Mapped[str] = mapped_column(sa.Text, nullable=False)
    slug: Mapped[str] = mapped_column(sa.Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.Text)
    cover_asset_id: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("assets.id", ondelete="SET NULL")
    )
    status: Mapped[ContentStatus] = mapped_column(
        content_status_enum, nullable=False, server_default=ContentStatus.PUBLISHED.value
    )
    created_by: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    deleted_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True)
    )


class AlbumItem(Base):
    __tablename__ = "album_items"
    __table_args__ = (
        sa.UniqueConstraint("album_id", "position", name="uq_album_items_album_pos"),
        sa.UniqueConstraint("album_id", "asset_id", name="uq_album_items_album_asset"),
        sa.Index("album_items_album_pos_idx", "album_id", "position"),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    album_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("albums.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("assets.id", ondelete="RESTRICT"), nullable=False
    )
    position: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=text("0")
    )
    caption: Mapped[Optional[str]] = mapped_column(sa.Text)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class VideoEmbed(Base):
    __tablename__ = "video_embeds"

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    public_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        unique=True,
        nullable=False,
        server_default=text("gen_random_uuid()"),
    )
    provider: Mapped[EmbedProvider] = mapped_column(
        embed_provider_enum, nullable=False
    )
    url: Mapped[str] = mapped_column(sa.Text, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(sa.Text)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(sa.Text)
    created_by: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class AlbumVideo(Base):
    __tablename__ = "album_videos"
    __table_args__ = (
        sa.UniqueConstraint("album_id", "position", name="uq_album_videos_album_pos"),
        sa.UniqueConstraint("album_id", "video_id", name="uq_album_videos_album_vid"),
        sa.Index("album_videos_album_pos_idx", "album_id", "position"),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    album_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("albums.id", ondelete="CASCADE"), nullable=False
    )
    video_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey("video_embeds.id", ondelete="RESTRICT"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=text("0")
    )


class JobOutbox(Base):
    __tablename__ = "jobs_outbox"
    __table_args__ = (
        sa.Index(
            "jobs_outbox_pick_idx",
            "status",
            "run_after",
            "id",
            postgresql_where=text("status IN ('queued','failed')"),
        ),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    job_type: Mapped[JobType] = mapped_column(
        "type",
        job_type_enum,
        nullable=False,
        server_default=JobType.POST_TO_FACEBOOK.value,
    )
    status: Mapped[JobStatus] = mapped_column(
        job_status_enum,
        nullable=False,
        server_default=JobStatus.QUEUED.value,
    )
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    run_after: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    locked_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True)
    )
    locked_by: Mapped[Optional[str]] = mapped_column(sa.Text)
    attempt_count: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=text("0")
    )
    last_error: Mapped[Optional[str]] = mapped_column(sa.Text)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class FacebookPostLog(Base):
    __tablename__ = "facebook_post_log"
    __table_args__ = (
        sa.UniqueConstraint("post_id", name="uq_facebook_post_log_post_id"),
        sa.Index(
            "facebook_post_log_status_idx",
            "status",
            sa.text("updated_at DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    post_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[JobStatus] = mapped_column(
        job_status_enum, nullable=False, server_default=JobStatus.QUEUED.value
    )
    fb_post_id: Mapped[Optional[str]] = mapped_column(sa.Text)
    request_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    response_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    error_message: Mapped[Optional[str]] = mapped_column(sa.Text)
    attempt_count: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, server_default=text("0")
    )
    last_attempt_at: Mapped[Optional[sa.DateTime]] = mapped_column(
        sa.TIMESTAMP(timezone=True)
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class ContactMessage(Base):
    __tablename__ = "contact_messages"
    __table_args__ = (
        sa.Index(
            "contact_messages_status_time_idx",
            "status",
            sa.text("created_at DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    full_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(sa.Text)
    email: Mapped[Optional[str]] = mapped_column(CITEXT())
    message: Mapped[str] = mapped_column(sa.Text, nullable=False)
    status: Mapped[ContactStatus] = mapped_column(
        contact_status_enum, nullable=False, server_default=ContactStatus.NEW.value
    )
    ip: Mapped[Optional[str]] = mapped_column(INET)
    user_agent: Mapped[Optional[str]] = mapped_column(sa.Text)
    spam_score: Mapped[Optional[float]] = mapped_column(sa.REAL)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        sa.Index(
            "audit_log_entity_idx",
            "entity_type",
            "entity_id",
            sa.text("created_at DESC"),
        ),
    )

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True)
    actor_id: Mapped[Optional[int]] = mapped_column(
        sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(sa.Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    entity_id: Mapped[Optional[int]] = mapped_column(sa.BigInteger)
    diff: Mapped[Optional[dict]] = mapped_column(JSONB)
    ip: Mapped[Optional[str]] = mapped_column(INET)
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

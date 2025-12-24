import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    EDITOR = "editor"


class PostType(str, enum.Enum):
    NEWS = "news"
    ANNOUNCEMENT = "announcement"


class ContentStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class JobType(str, enum.Enum):
    POST_TO_FACEBOOK = "post_to_facebook"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD = "dead"


class EmbedProvider(str, enum.Enum):
    YOUTUBE = "youtube"
    FACEBOOK = "facebook"


class ContactStatus(str, enum.Enum):
    NEW = "new"
    HANDLED = "handled"
    SPAM = "spam"

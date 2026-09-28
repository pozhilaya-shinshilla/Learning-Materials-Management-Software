from enum import StrEnum


class Role(StrEnum):
    """User role in the role-based access model."""

    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


class AccountStatus(StrEnum):
    """Lifecycle status of a user account."""

    ACTIVE = "active"
    BLOCKED = "blocked"


class FileType(StrEnum):
    """File formats supported for teaching materials."""

    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    JPG = "jpg"
    PNG = "png"


class EventType(StrEnum):
    """Types of events written to the system event log."""

    USER_LOGGED_IN = "user_logged_in"
    USER_LOGIN_FAILED = "user_login_failed"
    USER_LOGGED_OUT = "user_logged_out"
    MATERIAL_CREATED = "material_created"
    MATERIAL_EDITED = "material_edited"
    MATERIAL_DELETED = "material_deleted"
    MATERIAL_DOWNLOADED = "material_downloaded"
    FILE_UPLOADED = "file_uploaded"
    FAVORITE_ADDED = "favorite_added"
    FAVORITE_REMOVED = "favorite_removed"
    DISCIPLINE_CREATED = "discipline_created"
    TOPIC_CREATED = "topic_created"
    USER_ACCOUNT_CHANGED = "user_account_changed"
    USER_ROLE_CHANGED = "user_role_changed"
    USER_BLOCKED = "user_blocked"
    USER_UNBLOCKED = "user_unblocked"
    PASSWORD_RESET_REQUESTED = "password_reset_requested"
    PASSWORD_RESET = "password_reset"


class SortField(StrEnum):
    """Fields that material listings can be sorted by."""

    UPLOAD_DATE = "upload_date"
    TITLE = "title"


class SortOrder(StrEnum):
    """Sort direction for material listings."""

    ASCENDING = "asc"
    DESCENDING = "desc"

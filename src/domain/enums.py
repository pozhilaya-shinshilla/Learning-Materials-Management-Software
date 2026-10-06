"""Перечисления предметной области.

У каждого значения есть машинное имя (`value`, английское — оно хранится и
сравнивается в коде) и человекочитаемая подпись (`label`, русская — её
показывает интерфейс). Так CLI не приходится дублировать переводы у себя.
"""

from enum import StrEnum


class Role(StrEnum):
    """Роль пользователя в ролевой модели доступа."""

    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"

    @property
    def label(self) -> str:
        """Название роли для показа пользователю."""
        return {
            Role.STUDENT: "студент",
            Role.TEACHER: "преподаватель",
            Role.ADMIN: "администратор",
        }[self]


class AccountStatus(StrEnum):
    """Статус учётной записи."""

    ACTIVE = "active"
    BLOCKED = "blocked"

    @property
    def label(self) -> str:
        """Название статуса для показа пользователю."""
        return {
            AccountStatus.ACTIVE: "активен",
            AccountStatus.BLOCKED: "заблокирован",
        }[self]


class FileType(StrEnum):
    """Форматы файлов, поддерживаемые для учебных материалов."""

    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    JPG = "jpg"
    PNG = "png"


class EventType(StrEnum):
    """Типы событий, записываемых в журнал."""

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

    @property
    def label(self) -> str:
        """Описание события для показа пользователю."""
        return _EVENT_LABELS[self]


_EVENT_LABELS: dict[EventType, str] = {
    EventType.USER_LOGGED_IN: "вход в систему",
    EventType.USER_LOGIN_FAILED: "неудачная попытка входа",
    EventType.USER_LOGGED_OUT: "выход из системы",
    EventType.MATERIAL_CREATED: "материал создан",
    EventType.MATERIAL_EDITED: "материал изменён",
    EventType.MATERIAL_DELETED: "материал удалён",
    EventType.MATERIAL_DOWNLOADED: "материал скачан",
    EventType.FILE_UPLOADED: "файл загружен",
    EventType.FAVORITE_ADDED: "добавлено в избранное",
    EventType.FAVORITE_REMOVED: "убрано из избранного",
    EventType.DISCIPLINE_CREATED: "дисциплина создана",
    EventType.TOPIC_CREATED: "тема создана",
    EventType.USER_ACCOUNT_CHANGED: "изменена учётная запись",
    EventType.USER_ROLE_CHANGED: "изменена роль пользователя",
    EventType.USER_BLOCKED: "пользователь заблокирован",
    EventType.USER_UNBLOCKED: "пользователь разблокирован",
    EventType.PASSWORD_RESET_REQUESTED: "запрошен сброс пароля",
    EventType.PASSWORD_RESET: "пароль изменён",
}


class SortField(StrEnum):
    """Поля, по которым можно сортировать список материалов."""

    UPLOAD_DATE = "upload_date"
    TITLE = "title"


class SortOrder(StrEnum):
    """Направление сортировки."""

    ASCENDING = "asc"
    DESCENDING = "desc"

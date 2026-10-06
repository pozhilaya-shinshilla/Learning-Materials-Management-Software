"""Исключения предметной области.

Все нарушения бизнес-правил наследуются от `DomainError`, поэтому интерфейс
ловит один базовый класс и показывает пользователю `str(error)`.

Иерархия:

    DomainError
    ├── AuthenticationError       неверные учётные данные
    ├── AccountBlockedError       учётная запись заблокирована
    ├── AuthorizationError        действие не разрешено роли
    ├── EntityNotFoundError       сущность не найдена
    ├── DuplicateEntityError      сущность с таким именем уже существует
    │   ├── DuplicateLoginError   логин занят
    │   └── DuplicateEmailError   email занят
    └── ValidationError           некорректные входные данные
        ├── UnsupportedFileTypeError   формат файла не разрешён
        ├── FileTooLargeError          файл слишком большой
        └── SourceFileNotFoundError    исходный файл не найден
"""


class DomainError(Exception):
    """Базовый класс всех нарушений бизнес-правил."""


# --- аутентификация и права -------------------------------------------------


class AuthenticationError(DomainError):
    """Неверный логин или пароль."""


class AccountBlockedError(DomainError):
    """Заблокированная учётная запись пытается войти в систему."""


class AuthorizationError(DomainError):
    """Пользователь пытается выполнить действие, недоступное его роли."""


# --- сущности ---------------------------------------------------------------


class EntityNotFoundError(DomainError):
    """Запрошенная сущность отсутствует в хранилище."""


class DuplicateEntityError(DomainError):
    """Сущность с таким уникальным значением уже существует."""


class DuplicateLoginError(DuplicateEntityError):
    """Логин уже занят другой учётной записью."""


class DuplicateEmailError(DuplicateEntityError):
    """Email уже используется другой учётной записью."""


# --- проверка входных данных ------------------------------------------------


class ValidationError(DomainError):
    """Обязательное поле пусто или значение имеет неверный формат."""


class UnsupportedFileTypeError(ValidationError):
    """Расширение файла не входит в список разрешённых."""


class FileTooLargeError(ValidationError):
    """Размер файла превышает допустимый максимум."""


class SourceFileNotFoundError(ValidationError):
    """Локальный файл по указанному пути не существует."""

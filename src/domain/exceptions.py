"""Исключения предметной области.

Все нарушения бизнес-правил наследуются от `DomainError`, поэтому интерфейс
ловит один базовый класс и показывает пользователю `str(error)`.

Текст ошибки хранится в самом классе — в поле `message`. Места, где ошибка
выбрасывается, текст не передают, а только подставляют значения в шаблон:

    raise DuplicateLoginError(login="ivan")        # «Логин 'ivan' уже занят.»
    raise AuthenticationError()                    # текст уже внутри класса

Иерархия:

    DomainError
    ├── AuthenticationError            неверные учётные данные
    │   └── InvalidResetTokenError     код восстановления пароля недействителен
    ├── AccountBlockedError            учётная запись заблокирована
    ├── AuthorizationError             действие не разрешено роли
    │   ├── CatalogAccessError         управление каталогом
    │   ├── MaterialAccessError        управление материалами
    │   ├── ForeignMaterialAccessError чужой материал
    │   ├── EventLogAccessError        журнал событий
    │   ├── UserManagementAccessError  управление учётными записями
    │   ├── SelfRoleChangeError        смена собственной роли
    │   ├── SelfBlockError             блокировка самого себя
    │   └── SelfDeleteError            удаление самого себя
    ├── EntityNotFoundError            сущность не найдена
    │   ├── UnknownDisciplineError         дисциплина не найдена
    │   ├── UnknownTopicError              тема не найдена
    │   ├── DisciplineNotFoundError        дисциплина не найдена по названию
    │   ├── TopicNotFoundError             тема не найдена по названию
    │   ├── DisciplineNotInListError       дисциплины нет в показанном списке
    │   ├── TopicNotInListError            темы нет в показанном списке
    │   ├── MaterialNotFoundError          материал не найден
    │   ├── MaterialNotInListError         материала нет в показанном списке
    │   ├── MaterialFileNotStoredError     у материала нет сохранённого файла
    │   ├── FavoriteNotFoundError          материала нет в избранном
    │   ├── UserNotFoundError              пользователь не найден
    │   └── UserNotInListError             пользователя нет в показанном списке
    ├── DuplicateEntityError           сущность уже существует
    │   ├── DuplicateLoginError            логин занят
    │   ├── DuplicateEmailError            email занят
    │   ├── DuplicateDisciplineError       дисциплина уже есть
    │   ├── DuplicateTopicError            тема уже есть
    │   └── DuplicateFavoriteError         материал уже в избранном
    └── ValidationError                некорректные входные данные
        ├── EmptyFieldError                обязательное поле пусто
        ├── FieldTooLongError              значение слишком длинное
        ├── LoginRequiredError             не введён логин
        ├── PasswordRequiredError          не введён пароль
        ├── InvalidLoginError              логин неверного формата
        ├── InvalidEmailError              email неверного формата
        ├── PasswordTooShortError          пароль слишком короткий
        ├── NotPositiveIntegerError        ожидалось положительное целое
        ├── InvalidYesNoError              ответ не «да/нет»
        ├── UnknownRoleError               неизвестная роль
        ├── UnknownFileTypeError           неизвестный формат файла
        ├── SameRoleError                  роль не меняется
        ├── NameUnchangedError             новое название совпадает с текущим
        ├── PasswordMismatchError          пароли не совпадают
        ├── InvalidDateError               дата неверного формата
        ├── DateRangeError                 конечная дата раньше начальной
        ├── UnknownSortOptionError         неверный вариант сортировки
        ├── UserAlreadyBlockedError        пользователь уже заблокирован
        ├── UserNotBlockedError            пользователь не заблокирован
        ├── DisciplineDoesNotExistError    выбранной дисциплины нет
        ├── TopicDoesNotExistError         выбранной темы нет
        ├── TopicDisciplineMismatchError   тема из другой дисциплины
        ├── DisciplineNameRequiredError    не введено название дисциплины
        ├── TopicNameRequiredError         не введено название темы
        ├── UnsupportedFileTypeError       формат файла не разрешён
        ├── FileTooLargeError              файл слишком большой
        ├── SourceFileNotFoundError        исходный файл не найден
        ├── SourceFilePathRequiredError    не указан путь к файлу
        ├── NotADirectoryPathError         вместо папки указан файл
        └── DirectoryUnavailableError      папку не удалось открыть или создать
"""

from __future__ import annotations


class DomainError(Exception):
    """Базовый класс всех нарушений бизнес-правил.

    Атрибуты:
        message: шаблон текста ошибки; в нём можно использовать поля
            вида `{login}`, значения для которых передаются при создании.
        details: значения, подставленные в шаблон (удобно для отладки и тестов).
    """

    message: str = "Нарушено бизнес-правило."

    def __init__(self, **details: object) -> None:
        self.details = details
        super().__init__(self.message.format(**details))


# --- аутентификация и права -------------------------------------------------


class AuthenticationError(DomainError):
    """Неверный логин или пароль."""

    message = "Неверный логин или пароль."


class InvalidResetTokenError(AuthenticationError):
    """Код восстановления пароля неверен, уже использован или устарел."""

    message = "Код восстановления недействителен или устарел."


class AccountBlockedError(DomainError):
    """Заблокированная учётная запись пытается войти в систему."""

    message = "Учетная запись заблокирована. Обратитесь к администратору."


class AuthorizationError(DomainError):
    """Пользователь пытается выполнить действие, недоступное его роли."""

    message = "Недостаточно прав для выполнения действия."


class CatalogAccessError(AuthorizationError):
    """Каталог дисциплин и тем пытается менять не преподаватель и не администратор."""

    message = "Только преподаватели и администраторы могут управлять каталогом."


class MaterialAccessError(AuthorizationError):
    """Материалы пытается менять не преподаватель и не администратор."""

    message = "Только преподаватели и администраторы могут управлять материалами."


class ForeignMaterialAccessError(AuthorizationError):
    """Преподаватель пытается изменить или удалить материал другого автора."""

    message = "Преподаватель может изменять только свои материалы."


class EventLogAccessError(AuthorizationError):
    """Журнал событий пытается открыть не администратор."""

    message = "Журнал событий доступен только администратору."


class UserManagementAccessError(AuthorizationError):
    """Учётными записями пытается управлять не администратор."""

    message = "Только администратор может управлять учетными записями."


class SelfRoleChangeError(AuthorizationError):
    """Администратор пытается изменить роль собственной учётной записи."""

    message = "Нельзя изменить роль собственной учетной записи."


class SelfBlockError(AuthorizationError):
    """Администратор пытается заблокировать собственную учётную запись."""

    message = "Нельзя заблокировать собственную учетную запись."


class SelfDeleteError(AuthorizationError):
    """Администратор пытается удалить собственную учётную запись."""

    message = "Нельзя удалить собственную учетную запись."


# --- сущности ---------------------------------------------------------------


class EntityNotFoundError(DomainError):
    """Запрошенная сущность отсутствует в хранилище."""

    message = "Запрошенная запись не найдена."


class UnknownDisciplineError(EntityNotFoundError):
    """Дисциплина с указанным идентификатором отсутствует."""

    message = "Дисциплина не найдена."


class UnknownTopicError(EntityNotFoundError):
    """Тема с указанным идентификатором отсутствует."""

    message = "Тема не найдена."


class DisciplineNotFoundError(EntityNotFoundError):
    """Дисциплины с таким названием нет.

    Поля шаблона: `name` — введённое название, `available` — существующие названия.
    """

    message = "Дисциплина «{name}» не найдена. Доступные дисциплины: {available}."


class TopicNotFoundError(EntityNotFoundError):
    """В дисциплине нет темы с таким названием.

    Поля шаблона: `name` — введённое название, `available` — существующие названия.
    """

    message = "Тема «{name}» не найдена в этой дисциплине. Доступные темы: {available}."


class DisciplineNotInListError(EntityNotFoundError):
    """Введённой дисциплины нет в списке, показанном пользователю.

    Поле шаблона: `name` — введённое название.
    """

    message = "Дисциплина «{name}» не найдена. Введите название из списка."


class TopicNotInListError(EntityNotFoundError):
    """Введённой темы нет в списке, показанном пользователю.

    Поле шаблона: `name` — введённое название.
    """

    message = "Тема «{name}» не найдена. Введите название из списка."


class MaterialNotFoundError(EntityNotFoundError):
    """Материала с таким идентификатором нет.

    Поле шаблона: `material_id`.
    """

    message = "Материал с ID {material_id} не найден."


class MaterialNotInListError(EntityNotFoundError):
    """Введённого ID нет среди материалов, показанных пользователю.

    Поля шаблона: `material_id` — введённый ID, `available_ids` — допустимые ID.
    """

    message = "В списке нет материала с ID {material_id}. Доступные ID: {available_ids}."


class MaterialFileNotStoredError(EntityNotFoundError):
    """У материала нет сохранённого файла."""

    message = "Для этого материала не сохранен файл."


class FavoriteNotFoundError(EntityNotFoundError):
    """Материала нет в избранном пользователя.

    Поле шаблона: `material_id`.
    """

    message = "Материала с ID {material_id} нет в вашем избранном."


class UserNotFoundError(EntityNotFoundError):
    """Пользователя с таким идентификатором нет.

    Поле шаблона: `user_id`.
    """

    message = "Пользователь с ID {user_id} не найден."


class UserNotInListError(EntityNotFoundError):
    """Введённого ID нет среди пользователей, показанных администратору.

    Поля шаблона: `user_id` — введённый ID, `available_ids` — допустимые ID.
    """

    message = "В списке нет пользователя с ID {user_id}. Доступные ID: {available_ids}."


class DuplicateEntityError(DomainError):
    """Сущность с таким уникальным значением уже существует."""

    message = "Такая запись уже существует."


class DuplicateLoginError(DuplicateEntityError):
    """Логин уже занят другой учётной записью.

    Поле шаблона: `login`.
    """

    message = "Логин '{login}' уже занят."


class DuplicateEmailError(DuplicateEntityError):
    """Email уже используется другой учётной записью.

    Поле шаблона: `email`.
    """

    message = "Email '{email}' уже используется другой учетной записью."


class DuplicateDisciplineError(DuplicateEntityError):
    """Дисциплина с таким названием уже существует.

    Поле шаблона: `name`.
    """

    message = "Дисциплина «{name}» уже существует."


class DuplicateTopicError(DuplicateEntityError):
    """Тема с таким названием уже есть в этой дисциплине.

    Поле шаблона: `name`.
    """

    message = "Тема «{name}» уже есть в этой дисциплине."


class DuplicateFavoriteError(DuplicateEntityError):
    """Материал уже находится в избранном пользователя.

    Поле шаблона: `title` — название материала.
    """

    message = "Материал «{title}» уже в избранном."


# --- проверка входных данных ------------------------------------------------


class ValidationError(DomainError):
    """Обязательное поле пусто или значение имеет неверный формат."""

    message = "Введены некорректные данные."


class EmptyFieldError(ValidationError):
    """Обязательное текстовое поле оказалось пустым.

    Поле шаблона: `field_name`.
    """

    message = "Поле «{field_name}» не может быть пустым."


class FieldTooLongError(ValidationError):
    """Текстовое поле длиннее допустимого.

    Поля шаблона: `field_name`, `max_length`.
    """

    message = "Поле «{field_name}» не длиннее {max_length} символов."


class LoginRequiredError(ValidationError):
    """При входе не введён логин."""

    message = "Введите логин."


class PasswordRequiredError(ValidationError):
    """При входе не введён пароль."""

    message = "Введите пароль."


class InvalidLoginError(ValidationError):
    """Логин не соответствует формату."""

    message = "Логин должен быть 3-32 символа: латинские буквы, цифры, '_' или '-'."


class InvalidEmailError(ValidationError):
    """Email не соответствует формату."""

    message = "Некорректный формат email (пример: name@example.org)."


class PasswordTooShortError(ValidationError):
    """Пароль короче минимально допустимой длины.

    Поле шаблона: `min_length`.
    """

    message = "Пароль должен быть не короче {min_length} символов."


class NotPositiveIntegerError(ValidationError):
    """Вместо положительного целого числа введено что-то другое."""

    message = "Нужно ввести положительное целое число."


class InvalidYesNoError(ValidationError):
    """Ответ не похож ни на «да», ни на «нет»."""

    message = "Введите 'y' (да) или 'n' (нет)."


class UnknownRoleError(ValidationError):
    """Такой роли не существует.

    Поле шаблона: `allowed` — допустимые варианты.
    """

    message = "Неизвестная роль. Допустимые варианты: {allowed}."


class UnknownFileTypeError(ValidationError):
    """Введён формат файла, которого нет среди поддерживаемых.

    Поле шаблона: `allowed` — допустимые форматы.
    """

    message = "Неизвестный формат. Допустимые форматы: {allowed}."


class SameRoleError(ValidationError):
    """Пользователю назначают ту роль, которая у него уже есть.

    Поля шаблона: `login`, `role` — название роли для показа.
    """

    message = "У пользователя {login} уже роль «{role}»."


class NameUnchangedError(ValidationError):
    """Новое название совпадает с текущим."""

    message = "Новое название совпадает с текущим."


class PasswordMismatchError(ValidationError):
    """Пароль и его повтор не совпадают."""

    message = "Пароли не совпадают."


class InvalidDateError(ValidationError):
    """Дата введена не в формате ДД.ММ.ГГГГ."""

    message = "Дата должна быть в формате ДД.ММ.ГГГГ (например, 31.12.2026)."


class DateRangeError(ValidationError):
    """Конечная дата периода раньше начальной."""

    message = "Конечная дата не может быть раньше начальной."


class UnknownSortOptionError(ValidationError):
    """Выбран несуществующий вариант сортировки.

    Поле шаблона: `count` — число доступных вариантов.
    """

    message = "Выберите вариант сортировки: число от 1 до {count}."


class UserAlreadyBlockedError(ValidationError):
    """Пытаются заблокировать уже заблокированного пользователя.

    Поле шаблона: `login`.
    """

    message = "Пользователь {login} уже заблокирован."


class UserNotBlockedError(ValidationError):
    """Пытаются разблокировать пользователя, который не заблокирован.

    Поле шаблона: `login`.
    """

    message = "Пользователь {login} не заблокирован."


class DisciplineDoesNotExistError(ValidationError):
    """Для материала указана несуществующая дисциплина."""

    message = "Указанная дисциплина не существует."


class TopicDoesNotExistError(ValidationError):
    """Для материала указана несуществующая тема."""

    message = "Указанная тема не существует."


class TopicDisciplineMismatchError(ValidationError):
    """Тема принадлежит другой дисциплине."""

    message = "Тема не относится к выбранной дисциплине."


class DisciplineNameRequiredError(ValidationError):
    """При выборе дисциплины из списка ничего не введено."""

    message = "Введите название дисциплины из списка."


class TopicNameRequiredError(ValidationError):
    """При выборе темы из списка ничего не введено."""

    message = "Введите название темы из списка."


class UnsupportedFileTypeError(ValidationError):
    """Расширение файла не входит в список разрешённых.

    Поля шаблона: `shown` — расширение для показа (например, '.exe'
    или «без расширения»), `allowed` — допустимые форматы.
    """

    message = "Формат {shown} не поддерживается. Допустимые форматы: {allowed}."


class FileTooLargeError(ValidationError):
    """Размер файла превышает допустимый максимум.

    Поле шаблона: `max_mb` — предел в мегабайтах.
    """

    message = "Файл превышает максимально допустимый размер {max_mb} МБ."


class SourceFileNotFoundError(ValidationError):
    """Локальный файл по указанному пути не существует.

    Поле шаблона: `path`.
    """

    message = "Файл не найден: {path}"


class SourceFilePathRequiredError(ValidationError):
    """Путь к загружаемому файлу не указан."""

    message = "Путь к файлу обязателен."


class NotADirectoryPathError(ValidationError):
    """Для сохранения нужна папка, а указан путь к файлу."""

    message = "Указанный путь — это файл, нужна папка."


class DirectoryUnavailableError(ValidationError):
    """Папку не удалось открыть или создать.

    Поле шаблона: `reason` — причина от операционной системы.
    """

    message = "Не удалось открыть или создать папку: {reason}"

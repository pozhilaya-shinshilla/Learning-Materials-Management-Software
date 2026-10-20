from __future__ import annotations

from src.bootstrap import ApplicationContext
from src.cli.console_io import Cancelled, ConsoleIO
from src.domain.exceptions import (
    DomainError,
    LoginRequiredError,
    PasswordMismatchError,
    ValidationError,
)
from src.domain.models import User
from src.domain.validation import validate_email, validate_login, validate_password

RESET_COMMAND = "/reset"


class AuthController:
    """Сценарии входа: запрос логина и пароля, восстановление пароля, выход из аккаунта."""

    def __init__(self, context: ApplicationContext, io: ConsoleIO) -> None:
        self._auth_service = context.auth_service
        self._io = io

    def sign_in(self) -> User | None:
        """Спрашивать данные для входа до успеха; None — пользователь выбрал выход."""
        while True:
            login = self._read_login()
            if login is None:
                return None
            if login == RESET_COMMAND:
                self._password_reset_flow()
                continue
            password = self._read_password()
            try:
                user = self._auth_service.login(login, password)
            except DomainError as error:
                print(f"Ошибка входа: {error}")
                continue
            print(f"Добро пожаловать, {login}! Роль: {user.role.label}.")
            self._io.pause()
            return user

    def sign_out(self, user: User) -> None:
        """Завершить сеанс пользователя."""
        self._auth_service.logout(user)

    def _read_login(self) -> str | None:
        """Запросить логин; None — выход, "/reset" — восстановление пароля."""
        while True:
            raw = self._io.read_line("Логин ('/reset' — забыли пароль, 'exit' — выход): ").strip()
            if raw.lower() == "exit":
                return None
            if raw.lower() == RESET_COMMAND:
                return RESET_COMMAND
            try:
                if not raw:
                    raise LoginRequiredError()
                validate_login(raw)
            except ValidationError as error:
                print(f"Ошибка: {error}")
                continue
            return raw

    def _read_password(self) -> str:
        """Запросить пароль (без отображения), пока не будет введена непустая строка."""
        while True:
            password = self._io.read_secret("Пароль: ")
            if password:
                return password
            print("Ошибка: введите пароль.")

    def _password_reset_flow(self) -> None:
        """Восстановить пароль: код приходит на email, по нему задаётся новый пароль."""
        try:
            self._io.header("Восстановление пароля")
            email = self._io.ask("Email учетной записи: ", self._parse_email)
            self._auth_service.request_password_reset(email)
            print("Если учетная запись с таким email существует, на него отправлен код.")
            token = self._io.ask("Код из письма: ", self._parse_reset_token)
            password = self._io.ask(
                "Новый пароль (не короче 8 символов): ", self._parse_new_password, secret=True
            )
            self._io.ask(
                "Повторите пароль: ",
                lambda raw: self._parse_same_password(raw, password),
                secret=True,
            )
            self._auth_service.reset_password_with_token(token, password)
            print("Пароль изменен. Теперь войдите с новым паролем.")
        except Cancelled as cancelled:
            print(cancelled)
        except DomainError as error:
            print(f"Ошибка: {error}")
        self._io.pause()

    @staticmethod
    def _parse_email(raw: str) -> str:
        """Разобрать email: убрать пробелы по краям и проверить формат."""
        email = raw.strip()
        validate_email(email)
        return email

    def _parse_reset_token(self, raw: str) -> str:
        """Разобрать код из письма и проверить, что он действителен."""
        token = raw.strip()
        self._auth_service.check_reset_token(token)
        return token

    @staticmethod
    def _parse_new_password(raw: str) -> str:
        """Проверить новый пароль на допустимую длину."""
        validate_password(raw)
        return raw

    @staticmethod
    def _parse_same_password(raw: str, expected: str) -> str:
        """Проверить, что повторно введённый пароль совпадает с первым."""
        if raw != expected:
            raise PasswordMismatchError()
        return raw

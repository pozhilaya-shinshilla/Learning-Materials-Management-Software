from __future__ import annotations

from src.bootstrap import ApplicationContext
from src.cli.admin_controller import AdminController
from src.cli.auth_controller import AuthController
from src.cli.console_io import Cancelled, ConsoleIO
from src.cli.menu import MenuRenderer
from src.cli.student_controller import StudentController
from src.cli.teacher_controller import TeacherController
from src.domain.enums import Role
from src.domain.exceptions import DomainError
from src.domain.models import User

_CONTROLLERS: dict[Role, type[StudentController]] = {
    Role.STUDENT: StudentController,
    Role.TEACHER: TeacherController,
    Role.ADMIN: AdminController,
}


class CliApplication:
    """Точка сборки CLI: вход, выбор меню по роли и запуск выбранного сценария."""

    def __init__(self, context: ApplicationContext, io: ConsoleIO) -> None:
        self._context = context
        self._io = io
        self._auth_controller = AuthController(context, io)
        self._menu = MenuRenderer(io)

    def run(self) -> None:
        """Запустить интерактивный цикл команд; возвращается, когда пользователь выходит."""
        try:
            while True:
                user = self._sign_in()
                if user is None:
                    break
                self._serve(user)
        except (EOFError, KeyboardInterrupt):
            print("\nЗавершение работы.")

    def _sign_in(self) -> User | None:
        """Показать экран входа; None — пользователь выбрал выход из программы."""
        self._io.clear_screen()
        print("=== Сервис управления учебными материалами ===(login: admin; password: admin123)")
        return self._auth_controller.sign_in()

    def _serve(self, user: User) -> None:
        """Показывать меню роли пользователя, пока он не выйдет из аккаунта."""
        controller = _CONTROLLERS[user.role](self._context, self._io, user)
        while self._run_menu_step(user, controller):
            pass
        self._auth_controller.sign_out(user)

    def _run_menu_step(self, user: User, controller: StudentController) -> bool:
        """Показать меню, выполнить одно действие; False — пользователь вышел из аккаунта."""
        title = f"{controller.menu_title} ({user.login})"
        handler = self._menu.choose(title, controller.menu_items())
        if handler is None:
            return False
        print()
        try:
            handler()
        except Cancelled as cancelled:
            print(cancelled)
        except DomainError as error:
            print(f"Ошибка: {error}")
        self._io.pause()
        return True

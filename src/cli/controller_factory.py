"""Фабричный метод (Factory Method): создание контроллера по роли пользователя.

Каждая роль имеет свою фабрику, которая решает, какой класс контроллера создать.
Чтобы добавить роль, нужно написать новую фабрику и зарегистрировать её, а
`CliApplication` менять не придётся.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.bootstrap import ApplicationContext
from src.cli.admin_controller import AdminController
from src.cli.console_io import ConsoleIO
from src.cli.student_controller import StudentController
from src.cli.teacher_controller import TeacherController
from src.domain.enums import Role
from src.domain.models import User


class ControllerFactory(ABC):
    """Создатель: объявляет фабричный метод, возвращающий контроллер меню."""

    @abstractmethod
    def create_controller(
        self, context: ApplicationContext, io: ConsoleIO, user: User
    ) -> StudentController:
        """Создать контроллер сценариев для пользователя."""


class StudentControllerFactory(ControllerFactory):
    """Создаёт контроллер студента."""

    def create_controller(
        self, context: ApplicationContext, io: ConsoleIO, user: User
    ) -> StudentController:
        """Создать `StudentController`."""
        return StudentController(context, io, user)


class TeacherControllerFactory(ControllerFactory):
    """Создаёт контроллер преподавателя."""

    def create_controller(
        self, context: ApplicationContext, io: ConsoleIO, user: User
    ) -> StudentController:
        """Создать `TeacherController`."""
        return TeacherController(context, io, user)


class AdminControllerFactory(ControllerFactory):
    """Создаёт контроллер администратора."""

    def create_controller(
        self, context: ApplicationContext, io: ConsoleIO, user: User
    ) -> StudentController:
        """Создать `AdminController`."""
        return AdminController(context, io, user)


CONTROLLER_FACTORIES: dict[Role, ControllerFactory] = {
    Role.STUDENT: StudentControllerFactory(),
    Role.TEACHER: TeacherControllerFactory(),
    Role.ADMIN: AdminControllerFactory(),
}

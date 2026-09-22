# Архитектура веб-приложения для управления учебными материалами (C4)

## Уровень 1. Контекст системы

```mermaid
C4Context
    title Диаграмма контекста системы

    Person(student, "Студент", "Поиск, просмотр и скачивание материалов")
    Person(teacher, "Преподаватель", "Загрузка и редактирование материалов")
    Person(admin, "Администратор", "Пользователи, роли и журнал событий")

    System(webapp, "Веб-приложение", "Хранение, поиск и предоставление доступа к учебным материалам")
    System_Ext(mail, "Почтовый сервер", "Восстановление пароля")
    System_Ext(external, "Внешние ИС", "Интеграция через REST API")

    Rel(student, webapp, "Работает с материалами")
    Rel(teacher, webapp, "Управляет материалами")
    Rel(admin, webapp, "Администрирует")
    Rel(webapp, mail, "Отправляет письма")
    Rel(external, webapp, "Обращается к данным")

    UpdateLayoutConfig($c4ShapeInRow="2", $c4BoundaryInRow="1")
```

## Уровень 2. Контейнеры

```mermaid
C4Container
    title Диаграмма контейнеров системы

    Person(student, "Студент", "Просмотр и скачивание")
    Person(teacher, "Преподаватель", "Загрузка и редактирование")
    Person(admin, "Администратор", "Управление системой")

    System_Boundary(webapp, "Веб-приложение") {
        Container(frontend, "Frontend", "Nginx, SPA", "Интерфейсы всех ролей")
        Container(backend, "Backend", "REST API", "Аутентификация, бизнес-логика и поиск")
        ContainerDb(db, "База данных", "PostgreSQL", "Пользователи, материалы и журнал")
        ContainerDb(files, "Хранилище файлов", "Docker volume", "Файлы учебных материалов")
    }

    System_Ext(mail, "Почтовый сервер", "Восстановление пароля")
    System_Ext(external, "Внешние ИС", "REST API")

    Rel(student, frontend, "Использует")
    Rel(teacher, frontend, "Использует")
    Rel(admin, frontend, "Использует")

    Rel_R(frontend, backend, "REST API")
    Rel_D(backend, db, "SQL")
    Rel_D(backend, files, "Файлы")
    Rel_R(backend, mail, "SMTP")
    Rel_L(external, backend, "REST API")

    UpdateLayoutConfig($c4ShapeInRow="2", $c4BoundaryInRow="1")
```

## Уровень 3. Компоненты серверной части

```mermaid
C4Component
    title Диаграмма компонентов Backend

    Container(frontend, "Frontend", "Nginx, SPA", "Интерфейсы пользователей")
    ContainerDb(db, "База данных", "PostgreSQL", "Метаданные и журнал")
    ContainerDb(files, "Хранилище файлов", "Docker volume", "Учебные материалы")
    System_Ext(mail, "Почтовый сервер", "Восстановление пароля")

    Container_Boundary(backend, "Backend") {
        Component(auth, "Авторизация", "REST API", "Вход, JWT, роли и восстановление пароля")
        Component(materials, "Материалы", "REST API", "Создание, редактирование, удаление и просмотр")
        Component(search, "Поиск", "REST API", "Полнотекстовый поиск, фильтры и сортировка")
        Component(users, "Пользователи", "REST API", "Регистрация, роли, блокировка и удаление")
        Component(filestore, "Файлы", "Модуль", "Проверка, сохранение и выдача файлов")
        Component(audit, "Журнал", "Модуль", "Запись действий пользователей")
    }

    Rel_D(frontend, auth, "Auth API")
    Rel_D(frontend, materials, "Materials API")
    Rel_D(frontend, search, "Search API")
    Rel_D(frontend, users, "Users API")

    Rel_R(materials, filestore, "Файлы")
    Rel_D(materials, audit, "События")
    Rel_D(users, audit, "События")
    Rel_L(auth, audit, "Входы и выходы")

    Rel_R(auth, mail, "SMTP")
    Rel_D(filestore, files, "Файловый ввод-вывод")
    Rel_D(auth, db, "Пользователи")
    Rel_D(materials, db, "Метаданные")
    Rel_D(search, db, "Поиск")
    Rel_D(users, db, "Учётные записи")
    Rel_D(audit, db, "Журнал")

    UpdateLayoutConfig($c4ShapeInRow="2", $c4BoundaryInRow="1")
```

## Развёртывание

```mermaid
C4Deployment
    title Диаграмма развёртывания

    Deployment_Node(server, "Сервер Заказчика", "Ubuntu 20.04+ или Windows Server с WSL2") {
        Deployment_Node(docker, "Docker Engine 24+", "Docker Compose v2") {
            Deployment_Node(feNode, "frontend", "Nginx") {
                Container(frontend, "Frontend", "SPA", "Порты 80/443")
            }
            Deployment_Node(beNode, "backend", "REST API") {
                Container(backend, "Backend", "REST API", "Swagger: /docs")
            }
            Deployment_Node(dbNode, "db", "PostgreSQL") {
                ContainerDb(db, "База данных", "PostgreSQL", "Том для сохранения данных")
            }
        }
    }

    Rel_R(frontend, backend, "HTTP / JSON")
    Rel_D(backend, db, "SQL")
```

> Развёртывание выполняется в двух экземплярах: тестовая и промышленная среды.

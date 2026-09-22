# Архитектура веб-приложения для управления учебными материалами (C4)

## Уровень 1. Контекст системы

Кто и как взаимодействует с веб-приложением (см. раздел 3.1 ТЗ).

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'fontFamily': 'Arial, sans-serif', 'fontSize': '16px'}}}%%
C4Context
    title Диаграмма контекста: веб-приложение для управления учебными материалами

    Person(student, "Студент", "Поиск, просмотр, скачивание, избранное, комментарии")
    Person(teacher, "Преподаватель", "Загрузка, структурирование, редактирование материалов")
    Person(admin, "Администратор", "Пользователи, роли, дисциплины, журнал событий")

    System(webapp, "Веб-приложение", "Хранение, поиск и доступ к учебным материалам ВолгГТУ")

    System_Ext(mail, "Почтовый сервер", "Ссылки восстановления пароля")
    System_Ext(external, "Внешние системы", "Интеграция по REST API")

    Rel(student, webapp, "Просматривает и скачивает", "HTTPS")
    Rel(teacher, webapp, "Управляет материалами", "HTTPS")
    Rel(admin, webapp, "Администрирует", "HTTPS")
    Rel(webapp, mail, "Отправляет письма", "SMTP")
    Rel(external, webapp, "Запрашивает данные", "REST/JSON")

    UpdateLayoutConfig($c4ShapeInRow="2", $c4BoundaryInRow="1")
```

## Уровень 2. Контейнеры

Из каких частей состоит веб-приложение (см. раздел 3.2 ТЗ).

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'fontFamily': 'Arial, sans-serif', 'fontSize': '16px'}}}%%
C4Container
    title Диаграмма контейнеров: веб-приложение для управления учебными материалами

    Person(student, "Студент", "Просмотр и скачивание материалов")
    Person(teacher, "Преподаватель", "Загрузка и редактирование")
    Person(admin, "Администратор", "Управление и журнал событий")

    System_Boundary(webapp, "Веб-приложение") {
        Container(frontend, "Frontend", "Nginx, SPA", "Интерфейсы трёх ролей, адаптив от 320 px")
        Container(backend, "Backend", "REST API", "Аутентификация, бизнес-логика, поиск, журналирование")
        ContainerDb(db, "База данных", "PostgreSQL", "Пользователи, материалы, дисциплины, избранное, комментарии, журнал")
        ContainerDb(files, "Хранилище файлов", "Docker volume", "PDF, DOCX, PPTX, XLSX, JPG, PNG до 20 МБ")
    }

    System_Ext(mail, "Почтовый сервер", "Восстановление пароля")
    System_Ext(external, "Внешние системы", "Интеграция по API")

    Rel(student, frontend, "Использует", "HTTPS")
    Rel(teacher, frontend, "Использует", "HTTPS")
    Rel(admin, frontend, "Использует", "HTTPS")

    Rel(frontend, backend, "Вызывает API", "HTTPS/JSON, /api/v1")
    Rel(backend, db, "Читает и пишет", "SQL, 5432")
    Rel(backend, files, "Сохраняет и отдаёт", "Файловый ввод-вывод")
    Rel(backend, mail, "Отправляет ссылки", "SMTP")
    Rel(external, backend, "Интеграция", "REST API")

    UpdateLayoutConfig($c4ShapeInRow="2", $c4BoundaryInRow="1")
```

## Уровень 3. Компоненты серверной части

Из каких модулей состоит Backend (функциональные подсистемы из раздела 4.1 ТЗ).

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'fontFamily': 'Arial, sans-serif', 'fontSize': '16px'}}}%%
C4Component
    title Диаграмма компонентов: серверная часть (Backend)

    Container(frontend, "Frontend", "Nginx, SPA", "Интерфейсы трёх ролей")
    ContainerDb(db, "База данных", "PostgreSQL", "Пользователи, материалы, журнал")
    ContainerDb(files, "Хранилище файлов", "Docker volume", "Файлы материалов")
    System_Ext(mail, "Почтовый сервер", "Восстановление пароля")

    Container_Boundary(backend, "Backend") {
        Component(auth, "Авторизация", "REST API", "Вход, JWT, роли, восстановление пароля")
        Component(materials, "Материалы", "REST API", "CRUD, корзина, просмотр")
        Component(search, "Поиск", "REST API", "Полнотекстовый поиск, фильтры, сортировка")
        Component(users, "Пользователи", "REST API", "Регистрация, роли, блокировка, удаление")
        Component(filestore, "Файлы", "Модуль", "Проверка формата и размера до 20 МБ")
        Component(audit, "Журналирование", "Модуль", "Входы, изменения, загрузки")
    }

    Rel(frontend, auth, "Вход и восстановление", "HTTPS, /api/v1/auth")
    Rel(frontend, materials, "Работа с материалами", "HTTPS, /api/v1/materials")
    Rel(frontend, search, "Поиск и фильтры", "HTTPS")
    Rel(frontend, users, "Управление пользователями", "HTTPS, /api/v1/users")

    Rel(materials, filestore, "Сохраняет и читает файлы")
    Rel(auth, mail, "Отправляет ссылку", "SMTP")
    Rel(filestore, files, "Читает и пишет", "Файловый ввод-вывод")

    Rel(auth, db, "Пользователи и роли", "SQL")
    Rel(materials, db, "Метаданные материалов", "SQL")
    Rel(search, db, "Поисковые запросы", "SQL")
    Rel(users, db, "Учётные записи", "SQL")
    Rel(audit, db, "Журнал событий", "SQL")

    Rel(materials, audit, "Фиксирует действия")
    Rel(users, audit, "Фиксирует действия")
    Rel(auth, audit, "Фиксирует входы")

    UpdateLayoutConfig($c4ShapeInRow="2", $c4BoundaryInRow="1")
```

## Развёртывание

Схема запуска через Docker Compose (см. раздел 6 ТЗ).

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'fontFamily': 'Arial, sans-serif', 'fontSize': '16px'}}}%%
C4Deployment
    title Диаграмма развёртывания: сервер Заказчика (ВолгГТУ)

    Deployment_Node(server, "Сервер Заказчика", "Ubuntu 20.04+ / Windows Server + WSL2") {
        Deployment_Node(docker, "Docker Engine 24+", "Docker Compose v2") {
            Deployment_Node(feNode, "frontend", "Nginx") {
                Container(frontend, "SPA", "Статика", "Порты 80/443")
            }
            Deployment_Node(beNode, "backend", "REST API") {
                Container(backend, "API", "REST", "/docs, /api/v1/health")
            }
            Deployment_Node(dbNode, "db", "PostgreSQL") {
                ContainerDb(db, "БД", "PostgreSQL", "5432, том данных")
            }
        }
    }

    Rel(frontend, backend, "Вызывает API", "HTTP/JSON")
    Rel(backend, db, "Читает и пишет", "SQL")
```

> Развёртывание выполняется в двух экземплярах: тестовая среда (предварительные испытания) и промышленная среда (опытная эксплуатация).

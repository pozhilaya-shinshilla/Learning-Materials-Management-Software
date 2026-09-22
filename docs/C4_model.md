# Архитектура веб-приложения для управления учебными материалами (C4)

## Уровень 1. Контекст системы

Кто и как взаимодействует с веб-приложением (см. раздел 3.1 ТЗ).

```mermaid
C4Context
    title Диаграмма контекста

    Person(student, "Студент", "Поиск, скачивание, избранное")
    Person(teacher, "Преподаватель", "Загрузка и редактирование материалов")
    Person(admin, "Администратор", "Пользователи, дисциплины, журнал")

    System(webapp, "Веб-приложение", "Хранение, поиск и доступ к материалам ВолгГТУ")

    System_Ext(mail, "Почтовый сервер", "Восстановление пароля")
    System_Ext(external, "Внешние системы", "Интеграция по REST API")

    Rel(student, webapp, "HTTPS")
    Rel(teacher, webapp, "HTTPS")
    Rel(admin, webapp, "HTTPS")
    Rel(webapp, mail, "SMTP")
    Rel(external, webapp, "REST API")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

## Уровень 2. Контейнеры

Из каких частей состоит веб-приложение (см. раздел 3.2 ТЗ).

```mermaid
C4Container
    title Диаграмма контейнеров

    Person(student, "Студент")
    Person(teacher, "Преподаватель")
    Person(admin, "Администратор")

    System_Boundary(webapp, "Веб-приложение") {
        Container(frontend, "Frontend", "Nginx, SPA", "UI трёх ролей, адаптив от 320px")
        Container(backend, "Backend", "REST API", "Логика, аутентификация, поиск, журнал")
        ContainerDb(db, "База данных", "PostgreSQL", "Пользователи, материалы, журнал")
        ContainerDb(files, "Хранилище файлов", "Docker volume", "PDF/DOCX/PPTX/XLSX/JPG/PNG, ≤20 МБ")
    }

    System_Ext(mail, "Почтовый сервер")
    System_Ext(external, "Внешние системы")

    Rel(student, frontend, "HTTPS")
    Rel(teacher, frontend, "HTTPS")
    Rel(admin, frontend, "HTTPS")

    Rel(frontend, backend, "HTTPS, /api/v1")
    Rel(backend, db, "SQL")
    Rel(backend, files, "Файлы")
    Rel(backend, mail, "SMTP")
    Rel(external, backend, "REST API")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

## Уровень 3. Компоненты серверной части

Из каких модулей состоит Backend (см. раздел 4.1 ТЗ).

```mermaid
C4Component
    title Диаграмма компонентов Backend

    Container(frontend, "Frontend", "Nginx, SPA")
    ContainerDb(db, "База данных", "PostgreSQL")
    ContainerDb(files, "Хранилище файлов", "Docker volume")
    System_Ext(mail, "Почтовый сервер")

    Container_Boundary(backend, "Backend") {
        Component(auth, "Аутентификация и авторизация", "REST API", "Логин/пароль, JWT, роли")
        Component(materials, "Управление материалами", "REST API", "Создание, правка, удаление")
        Component(search, "Поиск и фильтрация", "REST API", "Полнотекстовый поиск, фильтры")
        Component(users, "Управление пользователями", "REST API", "Роли, блокировка, удаление")
        Component(filestore, "Хранение файлов", "Модуль", "Проверка формата и размера")
        Component(audit, "Журналирование", "Модуль", "Лог действий пользователей")
    }

    Rel(frontend, auth, "/api/v1/auth")
    Rel(frontend, materials, "/api/v1/materials")
    Rel(frontend, search, "/api/v1/search")
    Rel(frontend, users, "/api/v1/users")

    Rel(materials, filestore, "Файлы")
    Rel(materials, audit, "Лог")
    Rel(users, audit, "Лог")
    Rel(auth, audit, "Лог")

    Rel(auth, mail, "SMTP")
    Rel(filestore, files, "I/O")

    Rel(auth, db, "SQL")
    Rel(materials, db, "SQL")
    Rel(search, db, "SQL")
    Rel(users, db, "SQL")
    Rel(audit, db, "SQL")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

## Развёртывание

Схема запуска через Docker Compose (см. раздел 6 ТЗ).

```mermaid
C4Deployment
    title Диаграмма развёртывания

    Deployment_Node(server, "Сервер Заказчика", "Ubuntu 20.04+ / Windows Server + WSL2") {
        Deployment_Node(docker, "Docker Engine 24+", "docker-compose.yml") {
            Deployment_Node(feNode, "Контейнер frontend", "Nginx") {
                Container(frontend, "Frontend", "SPA", "Порты 80/443")
            }
            Deployment_Node(beNode, "Контейнер backend", "REST API") {
                Container(backend, "Backend", "REST API", "/docs, /api/v1/health")
            }
            Deployment_Node(dbNode, "Контейнер db", "PostgreSQL") {
                ContainerDb(db, "База данных", "PostgreSQL", "Порт 5432, том данных")
            }
        }
    }

    Rel(frontend, backend, "HTTP, JSON")
    Rel(backend, db, "SQL")
```

> Развёртывание выполняется в двух экземплярах: тестовая среда (предварительные испытания) и промышленная среда (опытная эксплуатация).

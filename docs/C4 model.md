# Архитектура веб-приложения для управления учебными материалами (C4)

## Уровень 1. Контекст системы

Кто и как взаимодействует с веб-приложением (см. раздел 3.1 ТЗ).

```mermaid
%%{init: {"c4": {"diagramMarginX": 40, "diagramMarginY": 30, "c4ShapeMargin": 60, "c4ShapePadding": 25, "width": 280, "height": 200, "fontSize": 15}}}%%
C4Context
    title Диаграмма контекста: веб-приложение для управления учебными материалами

    Person(student, "Студент", "Ищет, просматривает<br/>и скачивает материалы,<br/>добавляет в избранное,<br/>оставляет комментарии")
    Person(teacher, "Преподаватель", "Загружает, структурирует,<br/>редактирует и удаляет<br/>учебные материалы")
    Person(admin, "Администратор", "Управляет пользователями,<br/>ролями, структурой дисциплин,<br/>просматривает журнал событий")

    System(webapp, "Веб-приложение", "Единый ресурс для хранения,<br/>поиска и предоставления доступа<br/>к учебным материалам ВолгГТУ")

    System_Ext(mail, "Почтовый сервер", "Отправка ссылок<br/>для восстановления пароля")
    System_Ext(external, "Внешние информационные системы", "Интеграция<br/>через REST API")

    Rel(student, webapp, "Просматривает и скачивает материалы", "HTTPS")
    Rel(teacher, webapp, "Управляет материалами", "HTTPS")
    Rel(admin, webapp, "Администрирует систему", "HTTPS")
    Rel(webapp, mail, "Отправляет письма", "SMTP")
    Rel(external, webapp, "Обращается к данным", "REST API / JSON")

    UpdateLayoutConfig($c4ShapeInRow="2", $c4BoundaryInRow="1")
```

## Уровень 2. Контейнеры

Из каких частей состоит веб-приложение (см. раздел 3.2 ТЗ).

```mermaid
%%{init: {"c4": {"diagramMarginX": 40, "diagramMarginY": 30, "c4ShapeMargin": 60, "c4ShapePadding": 25, "width": 280, "height": 200, "fontSize": 15}}}%%
C4Container
    title Диаграмма контейнеров: веб-приложение для управления учебными материалами

    Person(student, "Студент", "Просмотр, поиск,<br/>скачивание материалов")
    Person(teacher, "Преподаватель", "Загрузка и редактирование<br/>материалов")
    Person(admin, "Администратор", "Управление пользователями,<br/>журнал событий")

    System_Boundary(webapp, "Веб-приложение") {
        Container(frontend, "Клиентская часть (Frontend)", "Nginx, SPA", "Интерфейсы студента, преподавателя<br/>и администратора, адаптивная<br/>вёрстка от 320 px")
        Container(backend, "Серверная часть (Backend)", "REST API", "Аутентификация, ролевая модель,<br/>бизнес-логика, поиск и фильтрация,<br/>журналирование")
        ContainerDb(db, "База данных", "PostgreSQL", "Пользователи, материалы,<br/>дисциплины, избранное,<br/>комментарии, журнал событий")
        ContainerDb(files, "Хранилище файлов", "Том Docker / файловая система", "Загруженные файлы: PDF, DOCX,<br/>PPTX, XLSX, JPG, PNG, до 20 МБ")
    }

    System_Ext(mail, "Почтовый сервер", "Восстановление пароля")
    System_Ext(external, "Внешние информационные системы", "Интеграция<br/>через API")

    Rel(student, frontend, "Использует", "HTTPS")
    Rel(teacher, frontend, "Использует", "HTTPS")
    Rel(admin, frontend, "Использует", "HTTPS")

    Rel(frontend, backend, "Вызывает API", "HTTPS, JSON, /api/v1")
    Rel(backend, db, "Читает и записывает данные", "SQL, порт 5432")
    Rel(backend, files, "Сохраняет и отдаёт файлы", "Файловый ввод-вывод")
    Rel(backend, mail, "Отправляет ссылки восстановления пароля", "SMTP")
    Rel(external, backend, "Интеграция", "REST API")

    UpdateLayoutConfig($c4ShapeInRow="2", $c4BoundaryInRow="1")
```

## Уровень 3. Компоненты серверной части

Из каких модулей состоит Backend (функциональные подсистемы из раздела 4.1 ТЗ).

```mermaid
%%{init: {"c4": {"diagramMarginX": 40, "diagramMarginY": 30, "c4ShapeMargin": 70, "c4ShapePadding": 25, "width": 280, "height": 210, "fontSize": 15}}}%%
C4Component
    title Диаграмма компонентов: серверная часть (Backend)

    Container(frontend, "Клиентская часть (Frontend)", "Nginx, SPA", "Интерфейсы трёх ролей")
    ContainerDb(db, "База данных", "PostgreSQL", "Пользователи, материалы,<br/>журнал событий")
    ContainerDb(files, "Хранилище файлов", "Том Docker", "Файлы учебных материалов")
    System_Ext(mail, "Почтовый сервер", "Восстановление пароля")

    Container_Boundary(backend, "Серверная часть (Backend)") {
        Component(auth, "Идентификация и авторизация", "REST API", "Вход по логину и паролю,<br/>хеширование паролей, токены JWT,<br/>ролевая модель,<br/>восстановление пароля")
        Component(materials, "Управление материалами", "REST API", "Создание, редактирование,<br/>удаление (в корзину)<br/>и просмотр материалов")
        Component(search, "Поиск и фильтрация", "REST API", "Полнотекстовый поиск с<br/>морфологией русского языка,<br/>фильтры, сортировка")
        Component(users, "Управление пользователями", "REST API", "Регистрация, смена ролей,<br/>блокировка, удаление")
        Component(filestore, "Хранение и управление файлами", "Модуль", "Проверка формата и размера<br/>(до 20 МБ), сохранение<br/>и выдача файлов")
        Component(audit, "Журналирование действий", "Модуль", "Запись входов, изменений материалов,<br/>загрузок, изменений<br/>учётных записей")
    }

    Rel(frontend, auth, "Вход, восстановление пароля", "HTTPS, /api/v1/auth")
    Rel(frontend, materials, "Работа с материалами", "HTTPS, /api/v1/materials")
    Rel(frontend, search, "Поиск и фильтры", "HTTPS")
    Rel(frontend, users, "Управление пользователями", "HTTPS, /api/v1/users")

    Rel(materials, filestore, "Сохраняет и читает файлы")
    Rel(materials, audit, "Фиксирует действия")
    Rel(users, audit, "Фиксирует действия")
    Rel(auth, audit, "Фиксирует входы и выходы")

    Rel(auth, mail, "Отправляет ссылку восстановления", "SMTP")
    Rel(filestore, files, "Читает и записывает", "Файловый ввод-вывод")
    Rel(auth, db, "Пользователи и роли", "SQL")
    Rel(materials, db, "Метаданные материалов", "SQL")
    Rel(search, db, "Поисковые запросы", "SQL")
    Rel(users, db, "Учётные записи", "SQL")
    Rel(audit, db, "Журнал событий", "SQL")

    UpdateLayoutConfig($c4ShapeInRow="2", $c4BoundaryInRow="1")
```

## Развёртывание

Схема запуска через Docker Compose (см. раздел 6 ТЗ).

```mermaid
%%{init: {"c4": {"diagramMarginX": 40, "diagramMarginY": 30, "c4ShapeMargin": 50, "c4ShapePadding": 20, "width": 260, "height": 170, "fontSize": 15}}}%%
C4Deployment
    title Диаграмма развёртывания: сервер Заказчика (ВолгГТУ)

    Deployment_Node(server, "Сервер Заказчика", "Linux Ubuntu 20.04+ или Windows Server с WSL2") {
        Deployment_Node(docker, "Docker Engine 24+", "Docker Compose v2, файл docker-compose.yml") {
            Deployment_Node(feNode, "Контейнер frontend", "Nginx") {
                Container(frontend, "Клиентская часть", "SPA", "Порты 80/443")
            }
            Deployment_Node(beNode, "Контейнер backend", "REST API") {
                Container(backend, "Серверная часть", "REST API", "Swagger UI: /docs,<br/>healthcheck: /api/v1/health")
            }
            Deployment_Node(dbNode, "Контейнер db", "PostgreSQL") {
                ContainerDb(db, "База данных", "PostgreSQL", "Порт 5432,<br/>том для сохранения данных")
            }
        }
    }

    Rel(frontend, backend, "Вызывает API", "HTTP, JSON")
    Rel(backend, db, "Читает и записывает данные", "SQL")
```

> Развёртывание выполняется в двух экземплярах: тестовая среда (предварительные испытания) и промышленная среда (опытная эксплуатация).

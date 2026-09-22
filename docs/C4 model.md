# Архитектура веб-приложения для управления учебными материалами (C4)

## Уровень 1. Контекст системы

Кто и как взаимодействует с веб-приложением (см. раздел 3.1 ТЗ).

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'fontFamily': 'Arial, sans-serif', 'fontSize': '16px'}}}%%
C4Context
title Диаграмма контекста: веб-приложение для управления учебными материалами

Person(student, "Студент", "Ищет, просматривает и скачивает материалы, добавляет в избранное, оставляет комментарии")
Person(teacher, "Преподаватель", "Загружает, структурирует, редактирует и удаляет учебные материалы")
Person(admin, "Администратор", "Управляет пользователями, ролями, структурой дисциплин, просматривает журнал событий")

System(webapp, "Веб-приложение", "Единый ресурс для хранения, поиска и предоставления доступа к учебным материалам ВолгГТУ")

System_Ext(mail, "Почтовый сервер", "Отправка ссылок для восстановления пароля")
System_Ext(external, "Внешние информационные системы", "Интеграция через REST API")

Rel(student, webapp, "Просматривает и скачивает материалы", "HTTPS")
Rel(teacher, webapp, "Управляет материалами", "HTTPS")
Rel(admin, webapp, "Администрирует систему", "HTTPS")
Rel(webapp, mail, "Отправляет письма", "SMTP")
Rel(external, webapp, "Обращается к данным", "REST API / JSON")

UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

## Уровень 2. Контейнеры

Из каких частей состоит веб-приложение (см. раздел 3.2 ТЗ).

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'fontFamily': 'Arial, sans-serif', 'fontSize': '16px'}}}%%
C4Container
title Диаграмма контейнеров: веб-приложение для управления учебными материалами

Person(student, "Студент", "Просмотр, поиск, скачивание материалов")
Person(teacher, "Преподаватель", "Загрузка и редактирование материалов")
Person(admin, "Администратор", "Управление пользователями, журнал событий")

System_Boundary(webapp, "Веб-приложение") {
    Container(frontend, "Клиентская часть (Frontend)", "Nginx, SPA", "Интерфейсы студента, преподавателя и администратора, адаптивная вёрстка от 320 px")
    Container(backend, "Серверная часть (Backend)", "REST API", "Аутентификация, ролевая модель, бизнес-логика, поиск и фильтрация, журналирование")
    ContainerDb(db, "База данных", "PostgreSQL", "Пользователи, материалы, дисциплины, избранное, комментарии, журнал событий")
    ContainerDb(files, "Хранилище файлов", "Том Docker / файловая система", "Загруженные файлы: PDF, DOCX, PPTX, XLSX, JPG, PNG, до 20 МБ")
}

System_Ext(mail, "Почтовый сервер", "Восстановление пароля")
System_Ext(external, "Внешние информационные системы", "Интеграция через API")

Rel(student, frontend, "Использует", "HTTPS")
Rel(teacher, frontend, "Использует", "HTTPS")
Rel(admin, frontend, "Использует", "HTTPS")

Rel(frontend, backend, "Вызывает API", "HTTPS, JSON, /api/v1")
Rel(backend, db, "Читает и записывает данные", "SQL, порт 5432")
Rel(backend, files, "Сохраняет и отдаёт файлы", "Файловый ввод-вывод")
Rel(backend, mail, "Отправляет ссылки восстановления пароля", "SMTP")
Rel(external, backend, "Интеграция", "REST API")

UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

## Уровень 3. Компоненты серверной части

Из каких модулей состоит Backend (функциональные подсистемы из раздела 4.1 ТЗ).

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'fontFamily': 'Arial, sans-serif', 'fontSize': '16px'}}}%%
C4Component
title Диаграмма компонентов: серверная часть (Backend)

Container(frontend, "Клиентская часть (Frontend)", "Nginx, SPA", "Интерфейсы трёх ролей")
ContainerDb(db, "База данных", "PostgreSQL", "Пользователи, материалы, журнал событий")
ContainerDb(files, "Хранилище файлов", "Том Docker", "Файлы учебных материалов")
System_Ext(mail, "Почтовый сервер", "Восстановление пароля")

Container_Boundary(backend, "Серверная часть (Backend)") {
    Component(auth, "Идентификация и авторизация", "REST API", "Вход по логину и паролю, хеширование паролей, токены JWT, ролевая модель, восстановление пароля")
    Component(materials, "Управление материалами", "REST API", "Создание, редактирование, удаление (в корзину) и просмотр материалов")
    Component(search, "Поиск и фильтрация", "REST API", "Полнотекстовый поиск с морфологией русского языка, фильтры, сортировка")
    Component(users, "Управление пользователями", "REST API", "Регистрация, смена ролей, блокировка, удаление")
    Component(filestore, "Хранение и управление файлами", "Модуль", "Проверка формата и размера (до 20 МБ), сохранение и выдача файлов")
    Component(audit, "Журналирование действий", "Модуль", "Запись входов, изменений материалов, загрузок, изменений учётных записей")
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

UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

## Развёртывание

Схема запуска через Docker Compose (см. раздел 6 ТЗ).

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'fontFamily': 'Arial, sans-serif', 'fontSize': '16px'}}}%%
C4Deployment
title Диаграмма развёртывания: сервер Заказчика (ВолгГТУ)

Deployment_Node(server, "Сервер Заказчика", "Linux Ubuntu 20.04+ или Windows Server с WSL2") {
    Deployment_Node(docker, "Docker Engine 24+", "Docker Compose v2, файл docker-compose.yml") {
        Deployment_Node(feNode, "Контейнер frontend", "Nginx") {
            Container(frontend, "Клиентская часть", "SPA", "Порты 80/443")
        }
        Deployment_Node(beNode, "Контейнер backend", "REST API") {
            Container(backend, "Серверная часть", "REST API", "Swagger UI: /docs, healthcheck: /api/v1/health")
        }
        Deployment_Node(dbNode, "Контейнер db", "PostgreSQL") {
            ContainerDb(db, "База данных", "PostgreSQL", "Порт 5432, том для сохранения данных")
        }
    }
}

Rel(frontend, backend, "Вызывает API", "HTTP, JSON")
Rel(backend, db, "Читает и записывает данные", "SQL")
```

> Развёртывание выполняется в двух экземплярах: тестовая среда (предварительные испытания) и промышленная среда (опытная эксплуатация).


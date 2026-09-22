## Уровень 1. Контекст системы

Кто и как взаимодействует с веб-приложением (см. раздел 3.1 ТЗ).

```mermaid
C4Context
    title Диаграмма контекста: веб-приложение для управления учебными материалами

    Person(student, "Студент", "Ищет, просматривает и скачивает материалы")
    Person(teacher, "Преподаватель", "Загружает и редактирует материалы")
    Person(admin, "Администратор", "Управляет пользователями и системой")

    System(webapp, "Веб-приложение", "Единый ресурс для хранения и поиска материалов ВолгГТУ")

    System_Ext(mail, "Почтовый сервер", "Отправка писем сброса пароля")
    System_Ext(external, "Внешние ИС", "Интеграция через REST API")

    Rel(student, webapp, "Просмотр и скачивание", "HTTPS")
    Rel(teacher, webapp, "Управление контентом", "HTTPS")
    Rel(admin, webapp, "Администрирование", "HTTPS")
    
    Rel(webapp, mail, "Отправка писем", "SMTP")
    Rel(external, webapp, "Обращение к данным", "REST API / JSON")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")

## Уровень 2. Контейнеры

C4Container
    title Диаграмма контейнеров: веб-приложение для управления учебными материалами

    Person(users, "Пользователи", "Студенты, Преподаватели, Администраторы")

    System_Boundary(webapp, "Веб-приложение") {
        Container(frontend, "Клиентская часть (Frontend)", "Nginx, SPA", "Интерфейсы трёх ролей, адаптивная вёрстка")
        Container(backend, "Серверная часть (Backend)", "REST API", "Аутентификация, бизнес-логика, поиск, журнал")
        ContainerDb(db, "База данных", "PostgreSQL", "Пользователи, материалы, комментарии, логи")
        ContainerDb(files, "Хранилище файлов", "Том Docker", "Файлы материалов (до 20 МБ)")
    }

    System_Ext(mail, "Почтовый сервер", "Восстановление пароля")
    System_Ext(external, "Внешние ИС", "Интеграция через API")

    Rel(users, frontend, "Использует интерфейс", "HTTPS")
    Rel(frontend, backend, "Вызывает API", "HTTPS / JSON")
    
    Rel(backend, db, "Читает и записывает данные", "SQL")
    Rel(backend, files, "Сохраняет и отдаёт файлы", "I/O")
    Rel(backend, mail, "Отправляет письма", "SMTP")
    Rel(external, backend, "Интеграция", "REST API")

    UpdateLayoutConfig($c4ShapeInRow="2", $c4BoundaryInRow="1")

## Уровень 3. Компоненты серверной части

C4Component
    title Диаграмма компонентов: серверная часть (Backend)

    Container(frontend, "Клиентская часть (Frontend)", "Nginx, SPA", "Интерфейсы трех ролей")
    System_Ext(mail, "Почтовый сервер", "SMTP", "Восстановление пароля")

    Container_Boundary(backend, "Серверная часть (Backend)") {
        Component(auth, "Идентификация и авторизация", "REST API", "JWT, роли, сброс пароля")
        Component(users, "Управление пользователями", "REST API", "Регистрация, роли, блокировка")
        Component(materials, "Управление материалами", "REST API", "CRUD материалов, корзина")
        Component(search, "Поиск и фильтрация", "REST API", "Полнотекстовый поиск с морфологией")
        
        Component(filestore, "Управление файлами", "Модуль", "Проверка формата/размера, I/O")
        Component(audit, "Журналирование действий", "Модуль", "Запись событий и логов")
    }

    ContainerDb(db, "База данных", "PostgreSQL", "Метаданные и пользователи")
    ContainerDb(files, "Хранилище файлов", "Том Docker", "Файлы учебных материалов")

    %% Связи сверху вниз (Frontend -> API)
    Rel(frontend, auth, "Вход и доступ", "HTTPS")
    Rel(frontend, users, "Пользователи", "HTTPS")
    Rel(frontend, materials, "Материалы", "HTTPS")
    Rel(frontend, search, "Поиск", "HTTPS")

    %% Внутренние связи Backend
    Rel(materials, filestore, "Передача файлов")
    Rel(auth, audit, "Фиксирует входы")
    Rel(materials, audit, "Фиксирует изменения")
    Rel(users, audit, "Фиксирует действия")

    %% Связи с внешними сервисами и БД
    Rel(auth, mail, "Отправка ссылок", "SMTP")
    Rel(filestore, files, "Запись и чтение", "I/O")
    
    Rel(auth, db, "Данные пользователей", "SQL")
    Rel(users, db, "Учётные записи", "SQL")
    Rel(materials, db, "Метаданные", "SQL")
    Rel(search, db, "Поисковый индекс", "SQL")
    Rel(audit, db, "Журнал событий", "SQL")

    UpdateLayoutConfig($c4ShapeInRow="4", $c4BoundaryInRow="1")
```

### Описание компонентов

| Компонент | Назначение |
|---|---|
| Авторизация | Вход, хеширование, JWT, роли, восстановление пароля |
| Материалы | Создание, редактирование, удаление и просмотр |
| Поиск | Полнотекстовый поиск, фильтры и сортировка |
| Пользователи | Регистрация, роли, блокировка и удаление |
| Файлы | Проверка, сохранение и выдача файлов |
| Журнал | Запись действий пользователей |

## Развёртывание

C4Deployment
    title Диаграмма развёртывания: сервер Заказчика (ВолгГТУ)

    Deployment_Node(server, "Сервер Заказчика", "Linux Ubuntu 20.04+ / Windows Server") {
        Deployment_Node(docker, "Docker Engine 24+", "Docker Compose v2") {
            Deployment_Node(feNode, "Контейнер frontend", "Nginx") {
                Container(frontend, "Клиентская часть", "SPA", "Порты 80/443")
            }
            Deployment_Node(beNode, "Контейнер backend", "REST API") {
                Container(backend, "Серверная часть", "REST API", "Swagger: /docs, Healthcheck: /api/v1/health")
            }
            Deployment_Node(dbNode, "Контейнер db", "PostgreSQL") {
                ContainerDb(db, "База данных", "PostgreSQL", "Порт 5432, Docker Volume")
            }
        }
    }

    Rel(frontend, backend, "Вызывает API", "HTTP / JSON")
    Rel(backend, db, "Читает и записывает данные", "SQL")

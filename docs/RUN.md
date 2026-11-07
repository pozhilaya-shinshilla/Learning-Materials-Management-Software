# Инструкция по запуску

Сервис управления учебными материалами: REST API на FastAPI, PostgreSQL, веб-интерфейс на React.

## Docker

Нужен Docker с Docker Compose. Поднимает всё сразу: базу, API и веб-интерфейс.

```bash
git clone <ссылка на репозиторий>
cd <папка проекта>

cp .env.example .env          # Windows: copy .env.example .env
# откройте .env и задайте свой ADMIN_PASSWORD

docker compose up -d --build
```

После запуска:

- веб-интерфейс: http://localhost:8000/
- Swagger UI (документация API): http://localhost:8000/docs

Администратор создаётся при первом запуске из `ADMIN_LOGIN`, `ADMIN_EMAIL` и `ADMIN_PASSWORD` в `.env`.
Пароль должен быть не короче 8 символов, с заглавной буквой, цифрой и специальным символом.
Если `ADMIN_PASSWORD` не задан, приложение сообщит об этом и завершится.

Остановка: `docker compose down`.
Полный сброс вместе с данными: `docker compose down -v`.

## Тесты

```bash
uv run pytest                  # обычный прогон, БД не нужна
uv run pytest -m db            # тесты на настоящем PostgreSQL (нужен docker compose up -d db)
uv run pytest -m "not fuzz"    # без долгого перебора запросов Schemathesis
uv run pytest --cov            # с покрытием
```

Тестовая база (`TEST_DATABASE_URL`, по умолчанию `lms_test`) пересоздаётся при прогоне.
Не указывайте в ней рабочую базу.

## Настройки (`.env`)

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `ADMIN_LOGIN` | логин администратора | `admin` |
| `ADMIN_EMAIL` | email администратора | `admin@example.org` |
| `ADMIN_PASSWORD` | пароль администратора (обязателен) | нет |
| `DATABASE_URL` | подключение к PostgreSQL | `postgresql+psycopg://lms:lms@localhost:5432/lms` |
| `TEST_DATABASE_URL` | база для тестов | `.../lms_test` |
| `APP_HOST`, `APP_PORT` | адрес и порт сервера | `127.0.0.1`, `8000` |
| `DB_WAIT_SECONDS` | сколько ждать базу при старте | `30` |
| `AUTO_MIGRATE` | применять миграции при старте (0 — отключить) | `1` |
| `APP_TIMEZONE` | часовой пояс для фильтра по датам | `Europe/Volgograd` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, `SMTP_USER`, `SMTP_PASSWORD` | почта | не заданы |

## Восстановление пароля без почты

Если `SMTP_HOST` не задан, письма не отправляются: код восстановления печатается в консоль сервера
строкой `[ПОЧТА, имитация отправки]`. Введите его на странице `/reset-password`.
В Docker смотрите вывод командой `docker compose logs app`.

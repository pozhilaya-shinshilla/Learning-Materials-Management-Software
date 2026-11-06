# Образ приложения: REST API + консоль. Веб-интерфейс собирается отдельно (frontend/Dockerfile, nginx).
# Запуск: `docker compose up -d`.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# Менеджер зависимостей uv берётся из официального образа.
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

WORKDIR /app

# Сначала зависимости: слой кешируется и не пересобирается при правках кода.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY migrations ./migrations
COPY src ./src

# Приложение работает не от root; в /app/data лежат загруженные файлы (том docker-compose).
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/data \
    && chown -R app:app /app/data
USER app

ENV PATH="/app/.venv/bin:$PATH" \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"APP_PORT\"]}/api/health', timeout=3)"

# Ждёт базу данных, применяет миграции и запускает сервер (см. src/main.py).
CMD ["python", "-m", "src.main"]

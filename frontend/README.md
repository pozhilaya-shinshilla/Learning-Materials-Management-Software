# Веб-интерфейс «Учебные материалы»

SPA для трёх ролей (студент, преподаватель, администратор). React + TypeScript + Vite,
Tailwind CSS v4, shadcn/ui (Radix), react-router, TanStack Query, react-hook-form + zod, axios, lucide-react.
Интерфейс на русском, адаптивный от 320 px, светлая и тёмная темы.

## Как открыть

В Docker интерфейс собирает и раздаёт контейнер `web` (nginx, `frontend/Dockerfile` и `frontend/nginx.conf`) на
**http://localhost:8000/**; он же проксирует `/api` и Swagger UI (`/docs`) в контейнер приложения. FastAPI статику не раздаёт.

- **Docker:** из корня проекта `docker compose up -d --build`.
- **Без Docker:** нужны Node.js 20+ и запущенное API (`uv run python -m src.main`, порт 8000).
  ```bash
  cd frontend
  npm ci
  npm run dev                       # http://localhost:5173
  # или: npm run build && npm run preview   # http://localhost:4173
  ```
  Оба режима проксируют `/api` на `http://localhost:8000`.

## Разработка

```bash
npm run dev        # http://localhost:5173, запросы /api проксируются на http://localhost:8000
npm run preview    # готовая сборка на http://localhost:4173 с тем же прокси
npm run typecheck  # tsc --noEmit
npm run lint       # eslint
npm run build      # tsc + vite build
npm run tokens     # пересобрать src/styles/tokens.css из design-tokens.json
```

Для `npm run dev` сервер API должен быть запущен на порту 8000.

## Вход и восстановление пароля

Администратор создаётся при первом запуске из `ADMIN_LOGIN` / `ADMIN_PASSWORD` в `.env`.
Если SMTP не настроен, письмо с кодом восстановления не отправляется, а код печатается в консоль
сервера строкой `[ПОЧТА, имитация отправки]`. Введите его на странице `/reset-password`
(ссылка из письма вида `/reset-password?token=...` подставляет код сама).

## Структура `src/`

- `api/` — клиент axios, типы ответов, обработка ошибок (оба формата), запросы и мутации TanStack Query;
- `auth/` — сессия в `sessionStorage`, контекст, выход при любом 401;
- `components/ui/` — компоненты в стиле shadcn/ui; `components/app/` — оболочка, списки, формы;
- `pages/` — страницы маршрутов; `hooks/`, `lib/` — вспомогательный код (форматы дат Europe/Volgograd, валидация);
- `styles/tokens.css` — сгенерированные токены, `index.css` — Tailwind и базовые стили.

## Поддерживаемые браузеры

Chrome/Edge 90+, Firefox 88+, Safari 14+, Яндекс Браузер 21+ (`build.target` в `vite.config.ts`).

# Образ веб-интерфейса: сборка React + Vite (node) и раздача статики через nginx.
# nginx проксирует /api, /docs, /redoc и /openapi.json на контейнер приложения (сервис `app`).

FROM node:22-slim AS build
WORKDIR /frontend
COPY package.json package-lock.json ./
RUN npm ci
COPY . ./
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /frontend/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1

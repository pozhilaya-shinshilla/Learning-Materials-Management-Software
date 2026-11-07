import axios from 'axios'
import { clearSession, getToken, setFlash } from '@/auth/storage'

export const http = axios.create({ baseURL: '/api', timeout: 30_000 })

// Эти запросы идут без токена; 401 на них означает «неверные данные», а не «сессия кончилась».
const PUBLIC_PATHS = ['/auth/login', '/auth/password/recovery', '/auth/password/reset']

let onUnauthorized: (() => void) | null = null
export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler
}

http.interceptors.request.use((config) => {
  const token = getToken()
  if (token && !PUBLIC_PATHS.includes(config.url ?? '')) {
    config.headers.set('Authorization', `Bearer ${token}`)
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (axios.isAxiosError(error) && error.response) {
      const { status, data } = error.response
      const url = error.config?.url ?? ''
      const isPrivate = !PUBLIC_PATHS.includes(url) && getToken() !== null
      // Любой 401 вне публичных запросов: токен истёк, отозван или учётная запись удалена.
      if (status === 401 && isPrivate) {
        clearSession()
        setFlash('Войдите снова.')
        onUnauthorized?.()
      }
      // Учётную запись заблокировали посреди сеанса: сервер отвечает 403 с этим кодом.
      const body = data as { detail?: unknown; code?: string } | null
      if (status === 403 && body?.code === 'AccountBlockedError' && isPrivate) {
        clearSession()
        setFlash(typeof body.detail === 'string' ? body.detail : 'Учётная запись заблокирована.')
        onUnauthorized?.()
      }
    }
    return Promise.reject(error)
  },
)

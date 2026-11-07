import type { User } from '@/api/types'

const TOKEN_KEY = 'lms-token'
const USER_KEY = 'lms-user'
const FLASH_KEY = 'lms-flash'

// sessionStorage может бросать исключения (приватное окно, запрет): всё в try/catch.
function read(key: string): string | null {
  try {
    return sessionStorage.getItem(key)
  } catch {
    return null
  }
}
function write(key: string, value: string | null) {
  try {
    if (value === null) sessionStorage.removeItem(key)
    else sessionStorage.setItem(key, value)
  } catch {
    /* хранилище недоступно: сессия живёт до обновления страницы */
  }
}

// Запасной вариант в памяти, если sessionStorage недоступен.
let memory: { token: string; user: User } | null = null

export function loadSession(): { token: string; user: User } | null {
  const token = read(TOKEN_KEY)
  const raw = read(USER_KEY)
  if (token && raw) {
    try {
      return { token, user: JSON.parse(raw) as User }
    } catch {
      /* повреждённые данные игнорируем */
    }
  }
  return memory
}

export function saveSession(token: string, user: User) {
  memory = { token, user }
  write(TOKEN_KEY, token)
  write(USER_KEY, JSON.stringify(user))
}

export function clearSession() {
  memory = null
  write(TOKEN_KEY, null)
  write(USER_KEY, null)
}

export function getToken(): string | null {
  return loadSession()?.token ?? null
}

/** Сообщение для экрана входа («Войдите снова») после сброса сессии. */
export function setFlash(message: string | null) {
  write(FLASH_KEY, message)
}
export function takeFlash(): string | null {
  const value = read(FLASH_KEY)
  if (value) write(FLASH_KEY, null)
  return value
}

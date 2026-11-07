import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '@/api/endpoints'
import { setUnauthorizedHandler } from '@/api/client'
import type { Material, Role, User } from '@/api/types'
import { clearSession, getToken, loadSession, saveSession } from './storage'

interface AuthState {
  user: User | null
  login: (login: string, password: string) => Promise<User>
  logout: () => Promise<void>
  hasRole: (...roles: Role[]) => boolean
  /** Можно ли менять и удалять материал: админ — любой, преподаватель — только свой. */
  canModify: (material: Material) => boolean
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => loadSession()?.user ?? null)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  // Любой 401 (кроме входа и восстановления) сбрасывает сессию и ведёт на /login.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null)
      queryClient.clear()
      navigate('/login', { replace: true })
    })
    return () => setUnauthorizedHandler(null)
  }, [navigate, queryClient])

  // Роль и статус берём у сервера (GET /api/auth/me): при запуске и при возвращении на вкладку.
  // 401 и 403 обработает общий перехватчик ответов.
  const signedIn = user !== null
  useEffect(() => {
    if (!signedIn) return
    let cancelled = false
    const refresh = () => {
      const token = getToken()
      if (!token || document.visibilityState === 'hidden') return
      authApi
        .me()
        .then((fresh) => {
          if (cancelled) return
          saveSession(token, fresh)
          setUser((current) => {
            if (!current) return current
            const same = current.id === fresh.id && current.role === fresh.role && current.status === fresh.status
            if (!same) void queryClient.invalidateQueries()
            return same ? current : fresh
          })
        })
        .catch(() => {
          /* сеть недоступна: остаёмся с сохранёнными данными */
        })
    }
    refresh()
    document.addEventListener('visibilitychange', refresh)
    return () => {
      cancelled = true
      document.removeEventListener('visibilitychange', refresh)
    }
  }, [signedIn, queryClient])

  const login = useCallback(
    async (loginValue: string, password: string) => {
      const response = await authApi.login(loginValue, password)
      queryClient.clear()
      saveSession(response.access_token, response.user)
      setUser(response.user)
      return response.user
    },
    [queryClient],
  )

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } catch {
      /* токен всё равно забываем на клиенте */
    }
    clearSession()
    setUser(null)
    queryClient.clear()
    navigate('/login', { replace: true })
  }, [navigate, queryClient])

  const value = useMemo<AuthState>(
    () => ({
      user,
      login,
      logout,
      hasRole: (...roles) => !!user && roles.includes(user.role),
      canModify: (m) => !!user && (user.role === 'admin' || (user.role === 'teacher' && m.author_id === user.id)),
    }),
    [user, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth вне AuthProvider')
  return ctx
}

export function useCurrentUser(): User {
  const { user } = useAuth()
  if (!user) throw new Error('Нет пользователя')
  return user
}

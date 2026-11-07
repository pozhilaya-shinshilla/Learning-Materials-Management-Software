import { Navigate, useLocation } from 'react-router-dom'
import { Link } from 'react-router-dom'
import { ShieldAlert, SearchX } from 'lucide-react'
import type { ReactNode } from 'react'
import type { Role } from '@/api/types'
import { useAuth } from '@/auth/AuthContext'
import { Button } from '@/components/ui/button'
import { usePageTitle } from '@/hooks/usePageTitle'
import { EmptyState } from './states'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const location = useLocation()
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  return <>{children}</>
}

/** Маршрут только для указанных ролей; остальным показывается экран «Нет доступа». */
export function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user } = useAuth()
  if (!user || !roles.includes(user.role)) return <Forbidden />
  return <>{children}</>
}

export function Forbidden() {
  usePageTitle('Нет доступа')
  return (
    <EmptyState
      icon={<ShieldAlert />}
      title="Нет доступа"
      action={
        <Button asChild>
          <Link to="/">В каталог</Link>
        </Button>
      }
    >
      У вашей роли нет прав на этот раздел. Если он нужен для работы, обратитесь к администратору.
    </EmptyState>
  )
}

export function NotFound({ title = 'Страница не найдена', text = 'Проверьте адрес или вернитесь в каталог.' }: { title?: string; text?: string }) {
  usePageTitle(title)
  return (
    <EmptyState
      icon={<SearchX />}
      title={title}
      action={
        <Button asChild>
          <Link to="/">В каталог</Link>
        </Button>
      }
    >
      {text}
    </EmptyState>
  )
}

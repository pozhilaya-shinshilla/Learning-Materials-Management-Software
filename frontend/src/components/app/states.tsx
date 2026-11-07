import { AlertTriangle, RefreshCw } from 'lucide-react'
import type { ReactNode } from 'react'
import { toApiError } from '@/api/errors'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'

export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl sm:text-3xl">{title}</h1>
        {description ? <p className="mt-1 text-muted-foreground">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  )
}

export function EmptyState({ icon, title, children, action }: { icon: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border px-4 py-12 text-center">
      <div className="text-muted-foreground [&_svg]:size-10" aria-hidden="true">
        {icon}
      </div>
      <h2 className="text-lg">{title}</h2>
      {children ? <p className="max-w-md text-muted-foreground">{children}</p> : null}
      {action}
    </div>
  )
}

/** Ошибка загрузки с кнопкой «Повторить» (особенно для сетевых сбоев). */
export function ErrorState({ error, onRetry, className }: { error: unknown; onRetry?: () => void; className?: string }) {
  const e = toApiError(error)
  return (
    <div role="alert" className={cn('flex flex-col items-center gap-3 rounded-lg border border-destructive px-4 py-10 text-center', className)}>
      <AlertTriangle className="size-9 text-destructive" aria-hidden="true" />
      <h2 className="text-lg">{e.network ? 'Нет связи с сервером' : 'Не удалось загрузить данные'}</h2>
      <p className="max-w-md text-muted-foreground">{e.message}</p>
      {onRetry ? (
        <Button variant="outline" onClick={onRetry}>
          <RefreshCw aria-hidden="true" /> Повторить
        </Button>
      ) : null}
    </div>
  )
}

export function FormError({ message }: { message?: string | null }) {
  if (!message) return null
  return (
    <div role="alert" className="flex gap-2 rounded-md border border-destructive p-3 text-sm text-destructive">
      <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <span>{message}</span>
    </div>
  )
}

export function CardsSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2" role="status" aria-label="Загрузка">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
          <Skeleton className="h-5 w-3/4" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-11 w-full" />
        </div>
      ))}
    </div>
  )
}

export function TableSkeleton({ rows = 8 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-3" role="status" aria-label="Загрузка">
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-11 w-full" />
      ))}
    </div>
  )
}

import { ArrowLeft, Pencil, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toApiError } from '@/api/errors'
import { useDeleteMaterial } from '@/api/mutations'
import { useMaterial } from '@/api/queries'
import { useAuth } from '@/auth/AuthContext'
import { ConfirmDialog } from '@/components/app/ConfirmDialog'
import { DownloadButton, FavoriteButton, FileTypeBadge } from '@/components/app/material-parts'
import { useAuthorLabel, useCatalogNames } from '@/components/app/material-hooks'
import { NotFound } from '@/components/app/guards'
import { ErrorState } from '@/components/app/states'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { usePageTitle } from '@/hooks/usePageTitle'
import { formatDateTime, formatFileSize } from '@/lib/format'
import { notifyError } from '@/lib/errors-ui'

export default function MaterialDetailPage() {
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const { canModify } = useAuth()
  const query = useMaterial(id)
  const names = useCatalogNames()
  const authorLabel = useAuthorLabel()
  const [confirm, setConfirm] = useState(false)
  const del = useDeleteMaterial(() => navigate('/', { replace: true }))
  usePageTitle(query.data?.title ?? 'Материал')

  if (query.isLoading) {
    return (
      <div className="flex flex-col gap-4" role="status" aria-label="Загрузка">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }
  if (query.isError) {
    if (toApiError(query.error).status === 404) return <NotFound title="Материал не найден" text="Возможно, его удалили или ссылка неверна." />
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  }
  const m = query.data
  if (!m) return null
  const author = authorLabel(m)
  const rows: [string, React.ReactNode][] = [
    ['Дисциплина', names.discipline(m.discipline_id)],
    ['Тема', names.topic(m.topic_id)],
    ['Файл', <span key="f" className="break-all">{m.file_name}</span>],
    ['Размер', formatFileSize(m.file_size_bytes)],
    ['Загружен', formatDateTime(m.uploaded_at)],
  ]
  if (author) rows.push(['Автор', author])

  return (
    <article className="flex flex-col gap-5">
      <Button asChild variant="ghost" className="-ml-3 self-start">
        <Link to="/">
          <ArrowLeft aria-hidden="true" /> К каталогу
        </Link>
      </Button>
      <header className="flex flex-col gap-2">
        <FileTypeBadge type={m.file_type} />
        <h1 className="text-2xl sm:text-3xl">{m.title}</h1>
      </header>

      <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
        <Card className="p-4 sm:p-5">
          <h2 className="mb-2 text-lg">Описание</h2>
          {m.description ? <p className="whitespace-pre-wrap">{m.description}</p> : <p className="text-muted-foreground">Описание не указано.</p>}
        </Card>
        <Card className="flex flex-col gap-4 p-4 sm:p-5">
          <dl className="grid gap-3 text-sm">
            {rows.map(([k, v]) => (
              <div key={k}>
                <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
          <div className="flex flex-wrap gap-2">
            <DownloadButton material={m} variant="default" />
            <FavoriteButton material={m} />
          </div>
          {canModify(m) ? (
            <div className="flex flex-wrap gap-2 border-t border-border pt-4">
              <Button asChild variant="outline">
                <Link to={`/manage/edit/${m.id}`}>
                  <Pencil aria-hidden="true" /> Изменить
                </Link>
              </Button>
              <Button variant="outline" className="text-destructive" onClick={() => setConfirm(true)}>
                <Trash2 aria-hidden="true" /> Удалить
              </Button>
            </div>
          ) : null}
        </Card>
      </div>

      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title="Удалить материал?"
        description={`«${m.title}» будет удалён вместе с файлом. Это действие нельзя отменить.`}
        confirmLabel="Удалить"
        pending={del.isPending}
        onConfirm={() => del.mutate(m, { onError: (e) => { setConfirm(false); notifyError(e, 'Не удалось удалить материал') } })}
      />
    </article>
  )
}

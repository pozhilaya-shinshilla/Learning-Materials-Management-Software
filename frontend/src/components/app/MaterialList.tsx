import { Link } from 'react-router-dom'
import type { Material } from '@/api/types'
import { Card } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useIsWide } from '@/hooks/useMediaQuery'
import { formatDate, formatDateTime, formatFileSize } from '@/lib/format'
import { DownloadButton, FavoriteButton, FileTypeBadge } from './material-parts'
import { useAuthorLabel, useCatalogNames } from './material-hooks'

/**
 * Список материалов: карточки на узком экране, таблица на широком.
 * `actions` — дополнительные кнопки строки (изменить, удалить).
 */
export function MaterialList({
  materials,
  actions,
}: {
  materials: Material[]
  actions?: (material: Material) => React.ReactNode
}) {
  const wide = useIsWide()
  const names = useCatalogNames()
  const authorLabel = useAuthorLabel()
  const showAuthor = materials.some((m) => authorLabel(m) !== null)

  if (wide) {
    return (
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-muted">
            <TableHead>Название</TableHead>
            <TableHead>Дисциплина и тема</TableHead>
            <TableHead>Формат</TableHead>
            <TableHead>Загружен</TableHead>
            {showAuthor ? <TableHead>Автор</TableHead> : null}
            <TableHead className="text-right">Действия</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {materials.map((m) => (
            <TableRow key={m.id}>
              <TableCell className="max-w-md">
                <Link
                  to={`/materials/${m.id}`}
                  title={m.title}
                  className="line-clamp-2 min-h-11 content-center font-semibold text-primary underline-offset-4 hover:underline"
                >
                  {m.title}
                </Link>
                {m.description ? (
                  <p title={m.description} className="line-clamp-1 text-xs text-muted-foreground">
                    {m.description}
                  </p>
                ) : null}
              </TableCell>
              <TableCell className="max-w-56">
                <div className="truncate" title={names.discipline(m.discipline_id)}>
                  {names.discipline(m.discipline_id)}
                </div>
                <div className="truncate text-xs text-muted-foreground" title={names.topic(m.topic_id)}>
                  {names.topic(m.topic_id)}
                </div>
              </TableCell>
              <TableCell className="whitespace-nowrap">
                <FileTypeBadge type={m.file_type} />
                <span className="ml-2 text-xs text-muted-foreground">{formatFileSize(m.file_size_bytes)}</span>
              </TableCell>
              <TableCell className="whitespace-nowrap text-muted-foreground">{formatDate(m.uploaded_at)}</TableCell>
              {showAuthor ? <TableCell className="max-w-40 truncate text-muted-foreground">{authorLabel(m) ?? ''}</TableCell> : null}
              <TableCell>
                <div className="flex items-center justify-end gap-1">
                  <FavoriteButton material={m} />
                  <DownloadButton material={m} iconOnly />
                  {actions?.(m)}
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    )
  }

  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {materials.map((m) => {
        const author = authorLabel(m)
        return (
          <li key={m.id} className="min-w-0">
            <Card className="flex h-full flex-col gap-3 p-4">
              <div className="min-w-0">
                <Link
                  to={`/materials/${m.id}`}
                  title={m.title}
                  className="-my-2.5 block line-clamp-3 py-2.5 font-serif text-lg font-semibold leading-snug text-primary underline-offset-4 hover:underline"
                >
                  {m.title}
                </Link>
                {m.description ? <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{m.description}</p> : null}
              </div>
              <dl className="grid gap-1 text-sm">
                <div className="flex gap-2">
                  <dt className="sr-only">Дисциплина и тема</dt>
                  <dd className="min-w-0 break-words">
                    {names.discipline(m.discipline_id)} <span className="text-muted-foreground">· {names.topic(m.topic_id)}</span>
                  </dd>
                </div>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-muted-foreground">
                  <dt className="sr-only">Файл</dt>
                  <dd className="flex items-center gap-2">
                    <FileTypeBadge type={m.file_type} /> {formatFileSize(m.file_size_bytes)}
                  </dd>
                  <dt className="sr-only">Загружен</dt>
                  <dd>{formatDateTime(m.uploaded_at)}</dd>
                  {author ? (
                    <>
                      <dt className="sr-only">Автор</dt>
                      <dd>{author}</dd>
                    </>
                  ) : null}
                </div>
              </dl>
              <div className="mt-auto flex flex-wrap items-center gap-1 pt-1">
                <DownloadButton material={m} />
                <FavoriteButton material={m} />
                {actions?.(m)}
              </div>
            </Card>
          </li>
        )
      })}
    </ul>
  )
}

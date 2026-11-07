import { Download, FileImage, FileSpreadsheet, FileText, Presentation, Star } from 'lucide-react'
import type { ReactNode } from 'react'
import { useToggleFavorite, useFavorites } from '@/api/queries'
import type { FileType, Material } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { notifyError } from '@/lib/errors-ui'
import { cn } from '@/lib/utils'
import { useDownload } from './material-hooks'

const TYPE_ICON: Record<FileType, ReactNode> = {
  pdf: <FileText aria-hidden="true" />,
  docx: <FileText aria-hidden="true" />,
  pptx: <Presentation aria-hidden="true" />,
  xlsx: <FileSpreadsheet aria-hidden="true" />,
  jpg: <FileImage aria-hidden="true" />,
  png: <FileImage aria-hidden="true" />,
}

export function FileTypeBadge({ type }: { type: FileType }) {
  return (
    <Badge variant="outline" className="uppercase [&_svg]:size-3.5">
      {TYPE_ICON[type]}
      {type}
    </Badge>
  )
}

/** Звёздочка: состояние берётся из загруженного списка избранного, обновляется оптимистично. */
export function FavoriteButton({ material, className }: { material: Material; className?: string }) {
  const favorites = useFavorites()
  const toggle = useToggleFavorite()
  const active = (favorites.data ?? []).some((m) => m.id === material.id)
  const label = active ? 'Убрать из избранного' : 'Добавить в избранное'
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={`${label}: ${material.title}`}
      title={label}
      aria-pressed={active}
      disabled={favorites.isLoading}
      className={className}
      onClick={() => toggle.mutate({ material, add: !active }, { onError: (e) => notifyError(e, 'Не удалось изменить избранное') })}
    >
      <Star aria-hidden="true" className={cn(active && 'fill-highlight text-highlight')} />
    </Button>
  )
}

export function DownloadButton({ material, iconOnly, variant = 'outline' }: { material: Material; iconOnly?: boolean; variant?: 'outline' | 'default' }) {
  const { download, pendingId } = useDownload()
  const pending = pendingId === material.id
  return (
    <Button
      variant={variant}
      size={iconOnly ? 'icon' : 'default'}
      disabled={pending}
      aria-label={iconOnly ? `Скачать: ${material.title}` : undefined}
      title={iconOnly ? 'Скачать' : undefined}
      onClick={() => void download(material)}
    >
      <Download aria-hidden="true" />
      {iconOnly ? null : pending ? 'Скачивание…' : 'Скачать'}
    </Button>
  )
}

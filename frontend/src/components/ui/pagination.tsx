import { ChevronLeft, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from './button'

function pageWindow(page: number, count: number): (number | 'gap')[] {
  const set = new Set([1, count, page - 1, page, page + 1])
  const pages = [...set].filter((p) => p >= 1 && p <= count).sort((a, b) => a - b)
  const out: (number | 'gap')[] = []
  pages.forEach((p, i) => {
    const prev = pages[i - 1]
    if (prev !== undefined && p - prev > 1) out.push('gap')
    out.push(p)
  })
  return out
}

export function Pagination({
  page,
  pageCount,
  onChange,
  className,
}: {
  page: number
  pageCount: number
  onChange: (page: number) => void
  className?: string
}) {
  if (pageCount <= 1) return null
  return (
    <nav aria-label="Страницы" className={cn('flex flex-wrap items-center justify-center gap-1', className)}>
      <Button variant="outline" size="icon" aria-label="Предыдущая страница" disabled={page <= 1} onClick={() => onChange(page - 1)}>
        <ChevronLeft aria-hidden="true" />
      </Button>
      {pageWindow(page, pageCount).map((p, i) =>
        p === 'gap' ? (
          <span key={`gap-${i}`} aria-hidden="true" className="px-1 text-muted-foreground">
            …
          </span>
        ) : (
          <Button
            key={p}
            variant={p === page ? 'default' : 'ghost'}
            size="icon"
            aria-label={`Страница ${p}`}
            aria-current={p === page ? 'page' : undefined}
            onClick={() => onChange(p)}
          >
            {p}
          </Button>
        ),
      )}
      <Button variant="outline" size="icon" aria-label="Следующая страница" disabled={page >= pageCount} onClick={() => onChange(page + 1)}>
        <ChevronRight aria-hidden="true" />
      </Button>
    </nav>
  )
}

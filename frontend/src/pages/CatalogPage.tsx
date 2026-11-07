import { FilterX, LibraryBig, Plus, Search, SlidersHorizontal } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useDisciplines, useMaterials, useTopics } from '@/api/queries'
import type { FileType, MaterialQuery } from '@/api/types'
import { useAuth } from '@/auth/AuthContext'
import { FilterSelect } from '@/components/app/FilterSelect'
import { MaterialList } from '@/components/app/MaterialList'
import { CardsSkeleton, EmptyState, ErrorState, PageHeader, TableSkeleton } from '@/components/app/states'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Pagination } from '@/components/ui/pagination'
import { useDebounced } from '@/hooks/useDebounced'
import { useIsWide } from '@/hooks/useMediaQuery'
import { PAGE_SIZE } from '@/hooks/usePaging'
import { FILE_TYPES, SORT_OPTIONS } from '@/lib/labels'
import { pluralize } from '@/lib/format'
import { cn } from '@/lib/utils'

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/

export default function CatalogPage() {
  const { hasRole } = useAuth()
  const [params, setParams] = useSearchParams()
  const wide = useIsWide()
  const [filtersOpen, setFiltersOpen] = useState(false)

  const q = params.get('q') ?? ''
  const discipline = params.get('discipline') ?? ''
  const topic = params.get('topic') ?? ''
  const type = params.get('type') ?? ''
  const from = params.get('from') ?? ''
  const to = params.get('to') ?? ''
  const sort = params.get('sort') ?? 'new'
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1)

  // Поиск уходит на сервер с задержкой 300 мс.
  const [qInput, setQInput] = useState(q)
  const debouncedQ = useDebounced(qInput, 300)

  function update(changes: Record<string, string>, resetPage = true) {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        for (const [k, v] of Object.entries(changes)) {
          if (v === '' || (k === 'sort' && v === 'new')) next.delete(k)
          else next.set(k, v)
        }
        if (resetPage) next.delete('page')
        return next
      },
      { replace: true },
    )
  }

  useEffect(() => {
    if (debouncedQ.trim() !== q) update({ q: debouncedQ.trim() })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedQ])

  const disciplines = useDisciplines()
  const topics = useTopics()
  const topicOptions = useMemo(
    () => (topics.data ?? []).filter((t) => String(t.discipline_id) === discipline).map((t) => ({ value: String(t.id), label: t.name })),
    [topics.data, discipline],
  )

  const dateOrderBroken = DATE_RE.test(from) && DATE_RE.test(to) && to < from
  const sortOption = SORT_OPTIONS.find((o) => o.value === sort) ?? SORT_OPTIONS[0]!
  // На сервер уходят только заданные параметры: неизвестные и лишние он отклоняет (422).
  const query: MaterialQuery = {
    ...(q ? { q } : {}),
    ...(discipline ? { discipline_id: Number(discipline) } : {}),
    ...(topic ? { topic_id: Number(topic) } : {}),
    ...(type ? { file_type: type as FileType } : {}),
    ...(DATE_RE.test(from) && !dateOrderBroken ? { uploaded_from: from } : {}),
    ...(DATE_RE.test(to) && !dateOrderBroken ? { uploaded_to: to } : {}),
    ...(sortOption.value !== 'new' ? { sort_by: sortOption.sort_by, order: sortOption.order } : {}),
    limit: PAGE_SIZE,
    offset: (Math.max(1, page) - 1) * PAGE_SIZE,
  }
  const result = useMaterials(query)

  const activeCount = [discipline, topic, type, from, to].filter(Boolean).length
  const hasFilters = activeCount > 0 || q !== ''
  const slice = result.data?.items ?? []
  const total = result.data?.total ?? 0
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const current = Math.min(page, pageCount)

  // Страница за пределами результата (например, после смены фильтра по ссылке): возвращаемся на последнюю.
  useEffect(() => {
    if (result.data && !result.isPlaceholderData && page > pageCount) update({ page: String(pageCount) }, false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result.data, result.isPlaceholderData, page, pageCount])

  function reset() {
    setQInput('')
    setParams({}, { replace: true })
  }

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title="Каталог материалов" description="Лекции, методические указания и другие учебные материалы кафедры." />

      <section aria-label="Поиск и фильтры" className="flex flex-col gap-3 rounded-lg border border-border bg-card p-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="catalog-search">Поиск по названию и описанию</Label>
          <div className="flex gap-2">
            <div className="relative min-w-0 flex-1">
              <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="catalog-search"
                type="search"
                className="pl-9"
                placeholder="Например: лекция, дифференциальные"
                value={qInput}
                onChange={(e) => setQInput(e.target.value)}
                maxLength={200}
                autoComplete="off"
              />
            </div>
            <Button
              variant="outline"
              className="lg:hidden"
              aria-expanded={filtersOpen}
              aria-controls="catalog-filters"
              onClick={() => setFiltersOpen((v) => !v)}
            >
              <SlidersHorizontal aria-hidden="true" />
              Фильтры{activeCount ? ` (${activeCount})` : ''}
            </Button>
          </div>
        </div>

        <div id="catalog-filters" className={cn('grid-cols-1 gap-3 sm:grid-cols-2 lg:grid lg:grid-cols-4', filtersOpen || wide ? 'grid' : 'hidden')}>
          <FilterSelect
            id="f-discipline"
            label="Дисциплина"
            allLabel="Все дисциплины"
            value={discipline}
            onChange={(v) => update({ discipline: v, topic: '' })}
            options={(disciplines.data ?? []).map((d) => ({ value: String(d.id), label: d.name }))}
          />
          <FilterSelect
            id="f-topic"
            label="Тема"
            allLabel={discipline ? 'Все темы' : 'Сначала выберите дисциплину'}
            value={topic}
            onChange={(v) => update({ topic: v })}
            options={topicOptions}
            disabled={!discipline}
          />
          <FilterSelect
            id="f-type"
            label="Тип файла"
            allLabel="Любой тип"
            value={type}
            onChange={(v) => update({ type: v })}
            options={FILE_TYPES.map((t) => ({ value: t, label: t.toUpperCase() }))}
          />
          <FilterSelect
            id="f-sort"
            label="Сортировка"
            allLabel={SORT_OPTIONS[0]!.label}
            value={sort === 'new' ? '' : sort}
            onChange={(v) => update({ sort: v || 'new' })}
            options={SORT_OPTIONS.slice(1).map((o) => ({ value: o.value, label: o.label }))}
          />
          <div className="flex min-w-0 flex-col gap-1.5">
            <Label htmlFor="f-from">Загружен с</Label>
            <Input id="f-from" type="date" value={from} max={to || undefined} onChange={(e) => update({ from: e.target.value })} />
          </div>
          <div className="flex min-w-0 flex-col gap-1.5">
            <Label htmlFor="f-to">Загружен по</Label>
            <Input
              id="f-to"
              type="date"
              value={to}
              min={from || undefined}
              aria-invalid={dateOrderBroken}
              aria-describedby={dateOrderBroken ? 'f-date-error' : undefined}
              onChange={(e) => update({ to: e.target.value })}
            />
          </div>
          <div className="flex items-end sm:col-span-2">
            <Button variant="ghost" onClick={reset} disabled={!hasFilters}>
              <FilterX aria-hidden="true" /> Сбросить
            </Button>
          </div>
          {dateOrderBroken ? (
            <p id="f-date-error" role="alert" className="text-sm font-medium text-destructive sm:col-span-2 lg:col-span-4">
              Конечная дата не может быть раньше начальной.
            </p>
          ) : null}
        </div>
      </section>

      <div aria-live="polite" className="text-sm text-muted-foreground">
        {result.isSuccess ? (
          <>
            Найдено: {total} {pluralize(total, ['материал', 'материала', 'материалов'])}
          </>
        ) : null}
      </div>

      {result.isLoading ? (
        wide ? (
          <TableSkeleton />
        ) : (
          <CardsSkeleton />
        )
      ) : result.isError ? (
        <ErrorState error={result.error} onRetry={() => void result.refetch()} />
      ) : total === 0 ? (
        hasFilters ? (
          <EmptyState
            icon={<Search />}
            title="Ничего не найдено"
            action={
              <Button variant="outline" onClick={reset}>
                <FilterX aria-hidden="true" /> Сбросить фильтры
              </Button>
            }
          >
            Попробуйте изменить запрос или убрать часть фильтров.
          </EmptyState>
        ) : (
          <EmptyState
            icon={<LibraryBig />}
            title="Материалов пока нет"
            action={
              hasRole('teacher', 'admin') ? (
                <Button asChild>
                  <Link to="/manage?tab=add">
                    <Plus aria-hidden="true" /> Добавить материал
                  </Link>
                </Button>
              ) : undefined
            }
          >
            {hasRole('teacher', 'admin') ? 'Каталог пуст: загрузите первый материал.' : 'Преподаватели ещё ничего не загрузили. Загляните позже.'}
          </EmptyState>
        )
      ) : (
        <div className={cn(result.isFetching && 'opacity-70 transition-opacity')}>
          <MaterialList materials={slice} />
        </div>
      )}

      <Pagination page={current} pageCount={pageCount} onChange={(p) => update({ page: String(p) }, false)} />
    </div>
  )
}

import { ClipboardList, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useEvents, useUsers } from '@/api/queries'
import { FilterSelect } from '@/components/app/FilterSelect'
import { CardsSkeleton, EmptyState, ErrorState, PageHeader, TableSkeleton } from '@/components/app/states'
import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Pagination } from '@/components/ui/pagination'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useIsWide } from '@/hooks/useMediaQuery'
import { usePageTitle } from '@/hooks/usePageTitle'
import { usePaging } from '@/hooks/usePaging'
import { formatDateTime, parseServerDate } from '@/lib/format'

const PAGE = 20

export default function EventsPage() {
  usePageTitle('Журнал событий')
  const wide = useIsWide()
  const events = useEvents()
  const users = useUsers()
  const [search, setSearch] = useState('')
  const [type, setType] = useState('')
  const [userId, setUserId] = useState('')

  const logins = useMemo(() => new Map((users.data ?? []).map((u) => [u.id, u.login])), [users.data])
  const who = (id: number | null) => (id === null ? '—' : (logins.get(id) ?? `№${id} (удалён)`))

  const sorted = useMemo(
    () =>
      [...(events.data ?? [])].sort(
        (a, b) => parseServerDate(b.occurred_at).getTime() - parseServerDate(a.occurred_at).getTime() || b.id - a.id,
      ),
    [events.data],
  )
  const typeOptions = useMemo(() => {
    const seen = new Map<string, string>()
    for (const e of events.data ?? []) seen.set(e.event_type, e.description)
    return [...seen].map(([value, label]) => ({ value, label })).sort((a, b) => a.label.localeCompare(b.label, 'ru'))
  }, [events.data])

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return sorted.filter(
      (e) =>
        (!type || e.event_type === type) &&
        (!userId || String(e.user_id) === userId) &&
        (!needle || e.target.toLowerCase().includes(needle) || e.description.toLowerCase().includes(needle) || who(e.user_id).toLowerCase().includes(needle)),
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sorted, type, userId, search, logins])
  const paging = usePaging(filtered, `${search}|${type}|${userId}`, PAGE)

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title="Журнал событий" description="Входы, изменения материалов, действия администраторов. Новые записи сверху." />
      <section aria-label="Поиск и фильтры" className="grid gap-3 rounded-lg border border-border bg-card p-4 sm:grid-cols-3">
        <div className="flex min-w-0 flex-col gap-1.5">
          <Label htmlFor="e-search">Поиск по записям</Label>
          <div className="relative">
            <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input id="e-search" type="search" className="pl-9" value={search} onChange={(e) => setSearch(e.target.value)} autoComplete="off" />
          </div>
        </div>
        <FilterSelect id="e-type" label="Тип события" allLabel="Все события" value={type} onChange={setType} options={typeOptions} />
        <FilterSelect id="e-user" label="Пользователь" allLabel="Все пользователи" value={userId} onChange={setUserId} options={(users.data ?? []).map((u) => ({ value: String(u.id), label: u.login }))} />
      </section>

      <div aria-live="polite" className="text-sm text-muted-foreground">
        {events.isSuccess ? `Записей: ${filtered.length}` : null}
      </div>

      {events.isLoading ? (
        wide ? <TableSkeleton /> : <CardsSkeleton count={4} />
      ) : events.isError ? (
        <ErrorState error={events.error} onRetry={() => void events.refetch()} />
      ) : filtered.length === 0 ? (
        <EmptyState icon={<ClipboardList />} title="Записей нет">Журнал пуст или под фильтры ничего не подошло.</EmptyState>
      ) : wide ? (
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-muted">
              <TableHead>Время</TableHead>
              <TableHead>Пользователь</TableHead>
              <TableHead>Событие</TableHead>
              <TableHead>Объект</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paging.slice.map((e) => (
              <TableRow key={e.id}>
                <TableCell className="whitespace-nowrap text-muted-foreground">{formatDateTime(e.occurred_at)}</TableCell>
                <TableCell className="max-w-40 truncate font-semibold">{who(e.user_id)}</TableCell>
                <TableCell>{e.description}</TableCell>
                <TableCell className="max-w-md break-words text-muted-foreground">{e.target || '—'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {paging.slice.map((e) => (
            <li key={e.id} className="min-w-0">
              <Card className="flex flex-col gap-1 p-4">
                <p className="font-semibold">{e.description}</p>
                <p className="text-sm text-muted-foreground">{formatDateTime(e.occurred_at)} · {who(e.user_id)}</p>
                {e.target ? <p className="break-words text-sm">{e.target}</p> : null}
              </Card>
            </li>
          ))}
        </ul>
      )}
      <Pagination page={paging.page} pageCount={paging.pageCount} onChange={paging.setPage} />
    </div>
  )
}

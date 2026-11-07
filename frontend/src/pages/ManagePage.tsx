import { FilePlus2, Pencil, Search, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useDeleteMaterial } from '@/api/mutations'
import { useMaterials } from '@/api/queries'
import type { Material } from '@/api/types'
import { useAuth } from '@/auth/AuthContext'
import { CatalogManager } from '@/components/app/CatalogManager'
import { ConfirmDialog } from '@/components/app/ConfirmDialog'
import { MaterialForm } from '@/components/app/MaterialForm'
import { MaterialList } from '@/components/app/MaterialList'
import { CardsSkeleton, EmptyState, ErrorState, PageHeader } from '@/components/app/states'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Pagination } from '@/components/ui/pagination'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { usePageTitle } from '@/hooks/usePageTitle'
import { usePaging } from '@/hooks/usePaging'
import { notifyError } from '@/lib/errors-ui'

function MyMaterials() {
  const { user, hasRole, canModify } = useAuth()
  const query = useMaterials({})
  const [search, setSearch] = useState('')
  const [toDelete, setToDelete] = useState<Material | null>(null)
  const del = useDeleteMaterial(() => setToDelete(null))
  const isAdmin = hasRole('admin')

  // Преподавателю — только его материалы, администратору — все.
  const own = useMemo(
    () => (query.data?.items ?? []).filter((m) => isAdmin || m.author_id === user?.id),
    [query.data, isAdmin, user?.id],
  )
  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return needle ? own.filter((m) => m.title.toLowerCase().includes(needle)) : own
  }, [own, search])
  const paging = usePaging(filtered, search)

  if (query.isLoading) return <CardsSkeleton count={4} />
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />

  return (
    <div className="flex flex-col gap-4">
      {own.length === 0 ? (
        <EmptyState
          icon={<FilePlus2 />}
          title={isAdmin ? 'Материалов пока нет' : 'Вы ещё ничего не загрузили'}
          action={
            <Button asChild>
              <Link to="/manage?tab=add">Добавить материал</Link>
            </Button>
          }
        >
          Загруженные материалы появятся здесь, и их можно будет изменить или удалить.
        </EmptyState>
      ) : (
        <>
          <div className="flex max-w-md flex-col gap-1.5">
            <Label htmlFor="manage-search">Найти по названию</Label>
            <div className="relative">
              <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input id="manage-search" type="search" className="pl-9" value={search} onChange={(e) => setSearch(e.target.value)} autoComplete="off" />
            </div>
          </div>
          {filtered.length === 0 ? (
            <EmptyState icon={<Search />} title="Ничего не найдено">
              Среди ваших материалов нет подходящих под этот запрос.
            </EmptyState>
          ) : (
            <>
              <MaterialList
                materials={paging.slice}
                actions={(m) =>
                  canModify(m) ? (
                    <>
                      <Button asChild variant="ghost" size="icon" aria-label={`Изменить: ${m.title}`} title="Изменить">
                        <Link to={`/manage/edit/${m.id}`}>
                          <Pencil aria-hidden="true" />
                        </Link>
                      </Button>
                      <Button variant="ghost" size="icon" aria-label={`Удалить: ${m.title}`} title="Удалить" className="text-destructive" onClick={() => setToDelete(m)}>
                        <Trash2 aria-hidden="true" />
                      </Button>
                    </>
                  ) : null
                }
              />
              <Pagination page={paging.page} pageCount={paging.pageCount} onChange={paging.setPage} />
            </>
          )}
        </>
      )}
      <ConfirmDialog
        open={toDelete !== null}
        onOpenChange={(open) => !open && setToDelete(null)}
        title="Удалить материал?"
        description={toDelete ? `«${toDelete.title}» будет удалён вместе с файлом. Это действие нельзя отменить.` : ''}
        confirmLabel="Удалить"
        pending={del.isPending}
        onConfirm={() => toDelete && del.mutate(toDelete, { onError: (e) => { setToDelete(null); notifyError(e, 'Не удалось удалить материал') } })}
      />
    </div>
  )
}

export default function ManagePage() {
  usePageTitle('Управление материалами')
  const { hasRole } = useAuth()
  const [params, setParams] = useSearchParams()
  const tab = ['materials', 'add', 'catalog'].includes(params.get('tab') ?? '') ? (params.get('tab') as string) : 'materials'

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Управление материалами"
        description={hasRole('admin') ? 'Все материалы системы, добавление и справочники.' : 'Ваши материалы, добавление и справочники.'}
      />
      <Tabs value={tab} onValueChange={(v) => setParams(v === 'materials' ? {} : { tab: v }, { replace: true })}>
        <TabsList aria-label="Разделы управления">
          <TabsTrigger value="materials">{hasRole('admin') ? 'Все материалы' : 'Мои материалы'}</TabsTrigger>
          <TabsTrigger value="add">Добавить материал</TabsTrigger>
          <TabsTrigger value="catalog">Дисциплины и темы</TabsTrigger>
        </TabsList>
        <TabsContent value="materials">
          <MyMaterials />
        </TabsContent>
        <TabsContent value="add">
          <MaterialForm />
        </TabsContent>
        <TabsContent value="catalog">
          <CatalogManager />
        </TabsContent>
      </Tabs>
    </div>
  )
}

import { Star } from 'lucide-react'
import { Link } from 'react-router-dom'
import { useFavorites } from '@/api/queries'
import { MaterialList } from '@/components/app/MaterialList'
import { CardsSkeleton, EmptyState, ErrorState, PageHeader } from '@/components/app/states'
import { Button } from '@/components/ui/button'
import { Pagination } from '@/components/ui/pagination'
import { usePageTitle } from '@/hooks/usePageTitle'
import { usePaging } from '@/hooks/usePaging'

export default function FavoritesPage() {
  usePageTitle('Избранное')
  const query = useFavorites()
  const items = query.data ?? []
  const paging = usePaging(items, 'favorites')

  return (
    <div className="flex flex-col gap-5">
      <PageHeader title="Избранное" description="Материалы, которые вы отметили звёздочкой." />
      {query.isLoading ? (
        <CardsSkeleton count={4} />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Star />}
          title="В избранном пока пусто"
          action={
            <Button asChild>
              <Link to="/">Перейти в каталог</Link>
            </Button>
          }
        >
          Нажмите на звёздочку у материала, чтобы он появился здесь.
        </EmptyState>
      ) : (
        <>
          <MaterialList materials={paging.slice} />
          <Pagination page={paging.page} pageCount={paging.pageCount} onChange={paging.setPage} />
        </>
      )}
    </div>
  )
}

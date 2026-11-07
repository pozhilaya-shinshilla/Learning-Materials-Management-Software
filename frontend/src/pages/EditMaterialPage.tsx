import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { toApiError } from '@/api/errors'
import { useMaterial } from '@/api/queries'
import { useAuth } from '@/auth/AuthContext'
import { Forbidden, NotFound } from '@/components/app/guards'
import { MaterialForm } from '@/components/app/MaterialForm'
import { ErrorState, PageHeader } from '@/components/app/states'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { usePageTitle } from '@/hooks/usePageTitle'

export default function EditMaterialPage() {
  usePageTitle('Изменить материал')
  const id = Number(useParams().id)
  const { canModify } = useAuth()
  const query = useMaterial(id)

  if (query.isLoading) return <Skeleton className="h-64 w-full" />
  if (query.isError) {
    if (toApiError(query.error).status === 404) return <NotFound title="Материал не найден" />
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  }
  const material = query.data
  if (!material) return null
  // Чужие материалы преподаватель менять не может: форму не показываем.
  if (!canModify(material)) return <Forbidden />

  return (
    <div className="flex flex-col gap-5">
      <Button asChild variant="ghost" className="-ml-3 self-start">
        <Link to={`/materials/${material.id}`}>
          <ArrowLeft aria-hidden="true" /> К материалу
        </Link>
      </Button>
      <PageHeader title="Изменить материал" />
      <MaterialForm key={material.id} material={material} />
    </div>
  )
}

import { useCallback, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { materialsApi } from '@/api/endpoints'
import { useDisciplines, useTopics } from '@/api/queries'
import type { Material } from '@/api/types'
import { useAuth } from '@/auth/AuthContext'
import { notifyError } from '@/lib/errors-ui'

/** Названия дисциплин и тем по id (справочники кэшируются в TanStack Query). */
export function useCatalogNames() {
  const disciplines = useDisciplines()
  const topics = useTopics()
  return useMemo(() => {
    const d = new Map((disciplines.data ?? []).map((x) => [x.id, x.name]))
    const t = new Map((topics.data ?? []).map((x) => [x.id, x.name]))
    return {
      loading: disciplines.isLoading || topics.isLoading,
      discipline: (id: number) => d.get(id) ?? '—',
      topic: (id: number) => t.get(id) ?? '—',
    }
  }, [disciplines.data, disciplines.isLoading, topics.data, topics.isLoading])
}

/** Автор материала: «Вы» для своих; логин приходит от сервера (`author_login`) для всех ролей. */
export function useAuthorLabel() {
  const { user } = useAuth()
  return useCallback(
    (m: Material): string | null => {
      if (m.author_id === null) return 'автор удалён'
      if (user && m.author_id === user.id) return 'Вы'
      return m.author_login ?? null
    },
    [user],
  )
}

/** Скачивание как blob: заголовок Authorization нельзя передать обычной ссылкой. */
export function useDownload() {
  const [pendingId, setPendingId] = useState<number | null>(null)
  const download = useCallback(async (material: Material) => {
    setPendingId(material.id)
    try {
      const blob = await materialsApi.download(material.id)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = material.file_name
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 10_000)
      toast.success(`Скачивание: ${material.file_name}`)
    } catch (error) {
      notifyError(error, 'Не удалось скачать файл')
    } finally {
      setPendingId(null)
    }
  }, [])
  return { download, pendingId }
}

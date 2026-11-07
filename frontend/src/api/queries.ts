import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@/auth/AuthContext'
import { catalogApi, eventsApi, favoritesApi, materialsApi, usersApi } from './endpoints'
import type { Material, MaterialQuery } from './types'

const REFERENCE_STALE = 5 * 60_000

export const keys = {
  materials: (q: MaterialQuery) => ['materials', q] as const,
  material: (id: number) => ['material', id] as const,
  disciplines: ['disciplines'] as const,
  topics: ['topics'] as const,
  favorites: ['favorites'] as const,
  users: ['users'] as const,
  events: ['events'] as const,
}

// Справочники кэшируются: дисциплины и темы меняются редко.
export const useDisciplines = () =>
  useQuery({ queryKey: keys.disciplines, queryFn: catalogApi.disciplines, staleTime: REFERENCE_STALE })

export const useTopics = () =>
  useQuery({ queryKey: keys.topics, queryFn: () => catalogApi.topics(), staleTime: REFERENCE_STALE })

export const useMaterials = (query: MaterialQuery) =>
  useQuery({
    queryKey: keys.materials(query),
    queryFn: ({ signal }) => materialsApi.list(query, signal),
    placeholderData: keepPreviousData,
  })

export const useMaterial = (id: number) =>
  useQuery({ queryKey: keys.material(id), queryFn: () => materialsApi.get(id), enabled: Number.isFinite(id) })

export const useFavorites = () => useQuery({ queryKey: keys.favorites, queryFn: favoritesApi.list })

/** Список пользователей нужен только администратору: имена авторов и журнал. */
export function useUsers(enabled = true) {
  const { hasRole } = useAuth()
  return useQuery({
    queryKey: keys.users,
    queryFn: usersApi.list,
    enabled: enabled && hasRole('admin'),
    staleTime: 60_000,
  })
}

export const useEvents = () => useQuery({ queryKey: keys.events, queryFn: eventsApi.list })

/** Звёздочка «в избранное» с оптимистичным обновлением. 409 («уже добавлен») — не ошибка. */
export function useToggleFavorite() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ material, add }: { material: Material; add: boolean }) => {
      try {
        if (add) await favoritesApi.add(material.id)
        else await favoritesApi.remove(material.id)
      } catch (error) {
        const status = (error as { response?: { status?: number } }).response?.status
        if ((add && status === 409) || (!add && status === 404)) return
        throw error
      }
    },
    onMutate: async ({ material, add }) => {
      await qc.cancelQueries({ queryKey: keys.favorites })
      const previous = qc.getQueryData<Material[]>(keys.favorites)
      qc.setQueryData<Material[]>(keys.favorites, (old = []) =>
        add ? (old.some((m) => m.id === material.id) ? old : [material, ...old]) : old.filter((m) => m.id !== material.id),
      )
      return { previous }
    },
    onError: (_e, _v, context) => {
      if (context?.previous) qc.setQueryData(keys.favorites, context.previous)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: keys.favorites }),
  })
}

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { materialsApi } from './endpoints'
import type { Material } from './types'

/** Удаление материала: после успеха обновляются списки, каталог и избранное. */
export function useDeleteMaterial(onDone?: () => void) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (material: Material) => materialsApi.remove(material.id),
    onSuccess: (_d, material) => {
      qc.removeQueries({ queryKey: ['material', material.id] })
      void qc.invalidateQueries({ queryKey: ['materials'] })
      void qc.invalidateQueries({ queryKey: ['favorites'] })
      toast.success(`Материал «${material.title}» удалён`)
      onDone?.()
    },
  })
}

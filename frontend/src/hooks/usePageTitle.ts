import { useEffect } from 'react'

export function usePageTitle(title: string) {
  useEffect(() => {
    document.title = title ? `${title} · Учебные материалы` : 'Учебные материалы'
  }, [title])
}

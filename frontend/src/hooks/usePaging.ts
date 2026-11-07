import { useMemo, useState } from 'react'

export const PAGE_SIZE = 10

/** Пагинация на клиенте: API отдаёт списки целиком. Страница сбрасывается при смене `resetKey`. */
export function usePaging<T>(items: T[], resetKey: string, pageSize = PAGE_SIZE) {
  const [state, setState] = useState({ page: 1, key: resetKey })
  const page = state.key === resetKey ? state.page : 1
  const pageCount = Math.max(1, Math.ceil(items.length / pageSize))
  const current = Math.min(page, pageCount)
  const slice = useMemo(() => items.slice((current - 1) * pageSize, current * pageSize), [items, current, pageSize])
  return { page: current, setPage: (p: number) => setState({ page: p, key: resetKey }), pageCount, slice }
}

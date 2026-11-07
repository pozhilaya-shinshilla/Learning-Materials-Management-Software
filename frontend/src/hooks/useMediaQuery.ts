import { useEffect, useState } from 'react'

/** Подписка на media query. Safari 14 знает только addListener на MediaQueryList: ниже запасной путь. */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const mql = window.matchMedia(query)
    const update = () => setMatches(mql.matches)
    update()
    if (mql.addEventListener) mql.addEventListener('change', update)
    else mql.addListener(update)
    return () => {
      if (mql.removeEventListener) mql.removeEventListener('change', update)
      else mql.removeListener(update)
    }
  }, [query])
  return matches
}

/** Широкий экран (≥ lg в Tailwind): таблицы вместо карточек. Граница задана в em, как в Tailwind. */
export function useIsWide(): boolean {
  return useMediaQuery('(min-width: 64em)')
}

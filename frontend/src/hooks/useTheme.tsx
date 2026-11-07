import { createContext, useCallback, useContext, useLayoutEffect, useMemo, useState, type ReactNode } from 'react'

export type ThemeChoice = 'light' | 'dark' | 'system'
const KEY = 'lms-theme'

function readChoice(): ThemeChoice {
  try {
    const v = localStorage.getItem(KEY)
    if (v === 'light' || v === 'dark' || v === 'system') return v
  } catch {
    /* ignore */
  }
  return 'system'
}

function systemPrefersDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function isDark(choice: ThemeChoice): boolean {
  return choice === 'dark' || (choice === 'system' && systemPrefersDark())
}

interface ThemeState {
  choice: ThemeChoice
  /** Действующая тема после учёта «как в системе»; берите её для значка и подписи, а не класс из DOM. */
  dark: boolean
  setChoice: (c: ThemeChoice) => void
}
const ThemeContext = createContext<ThemeState | null>(null)

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [choice, setChoiceState] = useState<ThemeChoice>(readChoice)
  const [dark, setDark] = useState<boolean>(() => isDark(readChoice()))

  const setChoice = useCallback((c: ThemeChoice) => {
    setChoiceState(c)
    try {
      localStorage.setItem(KEY, c)
    } catch {
      /* ignore */
    }
  }, [])

  // Layout-эффект: класс на <html> и состояние меняются до отрисовки, поэтому значок и подпись
  // кнопки никогда не отстают от настоящей темы.
  useLayoutEffect(() => {
    const apply = () => {
      const next = isDark(choice)
      document.documentElement.classList.toggle('dark', next)
      setDark(next)
    }
    apply()
    if (choice !== 'system') return
    const mql = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = apply
    if (mql.addEventListener) mql.addEventListener('change', onChange)
    else mql.addListener(onChange)
    return () => {
      if (mql.removeEventListener) mql.removeEventListener('change', onChange)
      else mql.removeListener(onChange)
    }
  }, [choice])

  const value = useMemo(() => ({ choice, dark, setChoice }), [choice, dark, setChoice])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeState {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme вне ThemeProvider')
  return ctx
}

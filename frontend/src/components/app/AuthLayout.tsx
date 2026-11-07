import { BookOpen } from 'lucide-react'
import type { ReactNode } from 'react'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Moon, Sun } from 'lucide-react'
import { useTheme } from '@/hooks/useTheme'

export function AuthLayout({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  const { dark, setChoice } = useTheme()
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-4 py-8">
      <div className="absolute right-2 top-2">
        <Button
          variant="ghost"
          size="icon"
          aria-label={dark ? 'Включить светлую тему' : 'Включить тёмную тему'}
          onClick={() => setChoice(dark ? 'light' : 'dark')}
        >
          {dark ? <Sun aria-hidden="true" /> : <Moon aria-hidden="true" />}
        </Button>
      </div>
      <div className="flex items-center gap-3">
        {/* Место под логотип вуза: замените на <img src="/logo.svg" alt="">. */}
        <span aria-hidden="true" className="flex size-12 items-center justify-center rounded-md border border-dashed border-input text-primary">
          <BookOpen className="size-6" />
        </span>
        <div className="leading-tight">
          <p className="font-serif text-xl font-semibold">Учебные материалы</p>
        </div>
      </div>
      <Card className="w-full max-w-md p-5 sm:p-6">
        <main className="flex flex-col gap-5">
          <div>
            <h1 className="text-2xl">{title}</h1>
            {description ? <p className="mt-1 text-sm text-muted-foreground">{description}</p> : null}
          </div>
          {children}
        </main>
      </Card>
    </div>
  )
}

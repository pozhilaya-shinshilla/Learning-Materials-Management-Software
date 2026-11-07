import { BookOpen, ClipboardList, LibraryBig, LogOut, Menu, Monitor, Moon, Star, Sun, Users, Settings2 } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '@/auth/AuthContext'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuItem,
} from '@/components/ui/dropdown-menu'
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { useTheme, type ThemeChoice } from '@/hooks/useTheme'
import { ROLE_LABEL } from '@/lib/labels'
import { cn } from '@/lib/utils'

interface NavItem {
  to: string
  label: string
  icon: ReactNode
  end?: boolean
}

function useNavItems(): NavItem[] {
  const { hasRole } = useAuth()
  const items: NavItem[] = [
    { to: '/', label: 'Каталог', icon: <LibraryBig aria-hidden="true" />, end: true },
    { to: '/favorites', label: 'Избранное', icon: <Star aria-hidden="true" /> },
  ]
  if (hasRole('teacher', 'admin')) items.push({ to: '/manage', label: 'Управление', icon: <Settings2 aria-hidden="true" /> })
  if (hasRole('admin')) {
    items.push({ to: '/admin/users', label: 'Пользователи', icon: <Users aria-hidden="true" /> })
    items.push({ to: '/admin/events', label: 'Журнал', icon: <ClipboardList aria-hidden="true" /> })
  }
  return items
}

/** Место под логотип вуза: замените содержимое на <img src="/logo.svg" alt="">. */
function Brand() {
  return (
    <Link to="/" className="flex min-w-0 items-center gap-3 rounded-md py-1">
      <span
        aria-hidden="true"
        className="flex size-10 shrink-0 items-center justify-center rounded-md border border-dashed border-input text-primary"
      >
        <BookOpen className="size-5" />
      </span>
      <span className="min-w-0 leading-tight">
        <span className="block truncate font-serif text-lg font-semibold">Учебные материалы</span>
      </span>
    </Link>
  )
}

const THEME_ICON: Record<ThemeChoice, ReactNode> = {
  light: <Sun aria-hidden="true" />,
  dark: <Moon aria-hidden="true" />,
  system: <Monitor aria-hidden="true" />,
}

function ThemeMenu() {
  const { choice, setChoice } = useTheme()
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Тема оформления">
          {THEME_ICON[choice]}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuLabel>Тема оформления</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={choice} onValueChange={(v) => setChoice(v as ThemeChoice)}>
          <DropdownMenuRadioItem value="light">Светлая</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="dark">Тёмная</DropdownMenuRadioItem>
          <DropdownMenuRadioItem value="system">Как в системе</DropdownMenuRadioItem>
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

/** Переключатель темы для мобильного меню: три кнопки вместо выпадающего списка. */
function ThemeSegmented() {
  const { choice, setChoice } = useTheme()
  const options: [ThemeChoice, string][] = [
    ['light', 'Светлая'],
    ['dark', 'Тёмная'],
    ['system', 'Авто'],
  ]
  return (
    <div role="group" aria-label="Тема оформления" className="mt-auto flex flex-col gap-1.5">
      <span className="text-xs font-semibold text-muted-foreground">Тема оформления</span>
      <div className="grid grid-cols-3 gap-1">
        {options.map(([value, label]) => (
          <Button key={value} variant={choice === value ? 'default' : 'outline'} size="sm" aria-pressed={choice === value} onClick={() => setChoice(value)}>
            {label}
          </Button>
        ))}
      </div>
    </div>
  )
}

function UserMenu() {
  const { user, logout } = useAuth()
  if (!user) return null
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" className="max-w-48" aria-label={`Учётная запись: ${user.login}`}>
          <span className="truncate">{user.login}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuLabel>
          {user.login} · {ROLE_LABEL[user.role]}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => void logout()}>
          <LogOut aria-hidden="true" /> Выйти
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'inline-flex h-11 items-center gap-2 border-b-2 px-3 text-sm font-semibold transition-colors [&_svg]:size-4',
    isActive ? 'border-highlight text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground',
  )

export function AppShell() {
  const { user, logout } = useAuth()
  const items = useNavItems()
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-[60] focus:rounded-md focus:bg-primary focus:px-4 focus:py-3 focus:text-primary-foreground"
      >
        К содержимому
      </a>
      <header className="sticky top-0 z-40 border-b border-border bg-card">
        <div className="mx-auto flex w-full max-w-7xl items-center gap-2 px-4 py-2">
          <div className="min-w-0 flex-1 lg:flex-none">
            <Brand />
          </div>
          <nav aria-label="Основная навигация" className="ml-4 hidden flex-1 items-center gap-1 lg:flex">
            {items.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className={linkClass}>
                {item.icon}
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="flex shrink-0 items-center gap-1">
            <div className="hidden lg:block">
              <ThemeMenu />
            </div>
            <div className="hidden lg:block">
              <UserMenu />
            </div>
            <div className="lg:hidden">
              <Sheet open={menuOpen} onOpenChange={setMenuOpen} key={location.pathname}>
                <SheetTrigger asChild>
                  <Button variant="ghost" size="icon" aria-label="Открыть меню">
                    <Menu aria-hidden="true" />
                  </Button>
                </SheetTrigger>
                <SheetContent side="right">
                  <SheetTitle className="font-serif text-xl font-semibold">Меню</SheetTitle>
                  <SheetDescription className="text-sm text-muted-foreground">
                    {user?.login} · {user ? ROLE_LABEL[user.role] : ''}
                  </SheetDescription>
                  <nav aria-label="Навигация" className="flex flex-col gap-1">
                    {items.map((item) => (
                      <SheetClose asChild key={item.to}>
                        <NavLink
                          to={item.to}
                          end={item.end}
                          className={({ isActive }) =>
                            cn(
                              'flex h-11 items-center gap-3 rounded-md px-3 text-base font-semibold [&_svg]:size-5',
                              isActive ? 'bg-accent text-foreground' : 'text-muted-foreground hover:bg-accent hover:text-foreground',
                            )
                          }
                        >
                          {item.icon}
                          {item.label}
                        </NavLink>
                      </SheetClose>
                    ))}
                  </nav>
                  <ThemeSegmented />
                  <Button variant="outline" onClick={() => void logout()}>
                    <LogOut aria-hidden="true" /> Выйти
                  </Button>
                </SheetContent>
              </Sheet>
            </div>
          </div>
        </div>
      </header>
      <main id="content" tabIndex={-1} className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}

import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Ban, CheckCircle2, MoreVertical, Search, Trash2, UserPlus, Users } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { usersApi } from '@/api/endpoints'
import { useUsers } from '@/api/queries'
import type { Role, User } from '@/api/types'
import { useAuth } from '@/auth/AuthContext'
import { ConfirmDialog } from '@/components/app/ConfirmDialog'
import { FilterSelect } from '@/components/app/FilterSelect'
import { PasswordInput } from '@/components/app/PasswordInput'
import { CardsSkeleton, EmptyState, ErrorState, FormError, PageHeader, TableSkeleton } from '@/components/app/states'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Pagination } from '@/components/ui/pagination'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useIsWide } from '@/hooks/useMediaQuery'
import { usePageTitle } from '@/hooks/usePageTitle'
import { usePaging } from '@/hooks/usePaging'
import { applyServerErrors, notifyError } from '@/lib/errors-ui'
import { pluralize } from '@/lib/format'
import { ROLE_LABEL, ROLES, STATUS_LABEL } from '@/lib/labels'
import { userCreateSchema } from '@/lib/validation'

type Pending =
  | { kind: 'role'; user: User; role: Role }
  | { kind: 'block'; user: User }
  | { kind: 'delete'; user: User }

function RoleBadge({ role }: { role: Role }) {
  return <Badge variant={role === 'admin' ? 'highlight' : 'outline'}>{ROLE_LABEL[role]}</Badge>
}
function StatusBadge({ blocked }: { blocked: boolean }) {
  return <Badge variant={blocked ? 'destructive' : 'success'}>{blocked ? STATUS_LABEL.blocked : STATUS_LABEL.active}</Badge>
}

function CreateUserForm({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const form = useForm({
    resolver: zodResolver(userCreateSchema),
    defaultValues: { login: '', email: '', password: '', role: 'student' as Role },
  })

  async function onSubmit(values: { login: string; email: string; password: string; role: Role }) {
    setError(null)
    try {
      await usersApi.create({ ...values, login: values.login.trim(), email: values.email.trim() })
      await qc.invalidateQueries({ queryKey: ['users'] })
      toast.success(`Пользователь ${values.login.trim()} создан`)
      onClose()
    } catch (e) {
      const rest = applyServerErrors(form, e, ['login', 'email', 'password', 'role'])
      if (rest) setError(rest.message)
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
        <FormError message={error} />
        <FormField control={form.control} name="login" render={({ field }) => (
          <FormItem>
            <FormLabel required>Логин</FormLabel>
            <FormControl><Input autoComplete="off" autoCapitalize="none" spellCheck={false} {...field} /></FormControl>
            <FormDescription>3–32 символа: латинские буквы, цифры, «_» и «-».</FormDescription>
            <FormMessage />
          </FormItem>
        )} />
        <FormField control={form.control} name="email" render={({ field }) => (
          <FormItem>
            <FormLabel required>E-mail</FormLabel>
            <FormControl><Input type="email" autoComplete="off" inputMode="email" {...field} /></FormControl>
            <FormMessage />
          </FormItem>
        )} />
        <FormField control={form.control} name="password" render={({ field }) => (
          <FormItem>
            <FormLabel required>Пароль</FormLabel>
            <FormControl><PasswordInput autoComplete="new-password" {...field} /></FormControl>
            <FormDescription>Не короче 8 символов, с заглавной буквой, цифрой и специальным символом.</FormDescription>
            <FormMessage />
          </FormItem>
        )} />
        <FormField control={form.control} name="role" render={({ field }) => (
          <FormItem>
            <FormLabel required>Роль</FormLabel>
            <Select value={field.value} onValueChange={field.onChange}>
              <FormControl><SelectTrigger><SelectValue /></SelectTrigger></FormControl>
              <SelectContent>
                {ROLES.map((r) => <SelectItem key={r} value={r}>{ROLE_LABEL[r]}</SelectItem>)}
              </SelectContent>
            </Select>
            <FormMessage />
          </FormItem>
        )} />
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Отмена</Button>
          <Button type="submit" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? 'Создаём…' : 'Создать'}
          </Button>
        </DialogFooter>
      </form>
    </Form>
  )
}

function CreateUserDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Новый пользователь</DialogTitle>
          <DialogDescription>Регистрацию выполняет только администратор. Передайте пользователю логин и пароль.</DialogDescription>
        </DialogHeader>
        {/* Форма монтируется при открытии: каждый раз чистая. */}
        <CreateUserForm onClose={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  )
}

function UserActions({ user, isSelf, onPick }: { user: User; isSelf: boolean; onPick: (p: Pending | 'unblock') => void }) {
  // Сервер ответил бы 403, но сами действия над собой не предлагаем.
  if (isSelf) {
    return (
      <Button variant="ghost" size="icon" disabled aria-label="Действия недоступны: это ваша учётная запись" title="Нельзя изменить свою учётную запись">
        <MoreVertical aria-hidden="true" />
      </Button>
    )
  }
  const blocked = user.status === 'blocked'
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={`Действия с пользователем ${user.login}`}>
          <MoreVertical aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuLabel>Роль</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={user.role} onValueChange={(r) => r !== user.role && onPick({ kind: 'role', user, role: r as Role })}>
          {ROLES.map((r) => (
            <DropdownMenuRadioItem key={r} value={r}>{ROLE_LABEL[r]}</DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        {blocked ? (
          <DropdownMenuItem onSelect={() => onPick('unblock')}>
            <CheckCircle2 aria-hidden="true" /> Разблокировать
          </DropdownMenuItem>
        ) : (
          <DropdownMenuItem onSelect={() => onPick({ kind: 'block', user })}>
            <Ban aria-hidden="true" /> Заблокировать
          </DropdownMenuItem>
        )}
        <DropdownMenuItem className="text-destructive" onSelect={() => onPick({ kind: 'delete', user })}>
          <Trash2 aria-hidden="true" /> Удалить
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export default function UsersPage() {
  usePageTitle('Пользователи')
  const { user: me } = useAuth()
  const qc = useQueryClient()
  const wide = useIsWide()
  const query = useUsers()
  const [search, setSearch] = useState('')
  const [role, setRole] = useState('')
  const [status, setStatus] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [pending, setPending] = useState<Pending | null>(null)

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase()
    return (query.data ?? []).filter(
      (u) =>
        (!needle || u.login.toLowerCase().includes(needle) || u.email.toLowerCase().includes(needle)) &&
        (!role || u.role === role) &&
        (!status || u.status === status),
    )
  }, [query.data, search, role, status])
  const paging = usePaging(filtered, `${search}|${role}|${status}`)

  const act = useMutation({
    mutationFn: async (p: Pending | { kind: 'unblock'; user: User }) => {
      switch (p.kind) {
        case 'role':
          return usersApi.update(p.user.id, { role: p.role })
        case 'block':
          return usersApi.update(p.user.id, { status: 'blocked' })
        case 'unblock':
          return usersApi.update(p.user.id, { status: 'active' })
        case 'delete':
          return usersApi.remove(p.user.id)
      }
    },
    onSuccess: async (_d, p) => {
      await qc.invalidateQueries({ queryKey: ['users'] })
      const messages = {
        role: `Роль пользователя ${p.user.login} изменена`,
        block: `Пользователь ${p.user.login} заблокирован`,
        unblock: `Пользователь ${p.user.login} разблокирован`,
        delete: `Пользователь ${p.user.login} удалён`,
      }
      toast.success(messages[p.kind])
      setPending(null)
    },
    onError: (e) => {
      setPending(null)
      notifyError(e, 'Не удалось выполнить действие')
    },
  })

  function pick(u: User, p: Pending | 'unblock') {
    if (p === 'unblock') act.mutate({ kind: 'unblock', user: u })
    else setPending(p)
  }

  const confirmCopy = pending && {
    role: {
      title: 'Изменить роль?',
      text: `Пользователь ${pending.user.login} получит роль «${pending.kind === 'role' ? ROLE_LABEL[pending.role] : ''}». Его текущий сеанс будет завершён: ему придётся войти заново.`,
      label: 'Изменить',
    },
    block: {
      title: 'Заблокировать пользователя?',
      text: `${pending.user.login} не сможет войти в систему, пока вы не разблокируете запись.`,
      label: 'Заблокировать',
    },
    delete: {
      title: 'Удалить пользователя?',
      text: `Учётная запись ${pending.user.login} будет удалена. Его материалы останутся в каталоге без автора. Действие нельзя отменить.`,
      label: 'Удалить',
    },
  }[pending.kind]

  return (
    <div className="flex flex-col gap-5">
      <PageHeader
        title="Пользователи"
        description="Учётные записи студентов, преподавателей и администраторов."
        actions={
          <Button onClick={() => setCreateOpen(true)}>
            <UserPlus aria-hidden="true" /> Создать пользователя
          </Button>
        }
      />

      <section aria-label="Поиск и фильтры" className="grid gap-3 rounded-lg border border-border bg-card p-4 sm:grid-cols-3">
        <div className="flex min-w-0 flex-col gap-1.5">
          <Label htmlFor="u-search">Логин или e-mail</Label>
          <div className="relative">
            <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input id="u-search" type="search" className="pl-9" value={search} onChange={(e) => setSearch(e.target.value)} autoComplete="off" />
          </div>
        </div>
        <FilterSelect id="u-role" label="Роль" allLabel="Все роли" value={role} onChange={setRole} options={ROLES.map((r) => ({ value: r, label: ROLE_LABEL[r] }))} />
        <FilterSelect id="u-status" label="Статус" allLabel="Любой статус" value={status} onChange={setStatus} options={[{ value: 'active', label: STATUS_LABEL.active }, { value: 'blocked', label: STATUS_LABEL.blocked }]} />
      </section>

      <div aria-live="polite" className="text-sm text-muted-foreground">
        {query.isSuccess ? `Найдено: ${filtered.length} ${pluralize(filtered.length, ['пользователь', 'пользователя', 'пользователей'])}` : null}
      </div>

      {query.isLoading ? (
        wide ? <TableSkeleton /> : <CardsSkeleton count={4} />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : filtered.length === 0 ? (
        <EmptyState icon={<Users />} title="Никого не найдено">Измените запрос или фильтры.</EmptyState>
      ) : wide ? (
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-muted">
              <TableHead>Логин</TableHead>
              <TableHead>E-mail</TableHead>
              <TableHead>Роль</TableHead>
              <TableHead>Статус</TableHead>
              <TableHead className="text-right">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paging.slice.map((u) => {
              const isSelf = u.id === me?.id
              return (
                <TableRow key={u.id}>
                  <TableCell className="max-w-48 truncate font-semibold" title={u.login}>
                    {u.login} {isSelf ? <Badge variant="secondary">Вы</Badge> : null}
                  </TableCell>
                  <TableCell className="max-w-64 truncate text-muted-foreground" title={u.email}>{u.email}</TableCell>
                  <TableCell><RoleBadge role={u.role} /></TableCell>
                  <TableCell><StatusBadge blocked={u.status === 'blocked'} /></TableCell>
                  <TableCell className="text-right"><UserActions user={u} isSelf={isSelf} onPick={(p) => pick(u, p)} /></TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {paging.slice.map((u) => {
            const isSelf = u.id === me?.id
            return (
              <li key={u.id} className="min-w-0">
                <Card className="flex items-start justify-between gap-2 p-4">
                  <div className="min-w-0">
                    <p className="break-words font-semibold">{u.login} {isSelf ? <Badge variant="secondary">Вы</Badge> : null}</p>
                    <p className="break-all text-sm text-muted-foreground">{u.email}</p>
                    <div className="mt-2 flex flex-wrap gap-2"><RoleBadge role={u.role} /><StatusBadge blocked={u.status === 'blocked'} /></div>
                  </div>
                  <UserActions user={u} isSelf={isSelf} onPick={(p) => pick(u, p)} />
                </Card>
              </li>
            )
          })}
        </ul>
      )}
      <Pagination page={paging.page} pageCount={paging.pageCount} onChange={paging.setPage} />

      <CreateUserDialog open={createOpen} onOpenChange={setCreateOpen} />
      <ConfirmDialog
        open={pending !== null}
        onOpenChange={(o) => !o && setPending(null)}
        title={confirmCopy?.title ?? ''}
        description={confirmCopy?.text ?? ''}
        confirmLabel={confirmCopy?.label ?? ''}
        pending={act.isPending}
        onConfirm={() => pending && act.mutate(pending)}
      />
    </div>
  )
}

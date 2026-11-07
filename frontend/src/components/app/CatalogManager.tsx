import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { FolderPlus, Pencil, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { catalogApi } from '@/api/endpoints'
import { useDisciplines, useTopics } from '@/api/queries'
import type { Discipline, Topic } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import { applyServerErrors, notifyError } from '@/lib/errors-ui'
import { MAX_NAME } from '@/lib/labels'
import { nameSchema } from '@/lib/validation'
import { ConfirmDialog } from './ConfirmDialog'
import { CardsSkeleton, EmptyState, ErrorState, FormError } from './states'

type Dialogs =
  | { kind: 'add-discipline' }
  | { kind: 'rename-discipline'; discipline: Discipline }
  | { kind: 'add-topic'; discipline: Discipline }
  | { kind: 'rename-topic'; topic: Topic }

const TITLES: Record<Dialogs['kind'], string> = {
  'add-discipline': 'Новая дисциплина',
  'rename-discipline': 'Переименовать дисциплину',
  'add-topic': 'Новая тема',
  'rename-topic': 'Переименовать тему',
}

function initialName(state: Dialogs): string {
  if (state.kind === 'rename-discipline') return state.discipline.name
  if (state.kind === 'rename-topic') return state.topic.name
  return ''
}

function NameForm({ state, onClose }: { state: Dialogs; onClose: () => void }) {
  const qc = useQueryClient()
  const [error, setError] = useState<string | null>(null)
  const form = useForm({ resolver: zodResolver(nameSchema), defaultValues: { name: initialName(state) } })

  const save = useMutation({
    mutationFn: (name: string) => {
      switch (state.kind) {
        case 'add-discipline':
          return catalogApi.createDiscipline(name)
        case 'rename-discipline':
          return catalogApi.renameDiscipline(state.discipline.id, name)
        case 'add-topic':
          return catalogApi.createTopic(name, state.discipline.id)
        case 'rename-topic':
          return catalogApi.renameTopic(state.topic.id, name)
      }
    },
  })

  async function onSubmit({ name }: { name: string }) {
    setError(null)
    try {
      await save.mutateAsync(name)
      await Promise.all([qc.invalidateQueries({ queryKey: ['disciplines'] }), qc.invalidateQueries({ queryKey: ['topics'] })])
      toast.success('Сохранено')
      onClose()
    } catch (e) {
      const rest = applyServerErrors(form, e, ['name'])
      if (rest) setError(rest.message)
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
        <FormError message={error} />
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Название</FormLabel>
              <FormControl>
                <Input maxLength={MAX_NAME + 20} autoComplete="off" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Отмена
          </Button>
          <Button type="submit" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? 'Сохраняем…' : 'Сохранить'}
          </Button>
        </DialogFooter>
      </form>
    </Form>
  )
}

function NameDialog({ state, onClose }: { state: Dialogs | null; onClose: () => void }) {
  return (
    <Dialog open={state !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        {state ? (
          <>
            <DialogHeader>
              <DialogTitle>{TITLES[state.kind]}</DialogTitle>
              <DialogDescription>
                {state.kind === 'add-topic' ? `Дисциплина: ${state.discipline.name}. ` : ''}Название должно быть уникальным.
              </DialogDescription>
            </DialogHeader>
            <NameForm state={state} onClose={onClose} />
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}

/** Управление справочниками: дисциплины и темы (создание, переименование, удаление пустых). */
export function CatalogManager() {
  const disciplines = useDisciplines()
  const topics = useTopics()
  const [dialog, setDialog] = useState<Dialogs | null>(null)
  const [toDelete, setToDelete] = useState<{ kind: 'discipline'; item: Discipline } | { kind: 'topic'; item: Topic } | null>(null)
  const qc = useQueryClient()
  const remove = useMutation({
    mutationFn: (target: NonNullable<typeof toDelete>) =>
      target.kind === 'discipline' ? catalogApi.deleteDiscipline(target.item.id) : catalogApi.deleteTopic(target.item.id),
    onSuccess: async () => {
      await Promise.all([qc.invalidateQueries({ queryKey: ['disciplines'] }), qc.invalidateQueries({ queryKey: ['topics'] })])
      toast.success('Удалено')
      setToDelete(null)
    },
    // 409: в дисциплине есть темы или к теме привязаны материалы — показываем текст сервера.
    onError: (error) => {
      setToDelete(null)
      notifyError(error, 'Не удалось удалить')
    },
  })

  if (disciplines.isLoading || topics.isLoading) return <CardsSkeleton count={2} />
  if (disciplines.isError || topics.isError) {
    return <ErrorState error={disciplines.error ?? topics.error} onRetry={() => { void disciplines.refetch(); void topics.refetch() }} />
  }
  const list = disciplines.data ?? []

  return (
    <div className="flex flex-col gap-4">
      <div>
        <Button onClick={() => setDialog({ kind: 'add-discipline' })}>
          <Plus aria-hidden="true" /> Добавить дисциплину
        </Button>
      </div>
      {list.length === 0 ? (
        <EmptyState icon={<FolderPlus />} title="Дисциплин пока нет">
          Создайте первую дисциплину, затем добавьте в неё темы.
        </EmptyState>
      ) : (
        <ul className="grid gap-3 lg:grid-cols-2">
          {list.map((d) => {
            const own = (topics.data ?? []).filter((t) => t.discipline_id === d.id)
            return (
              <li key={d.id}>
                <Card className="flex h-full flex-col gap-3 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="min-w-0 break-words text-lg">{d.name}</h3>
                    <Button variant="ghost" size="icon" aria-label={`Переименовать дисциплину «${d.name}»`} onClick={() => setDialog({ kind: 'rename-discipline', discipline: d })}>
                      <Pencil aria-hidden="true" />
                    </Button>
                    <Button variant="ghost" size="icon" aria-label={`Удалить дисциплину «${d.name}»`} onClick={() => setToDelete({ kind: 'discipline', item: d })}>
                      <Trash2 aria-hidden="true" />
                    </Button>
                  </div>
                  {own.length === 0 ? (
                    <p className="text-sm text-muted-foreground">Тем пока нет.</p>
                  ) : (
                    <ul className="flex flex-col divide-y divide-border">
                      {own.map((t) => (
                        <li key={t.id} className="flex items-center justify-between gap-2">
                          <span className="min-w-0 break-words py-2 text-sm">{t.name}</span>
                          <Button variant="ghost" size="icon" aria-label={`Переименовать тему «${t.name}»`} onClick={() => setDialog({ kind: 'rename-topic', topic: t })}>
                            <Pencil aria-hidden="true" />
                          </Button>
                          <Button variant="ghost" size="icon" aria-label={`Удалить тему «${t.name}»`} onClick={() => setToDelete({ kind: 'topic', item: t })}>
                            <Trash2 aria-hidden="true" />
                          </Button>
                        </li>
                      ))}
                    </ul>
                  )}
                  <Button variant="outline" className="mt-auto self-start" onClick={() => setDialog({ kind: 'add-topic', discipline: d })}>
                    <Plus aria-hidden="true" /> Добавить тему
                  </Button>
                </Card>
              </li>
            )
          })}
        </ul>
      )}
      <NameDialog state={dialog} onClose={() => setDialog(null)} />
      <ConfirmDialog
        open={toDelete !== null}
        onOpenChange={(open) => !open && !remove.isPending && setToDelete(null)}
        title={toDelete?.kind === 'discipline' ? 'Удалить дисциплину?' : 'Удалить тему?'}
        description={
          toDelete
            ? toDelete.kind === 'discipline'
              ? `Дисциплина «${toDelete.item.name}» будет удалена. Это возможно, только если в ней нет тем.`
              : `Тема «${toDelete.item.name}» будет удалена. Это возможно, только если к ней не привязаны материалы.`
            : ''
        }
        confirmLabel="Удалить"
        pending={remove.isPending}
        onConfirm={() => toDelete && remove.mutate(toDelete)}
      />
    </div>
  )
}

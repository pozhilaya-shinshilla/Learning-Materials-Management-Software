import { zodResolver } from '@hookform/resolvers/zod'
import { useQueryClient } from '@tanstack/react-query'
import { Upload } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useForm, useWatch } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { materialsApi } from '@/api/endpoints'
import { toApiError } from '@/api/errors'
import { useDisciplines, useTopics } from '@/api/queries'
import type { Material, MaterialUpdate } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form'
import { Input, Textarea } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { formatFileSize } from '@/lib/format'
import { applyServerErrors } from '@/lib/errors-ui'
import { MAX_DESCRIPTION, MAX_TITLE } from '@/lib/labels'
import { ALLOWED_EXTENSIONS, materialSchema, validateFile } from '@/lib/validation'
import { FormError } from './states'

type Values = { title: string; description: string; discipline_id: string; topic_id: string }

/** Форма материала: создание (с файлом и индикатором загрузки) и правка метаданных. */
export function MaterialForm({ material }: { material?: Material }) {
  const editing = !!material
  const navigate = useNavigate()
  const qc = useQueryClient()
  const disciplines = useDisciplines()
  const topics = useTopics()
  const [file, setFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [progress, setProgress] = useState<number | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  const form = useForm<Values>({
    resolver: zodResolver(materialSchema),
    defaultValues: {
      title: material?.title ?? '',
      description: material?.description ?? '',
      discipline_id: material ? String(material.discipline_id) : '',
      topic_id: material ? String(material.topic_id) : '',
    },
  })
  const disciplineId = useWatch({ control: form.control, name: 'discipline_id' })
  const topicOptions = useMemo(
    () => (topics.data ?? []).filter((t) => String(t.discipline_id) === disciplineId),
    [topics.data, disciplineId],
  )
  const description = useWatch({ control: form.control, name: 'description' })
  const uploading = progress !== null

  function onPickFile(next: File | null) {
    setFile(next)
    setFileError(next ? validateFile(next) : null)
  }

  async function onSubmit(values: Values) {
    setFormError(null)
    if (!editing) {
      const problem = validateFile(file)
      if (problem) {
        setFileError(problem)
        document.getElementById('material-file')?.focus()
        return
      }
    }
    try {
      if (material) {
        const changes: MaterialUpdate = {}
        if (values.title !== material.title) changes.title = values.title
        if (values.description !== material.description) changes.description = values.description
        if (Number(values.discipline_id) !== material.discipline_id) changes.discipline_id = Number(values.discipline_id)
        if (Number(values.topic_id) !== material.topic_id) changes.topic_id = Number(values.topic_id)
        if (Object.keys(changes).length === 0) {
          toast.info('Изменений нет')
          return
        }
        await materialsApi.update(material.id, changes)
        await Promise.all([
          qc.invalidateQueries({ queryKey: ['materials'] }),
          qc.invalidateQueries({ queryKey: ['material', material.id] }),
          qc.invalidateQueries({ queryKey: ['favorites'] }),
        ])
        toast.success('Изменения сохранены')
        navigate(`/materials/${material.id}`)
      } else {
        setProgress(0)
        const created = await materialsApi.create(
          {
            title: values.title,
            description: values.description,
            discipline_id: Number(values.discipline_id),
            topic_id: Number(values.topic_id),
            file: file!,
          },
          setProgress,
        )
        await qc.invalidateQueries({ queryKey: ['materials'] })
        toast.success(`Материал «${created.title}» опубликован`)
        navigate('/manage')
      }
    } catch (e) {
      const err = toApiError(e)
      // Решающим считаем ответ сервера: 413 и 415 относятся к полю файла.
      if (err.status === 413 || err.status === 415 || err.code === 'UnsupportedFileTypeError' || err.code === 'FileTooLargeError') {
        setFileError(err.message)
        return
      }
      const rest = applyServerErrors(form, e, ['title', 'description', 'discipline_id', 'topic_id'])
      if (rest) setFormError(rest.message)
    } finally {
      setProgress(null)
    }
  }

  if (disciplines.isSuccess && (disciplines.data?.length ?? 0) === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border p-6 text-center">
        <p className="mb-3">Чтобы добавить материал, сначала создайте дисциплину и тему.</p>
        <Button asChild>
          <Link to="/manage?tab=catalog">Перейти к справочникам</Link>
        </Button>
      </div>
    )
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} noValidate className="flex max-w-2xl flex-col gap-5">
        <FormError message={formError} />
        <FormField
          control={form.control}
          name="title"
          render={({ field }) => (
            <FormItem>
              <FormLabel required>Название</FormLabel>
              <FormControl>
                <Input maxLength={MAX_TITLE + 50} disabled={uploading} {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <FormField
          control={form.control}
          name="description"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Описание</FormLabel>
              <FormControl>
                <Textarea rows={5} disabled={uploading} {...field} />
              </FormControl>
              <FormDescription>
                {description.length} из {MAX_DESCRIPTION} символов
              </FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />
        <div className="grid gap-5 sm:grid-cols-2">
          <FormField
            control={form.control}
            name="discipline_id"
            render={({ field }) => (
              <FormItem>
                <FormLabel required>Дисциплина</FormLabel>
                <Select
                  value={field.value}
                  disabled={uploading}
                  onValueChange={(v) => {
                    field.onChange(v)
                    form.setValue('topic_id', '', { shouldValidate: form.formState.isSubmitted })
                  }}
                >
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder="Выберите дисциплину" />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {(disciplines.data ?? []).map((d) => (
                      <SelectItem key={d.id} value={String(d.id)}>
                        {d.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="topic_id"
            render={({ field }) => (
              <FormItem>
                <FormLabel required>Тема</FormLabel>
                <Select value={field.value} onValueChange={field.onChange} disabled={!disciplineId || uploading}>
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue placeholder={disciplineId ? 'Выберите тему' : 'Сначала выберите дисциплину'} />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {topicOptions.map((t) => (
                      <SelectItem key={t.id} value={String(t.id)}>
                        {t.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {disciplineId && topicOptions.length === 0 && topics.isSuccess ? (
                  <FormDescription>
                    В этой дисциплине нет тем. <Link className="text-primary underline" to="/manage?tab=catalog">Добавьте тему</Link>.
                  </FormDescription>
                ) : null}
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        {editing ? (
          <p className="text-sm text-muted-foreground">
            Файл: <span className="break-all font-semibold text-foreground">{material.file_name}</span> ({formatFileSize(material.file_size_bytes)}). Заменить файл нельзя: загрузите новый материал.
          </p>
        ) : (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="material-file">
              Файл<span aria-hidden="true" className="ml-0.5 text-destructive">*</span>
            </Label>
            <Input
              id="material-file"
              type="file"
              accept={ALLOWED_EXTENSIONS.map((e) => `.${e}`).join(',')}
              disabled={uploading}
              aria-invalid={!!fileError}
              aria-describedby="material-file-hint material-file-error"
              className="h-auto py-2 file:mr-3 file:rounded-md file:border-0 file:bg-secondary file:px-3 file:py-2 file:text-sm file:font-semibold"
              onChange={(e) => onPickFile(e.target.files?.[0] ?? null)}
            />
            <p id="material-file-hint" className="text-sm text-muted-foreground">
              PDF, DOCX, PPTX, XLSX, JPG или PNG, до 100 МБ.
              {file ? ` Выбран: ${file.name} (${formatFileSize(file.size)}).` : ''}
            </p>
            {fileError ? (
              <p id="material-file-error" role="alert" className="text-sm font-medium text-destructive">
                {fileError}
              </p>
            ) : null}
          </div>
        )}

        {uploading ? (
          <div className="flex flex-col gap-1.5" aria-live="polite">
            <div className="flex justify-between text-sm">
              <span>{progress === 100 ? 'Файл передан, сервер его проверяет…' : 'Загрузка файла…'}</span>
              <span>{progress}%</span>
            </div>
            <div
              role="progressbar"
              aria-label="Загрузка файла"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progress}
              className="h-2 overflow-hidden rounded-full bg-muted"
            >
              <div className="h-full bg-primary transition-[width] duration-150" style={{ width: `${progress}%` }} />
            </div>
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <Button type="submit" disabled={form.formState.isSubmitting || (!editing && !!fileError)}>
            <Upload aria-hidden="true" />
            {editing ? 'Сохранить' : uploading ? 'Загрузка…' : 'Опубликовать'}
          </Button>
          <Button variant="outline" disabled={uploading} onClick={() => navigate(editing ? `/materials/${material.id}` : '/manage')}>
            Отмена
          </Button>
        </div>
      </form>
    </Form>
  )
}

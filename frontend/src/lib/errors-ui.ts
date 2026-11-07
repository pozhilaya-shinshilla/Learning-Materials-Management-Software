import type { FieldValues, Path, UseFormReturn } from 'react-hook-form'
import { toast } from 'sonner'
import { fieldForCode, toApiError, type ApiError } from '@/api/errors'

/** Уведомление об ошибке. 401 не показываем: сессия уже сброшена, экран входа скажет «Войдите снова». */
export function notifyError(error: unknown, title?: string): ApiError {
  const e = toApiError(error)
  if (e.status === 401 && !title) return e
  if (title) toast.error(title, { description: e.message })
  else toast.error(e.message)
  return e
}

/**
 * Привязывает серверные ошибки к полям формы (по loc для 422 FastAPI и по коду бизнес-правила).
 * Возвращает ошибку, если её не удалось привязать к полю: её нужно показать над формой.
 */
export function applyServerErrors<T extends FieldValues>(
  form: UseFormReturn<T>,
  error: unknown,
  fields: string[],
): ApiError | null {
  const e = toApiError(error)
  let applied = false
  for (const [field, message] of Object.entries(e.fields)) {
    if (fields.includes(field)) {
      form.setError(field as Path<T>, { type: 'server', message })
      applied = true
    }
  }
  const byCode = fieldForCode(e.code)
  if (byCode && fields.includes(byCode)) {
    form.setError(byCode as Path<T>, { type: 'server', message: e.message })
    applied = true
  }
  return applied ? null : e
}

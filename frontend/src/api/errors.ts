import axios from 'axios'

export interface ApiError {
  /** HTTP-статус; 0 — ответа не было (сеть, таймаут). */
  status: number
  /** Текст для пользователя. */
  message: string
  /** Имя класса ошибки бизнес-правила на сервере (DuplicateLoginError…). */
  code?: string
  /** Ошибки по полям: имя поля -> текст. */
  fields: Record<string, string>
  network: boolean
}

interface FastApiIssue {
  loc?: (string | number)[]
  msg?: string
}

/** Ошибка поля в ответе 422 нашего сервера: {field, message}. */
interface ServerIssue {
  field?: string
  message?: string
}

/**
 * Единое место разбора ошибок сервера. Два вида тела:
 *  — {detail: "строка", code}: бизнес-правила (401/403/404/409/413/415/422);
 *  — {detail: "строка", code: "RequestValidationError", errors: [{field, message}]}: проверка данных (422),
 *    текст привязывается к полю по `field`;
 *  — {detail: [{loc, msg}]}: стандартная 422 FastAPI (на случай прокси или старой версии сервера).
 */
export function toApiError(error: unknown): ApiError {
  if (!axios.isAxiosError(error)) {
    return { status: 0, message: 'Что-то пошло не так. Попробуйте ещё раз.', fields: {}, network: false }
  }
  const response = error.response
  if (!response) {
    return {
      status: 0,
      message: 'Нет связи с сервером. Проверьте подключение и повторите.',
      fields: {},
      network: true,
    }
  }
  const data: unknown = response.data
  const detail = (data as { detail?: unknown } | null)?.detail
  const code = (data as { code?: string } | null)?.code
  const errors = (data as { errors?: unknown } | null)?.errors
  if (typeof detail === 'string' && Array.isArray(errors)) {
    const fields: Record<string, string> = {}
    for (const issue of errors as ServerIssue[]) {
      const name = issue.field?.split('.').pop()
      if (name && !(name in fields)) fields[name] = issue.message ?? 'Некорректное значение'
    }
    return { status: response.status, message: detail, code, fields, network: false }
  }
  if (typeof detail === 'string') {
    return { status: response.status, message: detail, code, fields: {}, network: false }
  }
  if (Array.isArray(detail)) {
    const fields: Record<string, string> = {}
    const lines: string[] = []
    for (const issue of detail as FastApiIssue[]) {
      const field = [...(issue.loc ?? [])].reverse().find((p) => typeof p === 'string' && !['body', 'query', 'path'].includes(p))
      const text = issue.msg ?? 'Некорректное значение'
      if (typeof field === 'string' && !(field in fields)) fields[field] = text
      lines.push(field ? `${field}: ${text}` : text)
    }
    return { status: response.status, message: lines.join('; ') || 'Данные не прошли проверку.', fields, network: false }
  }
  const fallback: Record<number, string> = {
    401: 'Войдите снова.',
    403: 'Недостаточно прав.',
    404: 'Не найдено.',
    413: 'Файл слишком большой.',
    500: 'Ошибка сервера. Попробуйте позже.',
  }
  return {
    status: response.status,
    message: fallback[response.status] ?? `Ошибка запроса (${response.status}).`,
    fields: {},
    network: false,
  }
}

/** Поле формы, к которому относится ошибка бизнес-правила по её коду. */
const CODE_TO_FIELD: Record<string, string> = {
  DuplicateLoginError: 'login',
  InvalidLoginError: 'login',
  LoginRequiredError: 'login',
  DuplicateEmailError: 'email',
  InvalidEmailError: 'email',
  PasswordTooShortError: 'password',
  PasswordTooWeakError: 'password',
  PasswordRequiredError: 'password',
  DuplicateDisciplineError: 'name',
  DuplicateTopicError: 'name',
  EmptyFieldError: 'name',
  NameUnchangedError: 'name',
  FieldTooLongError: 'name',
  InvalidResetTokenError: 'token',
  UnsupportedFileTypeError: 'file',
  FileTooLargeError: 'file',
  TopicDisciplineMismatchError: 'topic_id',
  TopicDoesNotExistError: 'topic_id',
  DisciplineDoesNotExistError: 'discipline_id',
}

export function fieldForCode(code?: string): string | undefined {
  return code ? CODE_TO_FIELD[code] : undefined
}

import { z } from 'zod'
import { MAX_DESCRIPTION, MAX_FILE_BYTES, MAX_NAME, MAX_TITLE } from './labels'

// Правила повторяют src/domain/validation.py, чтобы ошибки были видны до отправки.
export const loginField = z
  .string()
  .trim()
  .min(1, 'Введите логин')
  .regex(/^[A-Za-z0-9_-]{3,32}$/, 'Логин: 3–32 символа, латинские буквы, цифры, «_» или «-»')

export const emailField = z
  .string()
  .trim()
  .min(1, 'Введите e-mail')
  .max(255, 'Не длиннее 255 символов')
  .regex(/^[^@\s]+@[^@\s]+\.[^@\s]+$/, 'Некорректный e-mail, пример: name@example.org')

export const passwordField = z
  .string()
  .min(8, 'Не короче 8 символов')
  .max(128, 'Не длиннее 128 символов')
  .refine((v) => /\p{Lu}/u.test(v), 'Добавьте заглавную букву')
  .refine((v) => /\p{Nd}/u.test(v), 'Добавьте цифру')
  .refine((v) => /[^\p{L}\p{N}\s]/u.test(v), 'Добавьте специальный символ, например «!» или «#»')

export const loginSchema = z.object({
  login: z.string().trim().min(1, 'Введите логин'),
  password: z.string().min(1, 'Введите пароль'),
})

export const recoverySchema = z.object({ email: emailField })

export const resetSchema = z
  .object({
    token: z.string().trim().min(1, 'Введите код из письма'),
    new_password: passwordField,
    confirm: z.string().min(1, 'Повторите пароль'),
  })
  .refine((v) => v.new_password === v.confirm, { path: ['confirm'], message: 'Пароли не совпадают' })

export const userCreateSchema = z.object({
  login: loginField,
  email: emailField,
  password: passwordField,
  role: z.enum(['student', 'teacher', 'admin']),
})

export const nameSchema = z.object({
  name: z.string().trim().min(1, 'Введите название').max(MAX_NAME, `Не длиннее ${MAX_NAME} символов`),
})

const idField = (message: string) =>
  z.string().min(1, message).regex(/^\d+$/, message)

export const materialSchema = z.object({
  title: z.string().trim().min(1, 'Введите название').max(MAX_TITLE, `Не длиннее ${MAX_TITLE} символов`),
  description: z.string().trim().max(MAX_DESCRIPTION, `Не длиннее ${MAX_DESCRIPTION} символов`),
  discipline_id: idField('Выберите дисциплину'),
  topic_id: idField('Выберите тему'),
})

export const ALLOWED_EXTENSIONS = ['pdf', 'docx', 'pptx', 'xlsx', 'jpg', 'jpeg', 'png']

/** Проверка файла до отправки; решающим остаётся ответ сервера (413, 415). */
export function validateFile(file: File | null | undefined): string | null {
  if (!file) return 'Прикрепите файл'
  const ext = file.name.includes('.') ? (file.name.split('.').pop() ?? '').toLowerCase() : ''
  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    return `Формат не поддерживается. Допустимы: ${ALLOWED_EXTENSIONS.map((e) => e.toUpperCase()).join(', ')}`
  }
  if (file.size > MAX_FILE_BYTES) return 'Файл больше 100 МБ'
  if (file.size === 0) return 'Файл пустой'
  return null
}

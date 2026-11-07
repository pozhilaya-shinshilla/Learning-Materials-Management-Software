import type { AccountStatus, FileType, Role } from '@/api/types'

// Подписи совпадают с src/domain/enums.py и SORT_OPTIONS в src/domain/validation.py.
export const ROLE_LABEL: Record<Role, string> = {
  student: 'студент',
  teacher: 'преподаватель',
  admin: 'администратор',
}

export const STATUS_LABEL: Record<AccountStatus, string> = {
  active: 'активен',
  blocked: 'заблокирован',
}

export const ROLES: Role[] = ['student', 'teacher', 'admin']

export const FILE_TYPES: FileType[] = ['pdf', 'docx', 'pptx', 'xlsx', 'jpg', 'png']

export interface SortOption {
  value: string
  label: string
  sort_by: 'upload_date' | 'title'
  order: 'asc' | 'desc'
}

export const SORT_OPTIONS: SortOption[] = [
  { value: 'new', label: 'Сначала новые', sort_by: 'upload_date', order: 'desc' },
  { value: 'old', label: 'Сначала старые', sort_by: 'upload_date', order: 'asc' },
  { value: 'az', label: 'От А до Я', sort_by: 'title', order: 'asc' },
  { value: 'za', label: 'От Я до А', sort_by: 'title', order: 'desc' },
]

export const MAX_FILE_BYTES = 100 * 1024 * 1024
export const MAX_TITLE = 200
export const MAX_DESCRIPTION = 10000
export const MAX_NAME = 100

export type Role = 'student' | 'teacher' | 'admin'
export type AccountStatus = 'active' | 'blocked'
export type FileType = 'pdf' | 'docx' | 'pptx' | 'xlsx' | 'jpg' | 'png'

export interface User {
  id: number
  login: string
  email: string
  role: Role
  status: AccountStatus
}

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_at: string
  user: User
}

export interface Discipline {
  id: number
  name: string
}

export interface Topic {
  id: number
  name: string
  discipline_id: number
}

export interface Material {
  id: number
  title: string
  description: string
  discipline_id: number
  topic_id: number
  file_name: string
  file_type: FileType
  file_size_bytes: number
  author_id: number | null
  /** Логин автора; «автор удалён», если автора удалили. */
  author_login: string | null
  uploaded_at: string
}

export interface EventRecord {
  id: number
  user_id: number | null
  event_type: string
  description: string
  target: string
  occurred_at: string
}

export interface MessageResponse {
  detail: string
}

export interface MaterialQuery {
  q?: string
  discipline_id?: number
  topic_id?: number
  file_type?: FileType
  uploaded_from?: string
  uploaded_to?: string
  sort_by?: 'upload_date' | 'title'
  order?: 'asc' | 'desc'
  limit?: number
  offset?: number
}

/** Страница материалов и общее число подходящих (заголовок X-Total-Count). */
export interface MaterialPage {
  items: Material[]
  total: number
}

export interface MaterialUpdate {
  title?: string
  description?: string
  discipline_id?: number
  topic_id?: number
}

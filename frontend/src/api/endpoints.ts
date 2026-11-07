import { http } from './client'
import type {
  Discipline,
  EventRecord,
  Material,
  MaterialPage,
  MaterialQuery,
  MaterialUpdate,
  MessageResponse,
  Role,
  TokenResponse,
  Topic,
  User,
} from './types'

/** Пустые значения не отправляем: лишние параметры сервер не прощает (422). */
function clean<T extends object>(params: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''),
  ) as Partial<T>
}

export const authApi = {
  login: (login: string, password: string) =>
    http.post<TokenResponse>('/auth/login', { login, password }).then((r) => r.data),
  me: () => http.get<User>('/auth/me').then((r) => r.data),
  logout: () => http.post<MessageResponse>('/auth/logout').then((r) => r.data),
  recovery: (email: string) =>
    http.post<MessageResponse>('/auth/password/recovery', { email }).then((r) => r.data),
  reset: (token: string, new_password: string) =>
    http.post<MessageResponse>('/auth/password/reset', { token, new_password }).then((r) => r.data),
}

export const materialsApi = {
  list: (query: MaterialQuery, signal?: AbortSignal): Promise<MaterialPage> =>
    http.get<Material[]>('/materials', { params: clean(query), signal }).then((r) => {
      const header = Number(r.headers['x-total-count'])
      return { items: r.data, total: Number.isFinite(header) ? header : r.data.length }
    }),
  get: (id: number) => http.get<Material>(`/materials/${id}`).then((r) => r.data),
  create: (
    data: { title: string; description: string; discipline_id: number; topic_id: number; file: File },
    onProgress?: (percent: number) => void,
  ) => {
    const form = new FormData()
    form.append('title', data.title)
    form.append('description', data.description)
    form.append('discipline_id', String(data.discipline_id))
    form.append('topic_id', String(data.topic_id))
    form.append('file', data.file)
    return http
      .post<Material>('/materials', form, {
        timeout: 0,
        onUploadProgress: (e) => {
          if (e.total) onProgress?.(Math.round((e.loaded / e.total) * 100))
        },
      })
      .then((r) => r.data)
  },
  update: (id: number, changes: MaterialUpdate) =>
    http.patch<Material>(`/materials/${id}`, changes).then((r) => r.data),
  remove: (id: number) => http.delete(`/materials/${id}`).then(() => undefined),
  /** Скачивание идёт через blob: ссылке <a href> нельзя передать заголовок Authorization. */
  download: (id: number) =>
    http
      .get<Blob>(`/materials/${id}/download`, { responseType: 'blob', timeout: 0 })
      .then((r) => r.data)
      .catch(async (error: unknown) => {
        // Тело ошибки пришло как Blob: разбираем его, чтобы показать текст сервера.
        const data: unknown = (error as { response?: { data?: unknown } }).response?.data
        if (data instanceof Blob) {
          try {
            ;(error as { response: { data: unknown } }).response.data = JSON.parse(await data.text())
          } catch {
            /* оставляем как есть */
          }
        }
        throw error
      }),
}

export const catalogApi = {
  disciplines: () => http.get<Discipline[]>('/disciplines').then((r) => r.data),
  createDiscipline: (name: string) => http.post<Discipline>('/disciplines', { name }).then((r) => r.data),
  renameDiscipline: (id: number, name: string) =>
    http.patch<Discipline>(`/disciplines/${id}`, { name }).then((r) => r.data),
  deleteDiscipline: (id: number) => http.delete(`/disciplines/${id}`).then(() => undefined),
  deleteTopic: (id: number) => http.delete(`/topics/${id}`).then(() => undefined),
  topics: (disciplineId?: number) =>
    http.get<Topic[]>('/topics', { params: clean({ discipline_id: disciplineId }) }).then((r) => r.data),
  createTopic: (name: string, discipline_id: number) =>
    http.post<Topic>('/topics', { name, discipline_id }).then((r) => r.data),
  renameTopic: (id: number, name: string) => http.patch<Topic>(`/topics/${id}`, { name }).then((r) => r.data),
}

export const favoritesApi = {
  list: () => http.get<Material[]>('/favorites').then((r) => r.data),
  add: (materialId: number) => http.post(`/favorites/${materialId}`).then(() => undefined),
  remove: (materialId: number) => http.delete(`/favorites/${materialId}`).then(() => undefined),
}

export const usersApi = {
  list: () => http.get<User[]>('/users').then((r) => r.data),
  create: (data: { login: string; email: string; password: string; role: Role }) =>
    http.post<User>('/users', data).then((r) => r.data),
  update: (id: number, changes: { role?: Role; status?: 'active' | 'blocked' }) =>
    http.patch<User>(`/users/${id}`, changes).then((r) => r.data),
  remove: (id: number) => http.delete(`/users/${id}`).then(() => undefined),
}

export const eventsApi = {
  list: () => http.get<EventRecord[]>('/events').then((r) => r.data),
}

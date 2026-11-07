// Время показываем в поясе кафедры (ВолгГТУ), а не в поясе браузера.
const TIME_ZONE = 'Europe/Volgograd'

const dateTime = new Intl.DateTimeFormat('ru-RU', {
  timeZone: TIME_ZONE,
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})
const dateOnly = new Intl.DateTimeFormat('ru-RU', {
  timeZone: TIME_ZONE,
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
})

/** Строка без указания пояса считается UTC: сервер хранит время в UTC. */
export function parseServerDate(value: string): Date {
  const hasZone = /([zZ]|[+-]\d{2}:?\d{2})$/.test(value)
  return new Date(hasZone ? value : `${value}Z`)
}

export function formatDateTime(value: string): string {
  const d = parseServerDate(value)
  return Number.isNaN(d.getTime()) ? '—' : dateTime.format(d)
}

export function formatDate(value: string): string {
  const d = parseServerDate(value)
  return Number.isNaN(d.getTime()) ? '—' : dateOnly.format(d)
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`
  const units = ['КБ', 'МБ', 'ГБ']
  let value = bytes / 1024
  let i = 0
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024
    i += 1
  }
  const text = value >= 10 || Number.isInteger(value) ? Math.round(value).toString() : value.toFixed(1)
  return `${text.replace('.', ',')} ${units[i]}`
}

export function pluralize(n: number, forms: [string, string, string]): string {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return forms[0]
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return forms[1]
  return forms[2]
}

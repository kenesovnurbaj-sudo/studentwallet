const number = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 2 })

export const money = (value) => `${number.format(value)} ₸`

// Сегодняшняя дата в формате ГГГГ-ММ-ДД по местному времени
export const todayISO = () => new Date().toLocaleDateString('en-CA')

// Текущий месяц в формате ГГГГ-ММ (как ждёт backend)
export const monthISO = () => todayISO().slice(0, 7)

export const shortDate = (iso) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })

export const monthTitle = (iso) =>
  new Date(`${iso}-01T00:00:00`).toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })

// 1 день, 2 дня, 5 дней
export function daysWord(n) {
  const last = n % 10
  const lastTwo = n % 100
  if (lastTwo >= 11 && lastTwo <= 14) return 'дней'
  if (last === 1) return 'день'
  if (last >= 2 && last <= 4) return 'дня'
  return 'дней'
}

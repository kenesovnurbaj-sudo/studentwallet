const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })

export const money = (value) => `₸${number.format(value)}`

// Сегодняшняя дата в формате ГГГГ-ММ-ДД по местному времени
export const todayISO = () => new Date().toLocaleDateString('en-CA')

// Текущий месяц в формате ГГГГ-ММ (как ждёт backend)
export const monthISO = () => todayISO().slice(0, 7)

export const shortDate = (iso) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })

export const monthTitle = (iso) =>
  new Date(`${iso}-01T00:00:00`).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })

// 1 day, 2 days
export const daysWord = (n) => (n === 1 ? 'day' : 'days')

import { useMemo, useState } from 'react'
import { money, monthTitle } from './format.js'

const pad = (n) => String(n).padStart(2, '0')

// Куда уходят деньги в текущем месяце. Считается из записей, которые уже загружены.
// Один цвет: категории различаются подписями, а не цветом.
export default function Analytics({ expenses, categories, month }) {
  const [hover, setHover] = useState(null)

  const spend = useMemo(
    () => expenses.filter((e) => e.type === 'expense' && e.spent_at.startsWith(month)),
    [expenses, month],
  )

  const byCategory = useMemo(() => {
    const sums = new Map()
    for (const e of spend) sums.set(e.category_id, (sums.get(e.category_id) || 0) + e.amount)
    const names = Object.fromEntries(categories.map((c) => [c.id, c]))
    return [...sums.entries()]
      .map(([id, sum]) => ({ id, sum, cat: names[id] }))
      .sort((a, b) => b.sum - a.sum)
  }, [spend, categories])

  const [year, mon] = month.split('-').map(Number)
  const daysInMonth = new Date(year, mon, 0).getDate()

  const perDay = useMemo(() => {
    const days = Array(daysInMonth).fill(0)
    for (const e of spend) days[Number(e.spent_at.slice(8, 10)) - 1] += e.amount
    return days
  }, [spend, daysInMonth])

  const dayLabel = (i) =>
    new Date(`${month}-${pad(i + 1)}T00:00:00`).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })

  if (spend.length === 0) {
    return (
      <section className="block">
        <h2>Куда уходят деньги</h2>
        <p className="empty">Графики появятся, когда в этом месяце будут расходы.</p>
      </section>
    )
  }

  const total = spend.reduce((s, e) => s + e.amount, 0)
  const maxDay = Math.max(...perDay)
  const peak = perDay.indexOf(maxDay)
  const tipLeft = hover === null ? 0 : Math.min(Math.max(((hover + 0.5) / daysInMonth) * 100, 20), 80)
  const ticks = [1, 8, 15, 22, 29].filter((d) => d <= daysInMonth)

  return (
    <section className="block">
      <h2>Куда уходят деньги</h2>
      <p className="muted">
        Расходы за {monthTitle(month)}: {money(total)}
      </p>

      <h3>По категориям</h3>
      <ul className="bars">
        {byCategory.map(({ id, sum, cat }) => (
          <li key={id} className="bar-row">
            <span className="bar-name">
              <span aria-hidden="true">{cat ? cat.icon : '🧾'}</span> {cat ? cat.name : 'Без категории'}
            </span>
            <span className="bar-track">
              <span className="bar-fill" style={{ width: `${(sum / byCategory[0].sum) * 100}%` }} />
            </span>
            <span className="bar-value">
              {money(sum)} <small>{Math.round((sum / total) * 100)}%</small>
            </span>
          </li>
        ))}
      </ul>

      <h3>По дням</h3>
      <p className="muted">
        Больше всего потрачено {dayLabel(peak)}: {money(maxDay)}
      </p>
      <div className="daily" onMouseLeave={() => setHover(null)}>
        <div className="daily-plot">
          {perDay.map((value, i) => (
            <button
              key={i}
              type="button"
              className="day"
              aria-label={`${dayLabel(i)}: ${money(value)}`}
              onMouseEnter={() => setHover(i)}
              onFocus={() => setHover(i)}
              onBlur={() => setHover(null)}
            >
              <span
                className="day-bar"
                style={{ height: value ? `${Math.max((value / maxDay) * 100, 4)}%` : 0 }}
              />
            </button>
          ))}
          {hover !== null && (
            <div className="tip" style={{ left: `${tipLeft}%` }} role="status">
              {dayLabel(hover)}: {money(perDay[hover])}
            </div>
          )}
        </div>
        <div className="daily-axis" aria-hidden="true">
          {ticks.map((d) => (
            <span key={d} style={{ left: `${((d - 0.5) / daysInMonth) * 100}%` }}>
              {d}
            </span>
          ))}
        </div>
      </div>

      <details className="table-view">
        <summary>Показать цифрами</summary>
        <table>
          <caption className="sr-only">Расходы по категориям и по дням</caption>
          <thead>
            <tr>
              <th scope="col">Категория</th>
              <th scope="col">Сумма</th>
            </tr>
          </thead>
          <tbody>
            {byCategory.map(({ id, sum, cat }) => (
              <tr key={id}>
                <td>{cat ? cat.name : 'Без категории'}</td>
                <td>{money(sum)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <table>
          <thead>
            <tr>
              <th scope="col">День</th>
              <th scope="col">Сумма</th>
            </tr>
          </thead>
          <tbody>
            {perDay.map((value, i) =>
              value ? (
                <tr key={i}>
                  <td>{dayLabel(i)}</td>
                  <td>{money(value)}</td>
                </tr>
              ) : null,
            )}
          </tbody>
        </table>
      </details>
    </section>
  )
}

import { money, monthTitle } from './format.js'
import { categoryName } from './categories.js'

const COLORS = [
  '#2b44ff',
  '#00856a',
  '#bd5700',
  '#8645c7',
  '#c52d59',
  '#527085',
]

export default function SpendingChart({
  expenses,
  categories,
  month,
}) {
  const totals = new Map()

  for (const item of expenses) {
    if (
      item.type !== 'expense' ||
      !item.spent_at.startsWith(`${month}-`)
    ) {
      continue
    }

    const cents = Math.round(Number(item.amount) * 100)

    totals.set(
      item.category_id,
      (totals.get(item.category_id) || 0) + cents
    )
  }

  const rows = [...totals.entries()]
    .map(([id, cents]) => ({
      id,
      cents,
      name: categoryName(
        categories.find((category) => category.id === id)?.name
      ),
    }))
    .sort((a, b) => b.cents - a.cents)

  const total = rows.reduce((sum, row) => sum + row.cents, 0)

  let position = 0

  const segments = rows.map((row, index) => {
    const start = position
    position += (row.cents / total) * 100

    return `${COLORS[index % COLORS.length]} ${start}% ${position}%`
  })

  return (
    <section className="block">
      <h2>Spending by category</h2>
      <p className="chart-caption">{monthTitle(month)}</p>

      {total === 0 ? (
        <p className="empty">
          Add an expense to see your spending breakdown.
        </p>
      ) : (
        <div className="chart-layout">
          <div
            className="spending-pie"
            style={{
              background: `conic-gradient(${segments.join(', ')})`,
            }}
            role="img"
            aria-label={rows
              .map(
                (row) =>
                  `${row.name}: ${money(row.cents / 100)}, ${
                    ((row.cents / total) * 100).toFixed(1)
                  } percent`
              )
              .join('; ')}
          />

          <div className="chart-details">
            <p>
              Total spent: <strong>{money(total / 100)}</strong>
            </p>

            <ul className="chart-legend">
              {rows.map((row, index) => (
                <li key={row.id}>
                  <span
                    className="chart-dot"
                    style={{
                      background: COLORS[index % COLORS.length],
                    }}
                    aria-hidden="true"
                  />
                  <span>{row.name}</span>
                  <strong>{money(row.cents / 100)}</strong>
                  <span>
                    {((row.cents / total) * 100).toFixed(1)}%
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </section>
  )
}
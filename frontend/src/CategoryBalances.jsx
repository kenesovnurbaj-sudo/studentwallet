import { useEffect, useState } from 'react'
import { api } from './api.js'
import { money } from './format.js'

// Траты и остаток по каждой категории за месяц (история 6). refreshKey меняется, когда данные устарели.
export default function CategoryBalances({ month, refreshKey }) {
  const [rows, setRows] = useState(null)

  useEffect(() => {
    let cancelled = false
    api
      .categoryBalances(month)
      .then((d) => !cancelled && setRows(d))
      .catch(() => !cancelled && setRows(null))
    return () => {
      cancelled = true
    }
  }, [month, refreshKey])

  if (rows === null) return null

  return (
    <section className="block cat-balances" aria-label="Balance by category">
      <h2>By category</h2>
      {rows.length === 0 ? (
        <p className="empty">Nothing spent yet. Add an expense, or use “Split budget with AI” to set limits per category.</p>
      ) : (
        <ul className="rows">
          {rows.map((r) => {
            const fill = r.percent_used === null ? 0 : Math.min(r.percent_used, 100)
            return (
              <li key={r.category_id} className={`cat-row cat-${r.status}`}>
                <div className="cat-head">
                  <span>
                    {r.icon} {r.category}
                  </span>
                  <span className="cat-amount">
                    {r.limit === null ? `${money(r.spent)} spent` : `${money(r.spent)} of ${money(r.limit)}`}
                  </span>
                </div>
                {r.limit !== null && (
                  <>
                    <div
                      className="cat-bar"
                      role="progressbar"
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={Math.round(fill)}
                      aria-label={`${r.category} budget used`}
                    >
                      <div className="cat-fill" style={{ width: `${fill}%` }} />
                    </div>
                    <p className="cat-left">
                      {r.remaining >= 0 ? `${money(r.remaining)} left` : `${money(-r.remaining)} over the limit`}
                    </p>
                  </>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

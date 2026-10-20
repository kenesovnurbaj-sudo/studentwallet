import { useEffect, useState } from 'react'
import { api } from './api.js'
import { money } from './format.js'

// Прогноз расходов до конца месяца и предупреждения о слишком быстрых тратах (история 7).
// refreshKey меняется при каждой перезагрузке бюджета, тогда прогноз запрашивается заново.
export default function ForecastCard({ month, refreshKey }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    let cancelled = false
    api
      .forecast(month)
      .then((d) => !cancelled && setData(d))
      .catch(() => !cancelled && setData(null)) // нет бюджета или сервер недоступен: карточку просто не показываем
    return () => {
      cancelled = true
    }
  }, [month, refreshKey])

  if (!data) return null

  const pace = data.projected_total !== null
  const share = pace ? Math.min((data.projected_total / data.limit) * 100, 100) : 0

  return (
    <section className={`forecast forecast-${data.level}`} aria-label="Spending forecast">
      <h2>Forecast</h2>
      {data.alerts.map((a) => (
        <p key={a.code} className={`forecast-msg ${a.level}`} role={a.level === 'danger' || a.level === 'exceeded' ? 'alert' : undefined}>
          {a.message}
        </p>
      ))}
      {pace && (
        <>
          <div className="meter forecast-meter" role="img" aria-label={`Projected ${Math.round(share)}% of the budget`}>
            <div className="meter-fill" style={{ width: `${share}%` }} />
          </div>
          <p className="forecast-facts">
            Daily average {money(data.daily_average)} · Projected {money(data.projected_total)} of {money(data.limit)}
            {data.safe_daily_limit !== null && ` · Safe daily limit ${money(data.safe_daily_limit)}`}
          </p>
        </>
      )}
    </section>
  )
}

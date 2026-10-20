import { useEffect, useState } from 'react'
import { api } from './api.js'
import { money, monthTitle } from './format.js'

// Предложение ИИ: как разделить месячный бюджет по категориям. Суммы можно поправить перед применением.
export default function BudgetSplit({ month, onClose }) {
  const [data, setData] = useState(null)
  const [amounts, setAmounts] = useState({}) // category_id -> строка из поля ввода
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState('')

  useEffect(() => {
    api
      .budgetSplit(month)
      .then((d) => {
        setData(d)
        setAmounts(Object.fromEntries(d.items.map((i) => [i.category_id, String(i.amount)])))
      })
      .catch((err) => setError(err.message))
  }, [month])

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && !busy && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [busy, onClose])

  const allocated = data ? data.items.reduce((sum, i) => sum + (Number(amounts[i.category_id]) || 0), 0) : 0
  const diff = data ? data.total - allocated : 0

  async function apply() {
    const items = data.items
      .map((i) => ({ category_id: i.category_id, limit_amount: Number(amounts[i.category_id]) || 0 }))
      .filter((i) => i.limit_amount > 0)
    if (items.length === 0) {
      setError('Enter at least one amount greater than zero')
      return
    }
    setError('')
    setBusy(true)
    try {
      const { saved: n } = await api.saveBudgetSplit(month, items)
      setSaved(`Saved limits for ${n} categories.`)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}>
      <section className="modal" role="dialog" aria-modal="true" aria-labelledby="split-title">
        <header className="modal-head">
          <h2 id="split-title">Split your budget with AI</h2>
          <button type="button" className="modal-close" onClick={onClose} disabled={busy} aria-label="Close">
            ×
          </button>
        </header>

        {!data && !error && <p className="hint">WALL·E is thinking…</p>}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        {data && (
          <>
            <p className="hint">
              {monthTitle(month)}: {money(data.total)}. {data.tip}
              {data.source === 'rules' && ' (AI was unavailable, so this is a standard student split.)'}
            </p>

            <div className="import-scroll">
              <table className="import-table">
                <thead>
                  <tr>
                    <th>Category</th>
                    <th className="num">Share</th>
                    <th className="num">Amount, ₸</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((i) => {
                    const value = Number(amounts[i.category_id]) || 0
                    return (
                      <tr key={i.category_id}>
                        <td>
                          {i.icon} {i.category}
                        </td>
                        <td className="num">{data.total ? Math.round((value / data.total) * 100) : 0}%</td>
                        <td className="num">
                          <input
                            className="amount-input"
                            type="number"
                            min="0"
                            step="1"
                            inputMode="numeric"
                            value={amounts[i.category_id]}
                            onChange={(e) => setAmounts({ ...amounts, [i.category_id]: e.target.value })}
                            aria-label={`Amount for ${i.category}`}
                          />
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            <p className={diff === 0 ? 'ok-note' : 'hint'}>
              Allocated {money(allocated)} of {money(data.total)}
              {diff > 0 && ` (${money(diff)} unassigned)`}
              {diff < 0 && ` (${money(-diff)} over the budget)`}
            </p>
            {saved && <p className="ok-note">{saved}</p>}

            <div className="import-actions">
              <button className="primary" type="button" disabled={busy || Boolean(saved)} onClick={apply}>
                {busy ? 'Saving…' : 'Apply split'}
              </button>
              <button className="link" type="button" disabled={busy} onClick={onClose}>
                {saved ? 'Close' : 'Cancel'}
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  )
}

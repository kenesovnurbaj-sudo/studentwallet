import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import { money, shortDate } from './format.js'

const sum = (list) => list.reduce((total, d) => total + d.amount, 0)

// Группируем долги по человеку: у плательщика по должникам, у должника по плательщикам
function groupBy(list, side) {
  const groups = new Map()
  for (const item of list) {
    const person = item[side]
    if (!groups.has(person.id)) groups.set(person.id, { person, items: [] })
    groups.get(person.id).items.push(item)
  }
  return [...groups.values()]
}

export default function Debts({ categories, version, onChanged }) {
  const [owed, setOwed] = useState(null) // null = ещё грузится
  const [owe, setOwe] = useState(null)
  const [tab, setTab] = useState('owed')
  const [tabChosen, setTabChosen] = useState(false)
  const [categoryId, setCategoryId] = useState('')
  const [busyId, setBusyId] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      const [a, b] = await Promise.all([api.debtsOwedToMe(), api.debtsIOwe()])
      setOwed(a)
      setOwe(b)
    } catch (err) {
      setError(err.message)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load, version])

  useEffect(() => {
    if (!categoryId && categories.length) setCategoryId(String(categories[0].id))
  }, [categories, categoryId])

  // При первом открытии показываем ту вкладку, где что-то есть
  useEffect(() => {
    if (tabChosen || owed === null || owe === null) return
    const mustPay = owe.some((d) => d.status === 'pending')
    if (owed.length === 0 && mustPay) setTab('owe')
  }, [owed, owe, tabChosen])

  if (owed === null || owe === null) return null
  if (owed.length === 0 && owe.length === 0) return null // долгов нет, блок не нужен

  async function act(share, action, message) {
    if (message && !window.confirm(message)) return
    setError('')
    setBusyId(share.id)
    try {
      await action()
      await load()
      onChanged() // долг мог попасть в расходы друга, обновляем бюджет и историю
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  const owedTotal = sum(owed)
  const oweTotal = sum(owe.filter((d) => d.status === 'pending'))
  const toConfirm = owed.filter((d) => d.status === 'marked_paid').length

  const choose = (value) => {
    setTab(value)
    setTabChosen(true)
  }

  return (
    <section className="block debts">
      <div className="block-head">
        <h2>Debts</h2>
        <button type="button" className="link" onClick={load}>
          Refresh
        </button>
      </div>

      <div className="segmented" role="group" aria-label="Which debts to show">
        <button type="button" className={tab === 'owed' ? 'on' : ''} aria-pressed={tab === 'owed'} onClick={() => choose('owed')}>
          Owed to me · {money(owedTotal)}
        </button>
        <button type="button" className={tab === 'owe' ? 'on' : ''} aria-pressed={tab === 'owe'} onClick={() => choose('owe')}>
          I owe · {money(oweTotal)}
        </button>
      </div>

      {tab === 'owed' && toConfirm > 0 && (
        <p className="notice">
          {toConfirm === 1 ? 'One friend says they paid you back' : `${toConfirm} friends say they paid you back`}. Check the transfer and confirm.
        </p>
      )}

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {tab === 'owed' && (
        <>
          {owed.length === 0 && <p className="empty">Nobody owes you anything.</p>}
          {groupBy(owed, 'debtor').map(({ person, items }) => (
            <div className="debt-group" key={person.id}>
              <div className="debt-head">
                <span>
                  <b>{person.name}</b>
                  <small>{person.email}</small>
                </span>
                <b>{money(sum(items))}</b>
              </div>
              <ul className="rows">
                {items.map((d) => (
                  <li className="debt-item" key={d.id}>
                    <span className="row-main">
                      <span className="row-title">{d.note || 'Shared bill'}</span>
                      <span className="row-sub">
                        {shortDate(d.spent_at)}
                        {d.paid_total != null ? `, bill ${money(d.paid_total)}` : ''}
                      </span>
                    </span>
                    <span className="row-amount">{money(d.amount)}</span>
                    <span className="debt-actions">
                      {d.status === 'marked_paid' ? (
                        <>
                          <span className="badge wait">friend marked as paid</span>
                          <button
                            type="button"
                            className="secondary"
                            disabled={busyId === d.id}
                            onClick={() => act(d, () => api.confirmShare(d.id))}
                          >
                            Received
                          </button>
                          <button
                            type="button"
                            className="link"
                            disabled={busyId === d.id}
                            onClick={() =>
                              act(d, () => api.rejectShare(d.id), `${person.name} marked this as paid but the money has not arrived? The debt will become open again.`)
                            }
                          >
                            Not received
                          </button>
                        </>
                      ) : (
                        <>
                          <span className="badge">awaiting payment</span>
                          <button
                            type="button"
                            className="link"
                            disabled={busyId === d.id}
                            onClick={() =>
                              act(d, () => api.confirmShare(d.id), `Close the ${money(d.amount)} debt: did ${person.name} pay you back (for example, in cash)?`)
                            }
                          >
                            Paid outside the app
                          </button>
                        </>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </>
      )}

      {tab === 'owe' && (
        <>
          {owe.length === 0 && <p className="empty">You do not owe anyone.</p>}
          {owe.some((d) => d.status === 'pending') && (
            <label className="pay-category">
              When you pay back, record it as an expense in category
              <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.icon} {c.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          {groupBy(owe, 'payer').map(({ person, items }) => (
            <div className="debt-group" key={person.id}>
              <div className="debt-head">
                <span>
                  <b>{person.name}</b>
                  <small>{person.email}</small>
                </span>
                <b>{money(sum(items.filter((d) => d.status === 'pending')))}</b>
              </div>
              <ul className="rows">
                {items.map((d) => (
                  <li className="debt-item" key={d.id}>
                    <span className="row-main">
                      <span className="row-title">{d.note || 'Shared bill'}</span>
                      <span className="row-sub">
                        {shortDate(d.spent_at)}
                        {d.paid_total != null ? `, bill ${money(d.paid_total)}` : ''}
                      </span>
                    </span>
                    <span className="row-amount">{money(d.amount)}</span>
                    <span className="debt-actions">
                      {d.status === 'marked_paid' ? (
                        <span className="badge wait">waiting for {person.name} to confirm</span>
                      ) : (
                        <button
                          type="button"
                          className="primary small"
                          disabled={busyId === d.id || !categoryId}
                          onClick={() =>
                            act(d, () => api.markPaid(d.id, Number(categoryId)), `Did you transfer ${money(d.amount)} to ${person.name}? The amount will be added to your expenses.`)
                          }
                        >
                          I paid
                        </button>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </>
      )}
    </section>
  )
}

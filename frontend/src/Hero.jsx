import { useState } from 'react'
import { api } from './api.js'
import { daysWord, money, monthTitle } from './format.js'

// Главный блок: сколько можно потратить сегодня и как расходуется бюджет месяца.
// summary: undefined = грузится, null = бюджет не задан, объект = данные.
export default function Hero({ summary, month, onSaved }) {
  const [editing, setEditing] = useState(false)

  if (summary === undefined) {
    return (
      <section className="hero" aria-busy="true">
        <p className="hero-label">Loading budget…</p>
      </section>
    )
  }

  if (summary === null || editing) {
    return (
      <section className="hero">
        <p className="hero-label">{monthTitle(month)}</p>
        <h2 className="hero-title">
          {summary === null ? 'Set your monthly budget' : 'Change budget'}
        </h2>
        <p className="hero-text">
          {summary === null
            ? 'Then you will see here how much you can spend each day.'
            : 'The new limit replaces the current one.'}
        </p>
        <BudgetForm
          month={month}
          initial={summary ? summary.limit : ''}
          onSaved={() => {
            setEditing(false)
            onSaved()
          }}
          onCancel={summary ? () => setEditing(false) : null}
        />
      </section>
    )
  }

  const { limit, spent, remaining, percent_used: percent, days_left: daysLeft, daily_limit: daily } = summary
  const over = remaining < 0
  const exhausted = remaining <= 0
  const state = exhausted ? 'bad' : percent >= 80 ? 'warn' : 'ok'
  const fill = Math.min(percent, 100)

  return (
    <section className={`hero hero-${state}`}>
      <p className="hero-label">{exhausted ? 'Budget used up' : 'You can spend today'}</p>
      <p className="hero-number">{money(exhausted ? Math.abs(remaining) : daily)}</p>

      {exhausted ? (
        <p className="hero-text">
          {over ? 'This is over your monthly limit.' : 'Nothing left to spend this month.'}
        </p>
      ) : (
        <p className="hero-text">
          {money(remaining)} left of {money(limit)}. {daysLeft} {daysWord(daysLeft)} until the end of the month.
        </p>
      )}

      <div
        className="meter"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(fill)}
        aria-label="Share of budget spent"
      >
        <div className="meter-fill" style={{ width: `${fill}%` }} />
        <span className="meter-tick" style={{ left: '80%' }} aria-hidden="true" />
      </div>

      <div className="hero-foot">
        <span>
          Spent {money(spent)} ({percent}%)
        </span>
        <button className="link light" type="button" onClick={() => setEditing(true)}>
          Change limit
        </button>
      </div>

      {state === 'warn' && <p className="hero-alert">You have spent more than 80% of your budget. Time to slow down.</p>}
      {state === 'bad' && <p className="hero-alert">Monthly limit reached.</p>}
    </section>
  )
}

function BudgetForm({ month, initial, onSaved, onCancel }) {
  const [value, setValue] = useState(initial === '' ? '' : String(initial))
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError('')
    const amount = Number(value)
    if (!amount || amount <= 0) {
      setError('Enter an amount greater than zero')
      return
    }
    setBusy(true)
    try {
      await api.setBudget({ month, limit_amount: amount })
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="budget-form" onSubmit={submit}>
      <label>
        Monthly limit, ₸
        <input
          type="number"
          inputMode="decimal"
          min="1"
          step="any"
          required
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="For example, 60000"
        />
      </label>
      <div className="row">
        <button className="primary light" type="submit" disabled={busy}>
          {busy ? 'Saving…' : 'Save budget'}
        </button>
        {onCancel && (
          <button className="link light" type="button" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
      {error && (
        <p className="error on-dark" role="alert">
          {error}
        </p>
      )}
    </form>
  )
}

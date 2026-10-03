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
        <p className="hero-label">Загружаем бюджет…</p>
      </section>
    )
  }

  if (summary === null || editing) {
    return (
      <section className="hero">
        <p className="hero-label">{monthTitle(month)}</p>
        <h2 className="hero-title">
          {summary === null ? 'Задайте бюджет на месяц' : 'Изменить бюджет'}
        </h2>
        <p className="hero-text">
          {summary === null
            ? 'Тогда здесь появится сумма, которую можно тратить каждый день.'
            : 'Новый лимит заменит текущий.'}
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
      <p className="hero-label">{exhausted ? 'Бюджет исчерпан' : 'Можно потратить сегодня'}</p>
      <p className="hero-number">{money(exhausted ? Math.abs(remaining) : daily)}</p>

      {exhausted ? (
        <p className="hero-text">
          {over ? 'Это перерасход сверх месячного лимита.' : 'До конца месяца тратить больше нечего.'}
        </p>
      ) : (
        <p className="hero-text">
          Осталось {money(remaining)} из {money(limit)}. До конца месяца {daysLeft} {daysWord(daysLeft)}.
        </p>
      )}

      <div
        className="meter"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(fill)}
        aria-label="Потрачено от бюджета"
      >
        <div className="meter-fill" style={{ width: `${fill}%` }} />
        <span className="meter-tick" style={{ left: '80%' }} aria-hidden="true" />
      </div>

      <div className="hero-foot">
        <span>
          Потрачено {money(spent)} ({percent}%)
        </span>
        <button className="link light" type="button" onClick={() => setEditing(true)}>
          Изменить лимит
        </button>
      </div>

      {state === 'warn' && <p className="hero-alert">Вы потратили больше 80% бюджета. Пора притормозить.</p>}
      {state === 'bad' && <p className="hero-alert">Лимит месяца достигнут.</p>}
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
      setError('Введите сумму больше нуля')
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
        Лимит на месяц, ₸
        <input
          type="number"
          inputMode="decimal"
          min="1"
          step="any"
          required
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Например, 60000"
        />
      </label>
      <div className="row">
        <button className="primary light" type="submit" disabled={busy}>
          {busy ? 'Сохраняем…' : 'Сохранить бюджет'}
        </button>
        {onCancel && (
          <button className="link light" type="button" onClick={onCancel}>
            Отмена
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

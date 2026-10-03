import { useEffect, useState } from 'react'
import { api } from './api.js'
import { todayISO } from './format.js'

export default function ExpenseForm({ categories, onAdded }) {
  const [type, setType] = useState('expense')
  const [amount, setAmount] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [note, setNote] = useState('')
  const [date, setDate] = useState(todayISO())
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  // Когда категории загрузились, выбираем первую по умолчанию
  useEffect(() => {
    if (!categoryId && categories.length) setCategoryId(String(categories[0].id))
  }, [categories, categoryId])

  async function submit(e) {
    e.preventDefault()
    setError('')
    const value = Number(amount)
    if (!value || value <= 0) {
      setError('Введите сумму больше нуля')
      return
    }
    setBusy(true)
    try {
      await api.addExpense({
        amount: value,
        category_id: Number(categoryId),
        type,
        note: note.trim(),
        spent_at: date,
        source: 'web',
      })
      setAmount('')
      setNote('')
      onAdded()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="block">
      <h2>Новая запись</h2>
      <form className="expense-form" onSubmit={submit}>
        <div className="segmented" role="group" aria-label="Тип записи">
          <button
            type="button"
            className={type === 'expense' ? 'on' : ''}
            aria-pressed={type === 'expense'}
            onClick={() => setType('expense')}
          >
            Расход
          </button>
          <button
            type="button"
            className={type === 'income' ? 'on' : ''}
            aria-pressed={type === 'income'}
            onClick={() => setType('income')}
          >
            Доход
          </button>
        </div>

        <div className="grid-2">
          <label>
            Сумма, ₸
            <input
              type="number"
              inputMode="decimal"
              min="1"
              step="any"
              required
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="1500"
            />
          </label>
          <label>
            Категория
            <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)} required>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.icon} {c.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="grid-2">
          <label>
            Комментарий
            <input
              value={note}
              maxLength={255}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Например, обед"
            />
          </label>
          <label>
            Дата
            <input type="date" required value={date} onChange={(e) => setDate(e.target.value)} />
          </label>
        </div>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <button className="primary" type="submit" disabled={busy || !categoryId}>
          {busy ? 'Сохраняем…' : 'Добавить'}
        </button>
      </form>
    </section>
  )
}

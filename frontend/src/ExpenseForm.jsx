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
  const [quick, setQuick] = useState('')
  const [quickBusy, setQuickBusy] = useState(false)
  const [quickHint, setQuickHint] = useState('')

  // Когда категории загрузились, выбираем первую по умолчанию
  useEffect(() => {
    if (!categoryId && categories.length) setCategoryId(String(categories[0].id))
  }, [categories, categoryId])

  // «lunch at canteen 2500» -> подставляем сумму, категорию, дату и описание в форму; сохраняет пользователь сам
  async function quickFill(e) {
    e.preventDefault()
    if (!quick.trim()) return
    setError('')
    setQuickHint('')
    setQuickBusy(true)
    try {
      const r = await api.parseExpense(quick.trim())
      setType(r.type)
      setAmount(String(r.amount))
      setCategoryId(String(r.category_id))
      setNote(r.note)
      setDate(r.spent_at)
      setQuickHint(`Filled in: ${r.category}${r.source === 'ai' ? ' (picked by AI)' : ''}. Check the details and press Add.`)
      setQuick('')
    } catch (err) {
      setError(err.message)
    } finally {
      setQuickBusy(false)
    }
  }

  async function submit(e) {
    e.preventDefault()
    setError('')
    const value = Number(amount)
    if (!value || value <= 0) {
      setError('Enter an amount greater than zero')
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
      <h2>New entry</h2>
      <form className="quick" onSubmit={quickFill}>
        <label className="sr-only" htmlFor="quick-add">
          Describe the entry in your own words
        </label>
        <input
          id="quick-add"
          value={quick}
          onChange={(e) => setQuick(e.target.value)}
          maxLength={300}
          placeholder="Type it like “lunch at canteen 2500”"
          autoComplete="off"
        />
        <button className="secondary" type="submit" disabled={quickBusy || !quick.trim()}>
          {quickBusy ? 'Reading…' : 'Fill in'}
        </button>
      </form>
      {quickHint && <p className="ok-note">{quickHint}</p>}
      <form className="expense-form" onSubmit={submit}>
        <div className="segmented" role="group" aria-label="Entry type">
          <button
            type="button"
            className={type === 'expense' ? 'on' : ''}
            aria-pressed={type === 'expense'}
            onClick={() => setType('expense')}
          >
            Expense
          </button>
          <button
            type="button"
            className={type === 'income' ? 'on' : ''}
            aria-pressed={type === 'income'}
            onClick={() => setType('income')}
          >
            Income
          </button>
        </div>

        <div className="grid-2">
          <label>
            Amount, ₸
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
            Category
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
            Note
            <input
              value={note}
              maxLength={255}
              onChange={(e) => setNote(e.target.value)}
              placeholder="For example, lunch"
            />
          </label>
          <label>
            Date
            <input type="date" required value={date} onChange={(e) => setDate(e.target.value)} />
          </label>
        </div>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <button className="primary" type="submit" disabled={busy || !categoryId}>
          {busy ? 'Saving…' : 'Add'}
        </button>
      </form>
    </section>
  )
}

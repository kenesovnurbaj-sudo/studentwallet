import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'
import { money, todayISO } from './format.js'
import SplitEditor, { buildRequest, emptySplit, incompleteReason } from './SplitEditor.jsx'

// Одна форма и для новой записи, и для редактирования (когда передан editing).
export default function ExpenseForm({ categories, editing, onSaved, onCancelEdit, onCategoryCreated }) {
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
  const [split, setSplit] = useState(emptySplit())

  const [newCatOpen, setNewCatOpen] = useState(false)
  const [newCatName, setNewCatName] = useState('')
  const [newCatIcon, setNewCatIcon] = useState('🏷️')

  const sectionRef = useRef(null)

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

  // Нажали «изменить» в истории: подставляем данные записи и прокручиваем к форме
  useEffect(() => {
    if (!editing) return
    setType(editing.type)
    setAmount(String(editing.amount))
    setCategoryId(String(editing.category_id))
    setNote(editing.note || '')
    setDate(editing.spent_at)
    setSplit(emptySplit())
    setError('')
    if (sectionRef.current) sectionRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [editing])

  function resetFields() {
    setType('expense')
    setAmount('')
    setNote('')
    setDate(todayISO())
    setSplit(emptySplit())
    setError('')
  }

  function cancelEdit() {
    resetFields()
    onCancelEdit()
  }

  // Редактируем трату, которую вы разделили: сумму менять нельзя, она связана с долгами друзей
  const sharedEdit = Boolean(editing && editing.paid_total != null)
  const splitting = split.on && !editing && type === 'expense'
  const itemsMode = splitting && split.mode === 'items'

  async function submit(e) {
    e.preventDefault()
    setError('')
    const value = Number(amount)
    const common = { category_id: Number(categoryId), type, note: note.trim(), spent_at: date }
    let payload

    if (splitting) {
      const reason = incompleteReason(split, amount)
      if (reason) {
        setError(reason)
        return
      }
      payload = { ...buildRequest(split, amount), ...common, source: 'web' }
    } else if (sharedEdit) {
      payload = common
    } else {
      if (!value || value <= 0) {
        setError('Enter an amount greater than zero')
        return
      }
      payload = { amount: value, ...common }
    }

    setBusy(true)
    try {
      if (editing) await api.updateExpense(editing.id, payload)
      else await api.addExpense({ ...payload, source: 'web' })
      resetFields()
      onSaved()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function createCategory() {
    const name = newCatName.trim()
    if (!name) {
      setError('Enter a category name')
      return
    }
    setError('')
    try {
      const created = await api.addCategory({ name, icon: newCatIcon.trim() })
      await onCategoryCreated()
      setCategoryId(String(created.id))
      setNewCatOpen(false)
      setNewCatName('')
    } catch (err) {
      setError(err.message)
    }
  }

  function onNewCatKey(e) {
    if (e.key === 'Enter') {
      e.preventDefault() // не отправляем основную форму
      createCategory()
    }
  }

  return (
    <section className="block" ref={sectionRef}>
      <h2>{editing ? 'Edit entry' : 'New entry'}</h2>
      {!editing && (
        <>
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
        </>
      )}
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
          {itemsMode ? (
            <div className="amount-auto">
              <span>Bill total</span>
              <p className="muted small">Calculated from the items below</p>
            </div>
          ) : (
            <label>
              {splitting ? 'Bill total, ₸' : 'Amount, ₸'}
              <input
                type="number"
                inputMode="decimal"
                min="1"
                step="any"
                required
                disabled={sharedEdit}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="1500"
              />
            </label>
          )}
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

        {newCatOpen ? (
          <div className="new-cat">
            <label className="new-cat-icon">
              Icon
              <input value={newCatIcon} maxLength={8} onChange={(e) => setNewCatIcon(e.target.value)} onKeyDown={onNewCatKey} />
            </label>
            <label className="new-cat-name">
              Category name
              <input
                value={newCatName}
                maxLength={60}
                onChange={(e) => setNewCatName(e.target.value)}
                onKeyDown={onNewCatKey}
                placeholder="For example, coffee"
                autoFocus
              />
            </label>
            <button type="button" className="secondary" onClick={createCategory}>
              Create
            </button>
            <button type="button" className="link" onClick={() => setNewCatOpen(false)}>
              Cancel
            </button>
          </div>
        ) : (
          <button type="button" className="link start" onClick={() => setNewCatOpen(true)}>
            New category
          </button>
        )}

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

        {sharedEdit && (
          <p className="notice">
            This is a shared bill: the whole bill is {money(editing.paid_total)}, your share is {money(editing.amount)}. The
            amount cannot be changed, but you can edit the category, note and date.
          </p>
        )}

        {!editing && type === 'expense' && (
          <>
            <div className="split-toggle">
              <button
                type="button"
                className={`secondary ${split.on ? 'on' : ''}`}
                aria-pressed={split.on}
                onClick={() => setSplit({ ...split, on: !split.on })}
              >
                {split.on ? '✓ Splitting with friends' : '+ Split with friends'}
              </button>
              <span className="muted small">Paid for others? Split the bill and track who owes you.</span>
            </div>
            {split.on && <SplitEditor split={split} amount={amount} onChange={setSplit} />}
          </>
        )}

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <div className="row">
          <button className="primary" type="submit" disabled={busy || !categoryId}>
            {busy ? 'Saving…' : editing ? 'Save changes' : 'Add'}
          </button>
          {editing && (
            <button className="link" type="button" onClick={cancelEdit}>
              Cancel
            </button>
          )}
        </div>
      </form>
    </section>
  )
}

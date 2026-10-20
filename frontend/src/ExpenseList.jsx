import { useMemo, useState } from 'react'
import { api } from './api.js'
import { money, shortDate } from './format.js'
import SplitExpenseModal from './SplitExpenseModal.jsx'

export default function ExpenseList({ expenses, categories, filter, onFilter, onChanged, onEdit, editingId }) {
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [selecting, setSelecting] = useState(false)
  const [picked, setPicked] = useState(() => new Set())
  const [target, setTarget] = useState('')
  const [busy, setBusy] = useState(false)
  const [splitting, setSplitting] = useState(null) // запись, которую делим с друзьями
  const byId = Object.fromEntries(categories.map((c) => [c.id, c]))

  async function remove(item) {
    const name = item.note || (byId[item.category_id] && byId[item.category_id].name) || 'entry'
    if (!window.confirm(`Delete “${name}” for ${money(item.amount)}?`)) return
    setError('')
    try {
      await api.deleteExpense(item.id)
      onChanged(item.id)
    } catch (err) {
      setError(err.message)
    }
  }

  const q = query.trim().toLowerCase()
  const shown = useMemo(
    () => (q ? expenses.filter((e) => (e.note || '').toLowerCase().includes(q)) : expenses),
    [expenses, q],
  )
  const pickedShown = shown.filter((e) => picked.has(e.id))
  const allPicked = shown.length > 0 && pickedShown.length === shown.length

  function toggle(id) {
    const next = new Set(picked)
    next.has(id) ? next.delete(id) : next.add(id)
    setPicked(next)
  }

  function toggleAll() {
    const next = new Set(picked)
    shown.forEach((e) => (allPicked ? next.delete(e.id) : next.add(e.id)))
    setPicked(next)
  }

  function stopSelecting() {
    setSelecting(false)
    setPicked(new Set())
    setTarget('')
  }

  async function applyBulk() {
    if (!target || pickedShown.length === 0) return
    setError('')
    setBusy(true)
    try {
      await api.bulkCategory(
        pickedShown.map((e) => e.id),
        Number(target),
      )
      stopSelecting()
      onChanged()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="block">
      <div className="block-head">
        <h2>History</h2>
        <button className="link" type="button" onClick={() => (selecting ? stopSelecting() : setSelecting(true))}>
          {selecting ? 'Done' : 'Select multiple'}
        </button>
        <label className="filter">
          <span className="sr-only">Filter by category</span>
          <select value={filter} onChange={(e) => onFilter(e.target.value)}>
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.icon} {c.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <input
        className="search"
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search by note, for example “NANGO”"
        aria-label="Search by note"
      />

      {selecting && (
        <div className="bulk-bar">
          <button className="secondary" type="button" onClick={toggleAll} disabled={shown.length === 0}>
            {allPicked ? 'Clear selection' : `Select all (${shown.length})`}
          </button>
          <select value={target} onChange={(e) => setTarget(e.target.value)} aria-label="New category">
            <option value="">New category…</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.icon} {c.name}
              </option>
            ))}
          </select>
          <button className="primary" type="button" disabled={busy || !target || pickedShown.length === 0} onClick={applyBulk}>
            {busy ? 'Updating…' : `Apply (${pickedShown.length})`}
          </button>
        </div>
      )}

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {shown.length === 0 && expenses.length > 0 ? (
        <p className="empty">Nothing found.</p>
      ) : expenses.length === 0 ? (
        <p className="empty">
          {filter ? 'No entries in this category.' : 'No entries yet. Add your first expense above.'}
        </p>
      ) : (
        <ul className="rows">
          {shown.map((item) => {
            const cat = byId[item.category_id]
            const income = item.type === 'income'
            const title = item.note || (cat ? cat.name : 'Untitled')
            return (
              <li key={item.id} className={`row-item ${editingId === item.id ? 'is-editing' : ''}`}>
                {selecting && (
                  <input
                    type="checkbox"
                    checked={picked.has(item.id)}
                    onChange={() => toggle(item.id)}
                    aria-label={`Select: ${item.note || 'entry'} ${money(item.amount)}`}
                  />
                )}
                <span className="row-icon" aria-hidden="true">
                  {cat ? cat.icon : '🧾'}
                </span>
                <span className="row-main">
                  <span className="row-title">{title}</span>
                  <span className="row-sub">
                    {cat ? cat.name : 'No category'}, {shortDate(item.spent_at)}
                    {item.source === 'siri' ? ', via Siri' : ''}
                    {item.paid_total != null ? `, your share of the ${money(item.paid_total)} bill` : ''}
                  </span>
                </span>
                <span className={`row-amount ${income ? 'plus' : ''}`}>
                  {income ? '+' : '−'}
                  {money(item.amount)}
                </span>
                {!income && item.paid_total == null && !selecting && (
                  <button
                    className="split-btn"
                    type="button"
                    onClick={() => setSplitting(item)}
                    aria-label={`Split “${title}” with friends`}
                    title="Split with friends"
                  >
                    Split
                  </button>
                )}
                <button
                  className="icon-btn"
                  type="button"
                  onClick={() => onEdit(item)}
                  aria-label={`Edit entry “${title}”`}
                  title="Edit"
                >
                  ✎
                </button>
                <button
                  className="icon-btn"
                  type="button"
                  onClick={() => remove(item)}
                  aria-label={`Delete entry “${title}”`}
                  title="Delete"
                >
                  ×
                </button>
              </li>
            )
          })}
        </ul>
      )}
      {splitting && (
        <SplitExpenseModal expense={splitting} onClose={() => setSplitting(null)} onDone={() => onChanged()} />
      )}
    </section>
  )
}

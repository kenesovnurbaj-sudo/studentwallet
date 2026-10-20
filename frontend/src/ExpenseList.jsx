import { useMemo, useState } from 'react'
import { api } from './api.js'
import { money, shortDate } from './format.js'

export default function ExpenseList({ expenses, categories, filter, onFilter, onChanged }) {
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [selecting, setSelecting] = useState(false)
  const [picked, setPicked] = useState(() => new Set())
  const [target, setTarget] = useState('')
  const [busy, setBusy] = useState(false)
  const byId = Object.fromEntries(categories.map((c) => [c.id, c]))

  async function remove(item) {
    const name = item.note || (byId[item.category_id] && byId[item.category_id].name) || 'запись'
    if (!window.confirm(`Удалить «${name}» на ${money(item.amount)}?`)) return
    setError('')
    try {
      await api.deleteExpense(item.id)
      onChanged()
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
        <h2>История</h2>
        <button className="link" type="button" onClick={() => (selecting ? stopSelecting() : setSelecting(true))}>
          {selecting ? 'Готово' : 'Выбрать несколько'}
        </button>
        <label className="filter">
          <span className="sr-only">Фильтр по категории</span>
          <select value={filter} onChange={(e) => onFilter(e.target.value)}>
            <option value="">Все категории</option>
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
        placeholder="Поиск по описанию, например «NANGO»"
        aria-label="Поиск по описанию"
      />

      {selecting && (
        <div className="bulk-bar">
          <label className="check">
            <input type="checkbox" checked={allPicked} onChange={toggleAll} />
            Все найденные ({shown.length})
          </label>
          <select value={target} onChange={(e) => setTarget(e.target.value)} aria-label="Новая категория">
            <option value="">Новая категория…</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.icon} {c.name}
              </option>
            ))}
          </select>
          <button className="primary" type="button" disabled={busy || !target || pickedShown.length === 0} onClick={applyBulk}>
            {busy ? 'Меняем…' : `Применить (${pickedShown.length})`}
          </button>
        </div>
      )}

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {shown.length === 0 && expenses.length > 0 ? (
        <p className="empty">Ничего не найдено.</p>
      ) : expenses.length === 0 ? (
        <p className="empty">
          {filter ? 'В этой категории записей нет.' : 'Записей пока нет. Добавьте первую трату выше.'}
        </p>
      ) : (
        <ul className="rows">
          {shown.map((item) => {
            const cat = byId[item.category_id]
            const income = item.type === 'income'
            return (
              <li key={item.id} className="row-item">
                {selecting && (
                  <input
                    type="checkbox"
                    checked={picked.has(item.id)}
                    onChange={() => toggle(item.id)}
                    aria-label={`Выбрать: ${item.note || 'запись'} ${money(item.amount)}`}
                  />
                )}
                <span className="row-icon" aria-hidden="true">
                  {cat ? cat.icon : '🧾'}
                </span>
                <span className="row-main">
                  <span className="row-title">{item.note || (cat ? cat.name : 'Без названия')}</span>
                  <span className="row-sub">
                    {cat ? cat.name : 'Без категории'}, {shortDate(item.spent_at)}
                    {item.source === 'siri' ? ', через Siri' : ''}
                  </span>
                </span>
                <span className={`row-amount ${income ? 'plus' : ''}`}>
                  {income ? '+' : '−'}
                  {money(item.amount)}
                </span>
                <button
                  className="icon-btn"
                  type="button"
                  onClick={() => remove(item)}
                  aria-label={`Удалить запись на ${money(item.amount)}`}
                >
                  ×
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

import { useState } from 'react'
import { api } from './api.js'
import { money, shortDate } from './format.js'

export default function ExpenseList({ expenses, categories, filter, onFilter, onChanged, onEdit, editingId }) {
  const [error, setError] = useState('')
  const byId = Object.fromEntries(categories.map((c) => [c.id, c]))

  async function remove(item) {
    const name = item.note || (byId[item.category_id] && byId[item.category_id].name) || 'запись'
    if (!window.confirm(`Удалить «${name}» на ${money(item.amount)}?`)) return
    setError('')
    try {
      await api.deleteExpense(item.id)
      onChanged(item.id)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <section className="block">
      <div className="block-head">
        <h2>История</h2>
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

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {expenses.length === 0 ? (
        <p className="empty">
          {filter ? 'В этой категории записей нет.' : 'Записей пока нет. Добавьте первую трату выше.'}
        </p>
      ) : (
        <ul className="rows">
          {expenses.map((item) => {
            const cat = byId[item.category_id]
            const income = item.type === 'income'
            const title = item.note || (cat ? cat.name : 'Без названия')
            return (
              <li key={item.id} className={`row-item ${editingId === item.id ? 'is-editing' : ''}`}>
                <span className="row-icon" aria-hidden="true">
                  {cat ? cat.icon : '🧾'}
                </span>
                <span className="row-main">
                  <span className="row-title">{title}</span>
                  <span className="row-sub">
                    {cat ? cat.name : 'Без категории'}, {shortDate(item.spent_at)}
                    {item.source === 'siri' ? ', через Siri' : ''}
                    {item.paid_total != null ? `, ваша доля из чека ${money(item.paid_total)}` : ''}
                  </span>
                </span>
                <span className={`row-amount ${income ? 'plus' : ''}`}>
                  {income ? '+' : '−'}
                  {money(item.amount)}
                </span>
                <button
                  className="icon-btn"
                  type="button"
                  onClick={() => onEdit(item)}
                  aria-label={`Изменить запись «${title}»`}
                  title="Изменить"
                >
                  ✎
                </button>
                <button
                  className="icon-btn"
                  type="button"
                  onClick={() => remove(item)}
                  aria-label={`Удалить запись «${title}»`}
                  title="Удалить"
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

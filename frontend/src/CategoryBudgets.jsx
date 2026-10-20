import { useEffect, useState } from 'react'
import { api } from './api.js'
import { money, monthTitle } from './format.js'
import { categoryName } from './categories.js'

export default function CategoryBudgets({
  categories,
  expenses,
  month,
  refreshKey,
  onSaved,
}) {
  const [budgets, setBudgets] = useState([])
  const [categoryId, setCategoryId] = useState('')
  const [amount, setAmount] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    let active = true

    setLoading(true)
    setError('')

    api.budgets(month)
      .then((data) => {
        if (active) setBudgets(data)
      })
      .catch((err) => {
        if (active) setError(err.message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [month, refreshKey])

  function chooseCategory(id) {
    setCategoryId(id)
    setError('')
    setSuccess('')

    const existing = budgets.find(
      (budget) => String(budget.category_id) === id
    )

    setAmount(existing ? String(existing.limit_amount) : '')
  }

  async function save(e) {
    e.preventDefault()
    setError('')
    setSuccess('')

    const value = Number(amount)

    if (
      !categories.some(
        (category) => String(category.id) === categoryId
      )
    ) {
      setError('Choose a category.')
      return
    }

    if (!Number.isFinite(value) || value <= 0) {
      setError('Enter a limit greater than zero.')
      return
    }

    setBusy(true)

    try {
      const saved = await api.setBudget({
        month,
        category_id: Number(categoryId),
        limit_amount: value,
      })

      setBudgets((previous) => [
        ...previous.filter(
          (budget) =>
            String(budget.category_id) !== String(saved.category_id)
        ),
        saved,
      ])

      setSuccess('Category limit saved.')
      onSaved?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const spending = new Map()

  for (const item of expenses) {
    if (
      item.type === 'expense' &&
      item.spent_at.startsWith(`${month}-`)
    ) {
      const cents = Math.round(Number(item.amount) * 100)
      const id = String(item.category_id)

      spending.set(id, (spending.get(id) || 0) + cents)
    }
  }

  return (
    <section className="block">
      <h2>Category budgets</h2>

      <p className="chart-caption">
        {monthTitle(month)}. Category limits do not change your
        overall monthly budget.
      </p>

      {loading ? (
        <p className="empty">Loading category limits…</p>
      ) : (
        <>
          <form className="expense-form" onSubmit={save}>
            <div className="grid-2">
              <label>
                Category
                <select
                  required
                  disabled={busy}
                  value={categoryId}
                  onChange={(e) => chooseCategory(e.target.value)}
                >
                  <option value="">Choose a category</option>

                  {categories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {categoryName(category.name)}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Monthly category limit, ₸
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  required
                  disabled={busy}
                  value={amount}
                  onChange={(e) => {
                    setAmount(e.target.value)
                    setSuccess('')
                  }}
                  placeholder="For example, 20000"
                />
              </label>
            </div>

            <button
              className="primary"
              type="submit"
              disabled={busy || !categoryId}
            >
              {busy ? 'Saving…' : 'Save category limit'}
            </button>

            {success && <p role="status">{success}</p>}
          </form>

          <div className="category-budget-list">
            {categories.map((category) => {
              const budget = budgets.find(
                (item) =>
                  String(item.category_id) === String(category.id)
              )

              const spentCents =
                spending.get(String(category.id)) || 0
              const spent = spentCents / 100
              const limitCents = budget
                ? Math.round(Number(budget.limit_amount) * 100)
                : 0
              const hasLimit = limitCents > 0

              const percent = hasLimit
                ? (spentCents / limitCents) * 100
                : 0
              const remaining = (limitCents - spentCents) / 100

              const color =
                percent > 100
                  ? '#b4232f'
                  : percent >= 70
                    ? '#b56a00'
                    : '#00856a'

              const name = categoryName(category.name)

              return (
                <div
                  className="category-budget-card"
                  key={category.id}
                >
                  <div className="block-head">
                    <strong>{name}</strong>
                    <span>Spent {money(spent)}</span>
                  </div>

                  {hasLimit ? (
                    <>
                      <p>
                        Limit: {money(limitCents / 100)}
                        {' · '}
                        {remaining < 0
                          ? `Over by ${money(Math.abs(remaining))}`
                          : `Left: ${money(remaining)}`}
                      </p>

                      <div
                        className="category-meter"
                        role="progressbar"
                        aria-label={`${name} budget used`}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={Math.min(
                          100,
                          Math.round(percent)
                        )}
                        aria-valuetext={`${percent.toFixed(1)}% used`}
                      >
                        <div
                          style={{
                            width: `${Math.min(percent, 100)}%`,
                            background: color,
                          }}
                        />
                      </div>

                      <p className="chart-caption">
                        {percent.toFixed(1)}% used
                      </p>

                      {percent >= 80 && (
                        <p
                          className="category-warning"
                          role="status"
                        >
                          {percent > 100
                            ? 'Category limit exceeded.'
                            : percent >= 100
                              ? 'Category limit reached.'
                              : 'You have used at least 80% of this category limit.'}
                        </p>
                      )}
                    </>
                  ) : (
                    <p className="chart-caption">
                      No valid limit set. Choose this category above
                      to set one.
                    </p>
                  )}
                </div>
              )
            })}
          </div>
        </>
      )}

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </section>
  )
}
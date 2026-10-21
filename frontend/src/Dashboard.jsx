import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import { monthISO } from './format.js'
import Hero from './Hero.jsx'
import ExpenseForm from './ExpenseForm.jsx'
import ExpenseList from './ExpenseList.jsx'
import ImportStatement from './ImportStatement.jsx'
import BudgetSplit from './BudgetSplit.jsx'
import ForecastCard from './ForecastCard.jsx'
import CategoryBalances from './CategoryBalances.jsx'
import Assistant from './Assistant.jsx'

export default function Dashboard({ user, onLogout }) {
  const month = monthISO()
  const [categories, setCategories] = useState([])
  const [expenses, setExpenses] = useState([])
  const [summary, setSummary] = useState(undefined) // undefined = грузится, null = бюджет не задан
  const [filter, setFilter] = useState('')
  const [error, setError] = useState('')
  const [importOpen, setImportOpen] = useState(false)
  const [splitOpen, setSplitOpen] = useState(false)
  const [tick, setTick] = useState(0) // меняется, когда данные бюджета устарели: карточки прогноза и категорий перезапрашиваются

  const loadSummary = useCallback(async () => {
    try {
      setSummary(await api.summary(month))
      setTick((t) => t + 1)
    } catch (err) {
      if (err.status === 404) setSummary(null)
      else setError(err.message)
    }
  }, [month])

  const loadExpenses = useCallback(async () => {
    try {
      setExpenses(await api.expenses(filter))
    } catch (err) {
      setError(err.message)
    }
  }, [filter])

  useEffect(() => {
    api.categories().then(setCategories).catch((err) => setError(err.message))
  }, [])
  useEffect(() => {
    loadSummary()
  }, [loadSummary])
  useEffect(() => {
    loadExpenses()
  }, [loadExpenses])

  const refresh = () => {
    setError('')
    loadSummary()
    loadExpenses()
  }

  return (
    <div className="page">
      <header className="topbar">
        <span className="wordmark small">StudentWallet</span>
        <span className="who">
          <button className="secondary" type="button" onClick={() => setImportOpen(true)}>
            Import statement
          </button>
          {user.full_name || user.email}
          <button className="link" type="button" onClick={onLogout}>
            Log out
          </button>
        </span>
      </header>

      <main>
        {error && (
          <p className="error banner" role="alert">
            {error}
          </p>
        )}
        <Hero summary={summary} month={month} onSaved={loadSummary} />
        {summary && <ForecastCard month={month} refreshKey={tick} />}
        {summary && (
          <p className="split-row">
            <button className="secondary" type="button" onClick={() => setSplitOpen(true)}>
              Split budget with AI
            </button>
          </p>
        )}
        {summary !== undefined && <CategoryBalances month={month} refreshKey={tick} />}
        <ExpenseForm categories={categories} onAdded={refresh} />
        <ExpenseList
          expenses={expenses}
          categories={categories}
          filter={filter}
          onFilter={setFilter}
          onChanged={refresh}
        />
      </main>

      {splitOpen && <BudgetSplit month={month} onSaved={() => setTick((t) => t + 1)} onClose={() => setSplitOpen(false)} />}
      {importOpen && (
        <ImportStatement categories={categories} onImported={refresh} onClose={() => setImportOpen(false)} />
      )}
      <Assistant />
    </div>
  )
}

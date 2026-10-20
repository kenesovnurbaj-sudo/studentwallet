import { useCallback, useEffect, useState } from 'react'
import { api } from './api.js'
import { monthISO } from './format.js'
import Hero from './Hero.jsx'
import ExpenseForm from './ExpenseForm.jsx'
import ExpenseList from './ExpenseList.jsx'
import ImportStatement from './ImportStatement.jsx'
import Assistant from './Assistant.jsx'

export default function Dashboard({ user, onLogout }) {
  const month = monthISO()
  const [categories, setCategories] = useState([])
  const [expenses, setExpenses] = useState([])
  const [summary, setSummary] = useState(undefined) // undefined = грузится, null = бюджет не задан
  const [filter, setFilter] = useState('')
  const [error, setError] = useState('')
  const [importOpen, setImportOpen] = useState(false)

  const loadSummary = useCallback(async () => {
    try {
      setSummary(await api.summary(month))
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
            Импорт выписки
          </button>
          {user.full_name || user.email}
          <button className="link" type="button" onClick={onLogout}>
            Выйти
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
        <ExpenseForm categories={categories} onAdded={refresh} />
        <ExpenseList
          expenses={expenses}
          categories={categories}
          filter={filter}
          onFilter={setFilter}
          onChanged={refresh}
        />
      </main>

      {importOpen && (
        <ImportStatement categories={categories} onImported={refresh} onClose={() => setImportOpen(false)} />
      )}
      <Assistant />
    </div>
  )
}

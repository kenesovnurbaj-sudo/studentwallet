import { useEffect, useState } from 'react'
import { api } from './api.js'
import { money } from './format.js'
import SplitEditor, { buildRequest, emptySplit, incompleteReason } from './SplitEditor.jsx'

// Разделить уже сохранённую трату: заплатили, а потом решили поделить счёт с друзьями.
export default function SplitExpenseModal({ expense, onClose, onDone }) {
  const [split, setSplit] = useState({ ...emptySplit(), on: true })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const title = expense.note || 'this expense'

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && !busy && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [busy, onClose])

  async function submit() {
    const reason = incompleteReason(split, expense.amount)
    if (reason) {
      setError(reason)
      return
    }
    setError('')
    setBusy(true)
    try {
      await api.splitExpense(expense.id, buildRequest(split, expense.amount).split)
      onDone()
      onClose()
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}>
      <section className="modal" role="dialog" aria-modal="true" aria-labelledby="split-exp-title">
        <header className="modal-head">
          <h2 id="split-exp-title">Split “{title}”</h2>
          <button type="button" className="modal-close" onClick={onClose} disabled={busy} aria-label="Close">
            ×
          </button>
        </header>
        <p className="hint">
          The bill is {money(expense.amount)}. After splitting, only your share stays in your budget; your friends’ shares become debts
          they owe you.
        </p>

        <SplitEditor split={split} amount={String(expense.amount)} onChange={setSplit} />

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <div className="import-actions">
          <button className="primary" type="button" disabled={busy} onClick={submit}>
            {busy ? 'Saving…' : 'Split this expense'}
          </button>
          <button className="link" type="button" disabled={busy} onClick={onClose}>
            Cancel
          </button>
        </div>
      </section>
    </div>
  )
}

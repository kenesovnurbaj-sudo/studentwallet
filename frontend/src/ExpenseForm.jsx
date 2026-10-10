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
  const [split, setSplit] = useState(emptySplit())

  const [newCatOpen, setNewCatOpen] = useState(false)
  const [newCatName, setNewCatName] = useState('')
  const [newCatIcon, setNewCatIcon] = useState('🏷️')

  const sectionRef = useRef(null)

  // Когда категории загрузились, выбираем первую по умолчанию
  useEffect(() => {
    if (!categoryId && categories.length) setCategoryId(String(categories[0].id))
  }, [categories, categoryId])

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
        setError('Введите сумму больше нуля')
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
      setError('Введите название категории')
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
      <h2>{editing ? 'Изменить запись' : 'Новая запись'}</h2>
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
          {itemsMode ? (
            <div className="amount-auto">
              <span>Сумма чека</span>
              <p className="muted small">Посчитается по позициям ниже</p>
            </div>
          ) : (
            <label>
              {splitting ? 'Сумма по чеку, ₸' : 'Сумма, ₸'}
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

        {newCatOpen ? (
          <div className="new-cat">
            <label className="new-cat-icon">
              Значок
              <input value={newCatIcon} maxLength={8} onChange={(e) => setNewCatIcon(e.target.value)} onKeyDown={onNewCatKey} />
            </label>
            <label className="new-cat-name">
              Название категории
              <input
                value={newCatName}
                maxLength={60}
                onChange={(e) => setNewCatName(e.target.value)}
                onKeyDown={onNewCatKey}
                placeholder="Например, кофе"
                autoFocus
              />
            </label>
            <button type="button" className="secondary" onClick={createCategory}>
              Создать
            </button>
            <button type="button" className="link" onClick={() => setNewCatOpen(false)}>
              Отмена
            </button>
          </div>
        ) : (
          <button type="button" className="link start" onClick={() => setNewCatOpen(true)}>
            Своя категория
          </button>
        )}

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

        {sharedEdit && (
          <p className="notice">
            Это общий счёт: весь чек {money(editing.paid_total)}, ваша доля {money(editing.amount)}. Сумму изменить
            нельзя, но можно поправить категорию, комментарий и дату.
          </p>
        )}

        {!editing && type === 'expense' && (
          <>
            <label className="check">
              <input
                type="checkbox"
                checked={split.on}
                onChange={(e) => setSplit({ ...split, on: e.target.checked })}
              />
              <span>Платил за друзей: они вернут свою долю</span>
            </label>
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
            {busy ? 'Сохраняем…' : editing ? 'Сохранить изменения' : 'Добавить'}
          </button>
          {editing && (
            <button className="link" type="button" onClick={cancelEdit}>
              Отмена
            </button>
          )}
        </div>
      </form>
    </section>
  )
}

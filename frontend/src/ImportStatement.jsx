import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'
import { money, shortDate } from './format.js'

// Импорт выписки Kaspi Gold (PDF): загрузка, предпросмотр с правкой категорий, подтверждение.
export default function ImportStatement({ categories, onImported, onClose }) {
  const [rows, setRows] = useState(null) // null = файл ещё не загружен
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState('')
  const fileRef = useRef(null)

  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && !busy && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [busy, onClose])

  async function pick(e) {
    const file = e.target.files[0]
    e.target.value = ''
    if (!file) return
    setError('')
    setResult('')
    setBusy(true)
    try {
      const data = await api.importKaspi(file)
      // Не импортируем по умолчанию: уже загруженные, внесённые вручную и переводы между своими счетами
      setRows(data.rows.map((r) => ({ ...r, on: !r.duplicate && !r.own_account && !r.manual_match })))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const update = (i, patch) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)))
  const selected = rows ? rows.filter((r) => r.on) : []

  async function confirm() {
    setError('')
    setBusy(true)
    try {
      const { imported, skipped_duplicates } = await api.importCommit(
        selected.map(({ date, amount, type, note, category_id }) => ({ date, amount, type, note, category_id })),
      )
      setResult(`Добавлено операций: ${imported}${skipped_duplicates ? `, пропущено дубликатов: ${skipped_duplicates}` : ''}`)
      setRows(null)
      onImported()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && !busy && onClose()}>
    <section className="modal" role="dialog" aria-modal="true" aria-labelledby="import-title">
      <header className="modal-head">
        <h2 id="import-title">Импорт выписки Kaspi</h2>
        <button type="button" className="modal-close" onClick={onClose} disabled={busy} aria-label="Закрыть">
          ×
        </button>
      </header>
      <p className="hint">Загрузите PDF-выписку Kaspi Gold на английском: Kaspi.kz → Gold → Выписка. Перед сохранением вы увидите список и сможете поправить категории. Уже загруженное повторно не добавится.</p>

      <input ref={fileRef} type="file" accept="application/pdf,.pdf" onChange={pick} hidden />
      {!rows && (
        <button className="primary" type="button" disabled={busy} onClick={() => fileRef.current.click()}>
          {busy ? 'Читаем файл…' : 'Выбрать PDF'}
        </button>
      )}

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {result && <p className="ok-note">{result}</p>}

      {rows && (
        <>
          <div className="import-scroll">
            <table className="import-table">
              <thead>
                <tr>
                  <th aria-label="Импортировать" />
                  <th>Дата</th>
                  <th>Описание</th>
                  <th>Категория</th>
                  <th className="num">Сумма</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} className={r.on ? '' : 'off'}>
                    <td>
                      <input type="checkbox" checked={r.on} onChange={(e) => update(i, { on: e.target.checked })} aria-label={`Импортировать: ${r.note}`} />
                    </td>
                    <td>{shortDate(r.date)}</td>
                    <td>
                      {r.note}
                      {r.duplicate && <span className="tag">уже загружено</span>}
                      {r.manual_match && <span className="tag">возможно, уже внесено вручную</span>}
                      {r.own_account && <span className="tag">между своими счетами</span>}
                    </td>
                    <td>
                      <select value={r.category_id} onChange={(e) => update(i, { category_id: Number(e.target.value) })} aria-label="Категория">
                        {categories.map((c) => (
                          <option key={c.id} value={c.id}>
                            {c.icon} {c.name}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className={`num ${r.type}`}>
                      {r.type === 'income' ? '+' : '−'}
                      {money(r.amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="import-actions">
            <button className="primary" type="button" disabled={busy || selected.length === 0} onClick={confirm}>
              {busy ? 'Сохраняем…' : `Импортировать (${selected.length})`}
            </button>
            <button className="link" type="button" disabled={busy} onClick={() => setRows(null)}>
              Отмена
            </button>
          </div>
        </>
      )}
    </section>
    </div>
  )
}

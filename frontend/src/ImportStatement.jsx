import { useRef, useState } from 'react'
import { api } from './api.js'
import { money, shortDate } from './format.js'

// Импорт выписки Kaspi Gold (PDF): загрузка, предпросмотр с правкой категорий, подтверждение.
export default function ImportStatement({ categories, onImported }) {
  const [rows, setRows] = useState(null) // null = файл ещё не загружен
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState('')
  const fileRef = useRef(null)

  async function pick(e) {
    const file = e.target.files[0]
    e.target.value = ''
    if (!file) return
    setError('')
    setResult('')
    setBusy(true)
    try {
      const data = await api.importKaspi(file)
      // Не импортируем по умолчанию: уже загруженные раньше и переводы между своими счетами
      setRows(data.rows.map((r) => ({ ...r, on: !r.duplicate && !r.own_account })))
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
    <section className="block">
      <h2>Импорт выписки Kaspi</h2>
      <p className="hint">Загрузите PDF-выписку Kaspi Gold на английском: Kaspi.kz → Gold → Выписка. Перед сохранением вы увидите список и сможете поправить категории.</p>

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
  )
}

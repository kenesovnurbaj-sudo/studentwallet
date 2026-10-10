import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'
import { money } from './format.js'

// Состояние деления счёта живёт в ExpenseForm, а здесь только его редактор и предпросмотр.

export const emptySplit = () => ({ on: false, mode: 'equal', friends: [], items: [], tip: '' })

const MODES = [
  ['equal', 'Поровну'],
  ['custom', 'Вручную'],
  ['items', 'По блюдам'],
]

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const shortName = (email) => email.split('@')[0]

let itemCounter = 0
const newItem = (eaters) => ({ key: ++itemCounter, name: '', price: '', eaters })

// Чего не хватает, чтобы посчитать деление. Пустая строка значит «всё заполнено».
export function incompleteReason(split, amount) {
  if (split.friends.length === 0) return 'Добавьте хотя бы одного друга'
  if (split.mode === 'items') {
    const filled = split.items.filter((i) => Number(i.price) > 0)
    if (filled.length === 0) return 'Добавьте позиции из чека и цены'
    const lonely = filled.find((i) => i.eaters.length === 0)
    if (lonely) return `Отметьте, кто ел «${lonely.name.trim() || 'позиция'}»`
    return ''
  }
  if (!(Number(amount) > 0)) return 'Введите сумму чека'
  if (split.mode === 'custom' && split.friends.some((f) => !(Number(f.amount) > 0))) {
    return 'Укажите сумму для каждого друга'
  }
  return ''
}

function splitPayload(split) {
  const items = split.mode === 'items'
  return {
    mode: split.mode,
    participants: split.friends.map((f) => ({
      email: f.email,
      ...(split.mode === 'custom' ? { amount: Number(f.amount) } : {}),
    })),
    items: items
      ? split.items
          .filter((i) => Number(i.price) > 0)
          .map((i) => ({ name: i.name.trim(), price: Number(i.price), eaters: i.eaters }))
      : [],
    tip_percent: Number(split.tip) || 0,
  }
}

// Часть запроса, общая для предпросмотра и сохранения
export function buildRequest(split, amount) {
  return {
    ...(split.mode === 'items' ? {} : { amount: Number(amount) }),
    split: splitPayload(split),
  }
}

export default function SplitEditor({ split, amount, onChange }) {
  const [draft, setDraft] = useState('')
  const [friendError, setFriendError] = useState('')
  const [preview, setPreview] = useState(null)
  const [previewError, setPreviewError] = useState('')
  const seq = useRef(0)

  const update = (patch) => onChange({ ...split, ...patch })
  const everyone = ['me', ...split.friends.map((f) => f.email)]
  const reason = incompleteReason(split, amount)

  // Предпросмотр: сервер сам считает доли, чтобы цифры на экране совпали с сохранёнными
  const requestKey = reason ? '' : JSON.stringify(buildRequest(split, amount))
  useEffect(() => {
    const id = ++seq.current
    if (!requestKey) {
      setPreview(null)
      setPreviewError('')
      return undefined
    }
    const timer = setTimeout(async () => {
      try {
        const result = await api.splitPreview(JSON.parse(requestKey))
        if (id === seq.current) {
          setPreview(result)
          setPreviewError('')
        }
      } catch (err) {
        if (id === seq.current) {
          setPreview(null)
          setPreviewError(err.message)
        }
      }
    }, 350)
    return () => clearTimeout(timer)
  }, [requestKey])

  function addFriend() {
    const email = draft.trim().toLowerCase()
    if (!email) return
    if (!EMAIL.test(email)) {
      setFriendError('Проверьте email друга')
      return
    }
    if (split.friends.some((f) => f.email === email)) {
      setFriendError('Этот друг уже добавлен')
      return
    }
    setFriendError('')
    setDraft('')
    // Блюдо, которое было «на всех», остаётся «на всех» и с новым другом
    const items = split.items.map((i) =>
      everyone.every((who) => i.eaters.includes(who)) ? { ...i, eaters: [...i.eaters, email] } : i,
    )
    update({ friends: [...split.friends, { email, amount: '' }], items })
  }

  function removeFriend(email) {
    update({
      friends: split.friends.filter((f) => f.email !== email),
      items: split.items.map((i) => ({ ...i, eaters: i.eaters.filter((e) => e !== email) })),
    })
  }

  function setMode(mode) {
    const patch = { mode }
    if (mode === 'items' && split.items.length === 0) patch.items = [newItem(everyone)]
    update(patch)
  }

  const patchFriend = (email, patch) =>
    update({ friends: split.friends.map((f) => (f.email === email ? { ...f, ...patch } : f)) })
  const patchItem = (key, patch) =>
    update({ items: split.items.map((i) => (i.key === key ? { ...i, ...patch } : i)) })
  const toggleEater = (item, who) =>
    patchItem(item.key, {
      eaters: item.eaters.includes(who) ? item.eaters.filter((e) => e !== who) : [...item.eaters, who],
    })

  const onDraftKey = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault() // не отправляем основную форму
      addFriend()
    }
  }

  return (
    <div className="split">
      <div className="segmented" role="group" aria-label="Как делить счёт">
        {MODES.map(([value, label]) => (
          <button
            key={value}
            type="button"
            className={split.mode === value ? 'on' : ''}
            aria-pressed={split.mode === value}
            onClick={() => setMode(value)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="split-friends">
        <label>
          Email друга
          <span className="inline-add">
            <input
              type="email"
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value)
                setFriendError('')
              }}
              onKeyDown={onDraftKey}
              placeholder="friend@gmail.com"
            />
            <button type="button" className="secondary" onClick={addFriend}>
              Добавить
            </button>
          </span>
        </label>
        {friendError ? (
          <p className="error" role="alert">
            {friendError}
          </p>
        ) : (
          <p className="muted small">Друг должен быть зарегистрирован на сайте. Он увидит свой долг у себя.</p>
        )}

        {split.friends.length > 0 && (
          <ul className="friend-list">
            {split.friends.map((f) => (
              <li key={f.email}>
                <span className="friend-name" title={f.email}>
                  {f.email}
                </span>
                {split.mode === 'custom' && (
                  <input
                    className="friend-amount"
                    type="number"
                    inputMode="decimal"
                    min="1"
                    step="any"
                    value={f.amount}
                    onChange={(e) => patchFriend(f.email, { amount: e.target.value })}
                    placeholder="Сумма, ₸"
                    aria-label={`Сколько должен ${f.email}`}
                  />
                )}
                <button
                  type="button"
                  className="icon-btn"
                  onClick={() => removeFriend(f.email)}
                  aria-label={`Убрать ${f.email}`}
                  title="Убрать"
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {split.mode === 'items' && (
        <div className="split-items">
          <h3>Позиции из чека</h3>
          <ul className="item-list">
            {split.items.map((item, index) => (
              <li key={item.key} className="item-row">
                <div className="item-fields">
                  <input
                    value={item.name}
                    maxLength={80}
                    onChange={(e) => patchItem(item.key, { name: e.target.value })}
                    placeholder="Что заказали"
                    aria-label={`Название позиции ${index + 1}`}
                  />
                  <input
                    type="number"
                    inputMode="decimal"
                    min="1"
                    step="any"
                    value={item.price}
                    onChange={(e) => patchItem(item.key, { price: e.target.value })}
                    placeholder="Цена, ₸"
                    aria-label={`Цена позиции ${index + 1}`}
                  />
                  <button
                    type="button"
                    className="icon-btn"
                    onClick={() => update({ items: split.items.filter((i) => i.key !== item.key) })}
                    aria-label={`Убрать позицию ${index + 1}`}
                    title="Убрать"
                  >
                    ×
                  </button>
                </div>
                <div className="eaters" role="group" aria-label="Кто ел">
                  <span className="muted small">Кто ел:</span>
                  {everyone.map((who) => (
                    <button
                      key={who}
                      type="button"
                      className={`chip ${item.eaters.includes(who) ? 'on' : ''}`}
                      aria-pressed={item.eaters.includes(who)}
                      onClick={() => toggleEater(item, who)}
                    >
                      {who === 'me' ? 'Я' : shortName(who)}
                    </button>
                  ))}
                </div>
              </li>
            ))}
          </ul>
          <div className="items-foot">
            <button
              type="button"
              className="secondary"
              onClick={() => update({ items: [...split.items, newItem(everyone)] })}
            >
              + Позиция
            </button>
          </div>
          <p className="muted small">Позиция на нескольких человек делится между ними поровну.</p>
        </div>
      )}

      <label className="service">
        Обслуживание, %
        <input
          type="number"
          inputMode="decimal"
          min="0"
          max="100"
          step="any"
          value={split.tip}
          onChange={(e) => update({ tip: e.target.value })}
          placeholder="Например, 10"
        />
        <span className="muted small">
          Процент добавится к чеку сверху и поделится пропорционально тому, сколько заказал каждый.
        </span>
      </label>

      <div className="split-preview" aria-live="polite">
        {previewError && <p className="error">{previewError}</p>}
        {!previewError && reason && <p className="muted">{reason}</p>}
        {preview && (
          <>
            <p className="split-total">
              Весь чек <b>{money(preview.total)}</b>, ваша доля <b>{money(preview.my_share)}</b>
            </p>
            {preview.service > 0 && (
              <p className="muted small split-service">В чек входит обслуживание: {money(preview.service)}</p>
            )}
            <ul className="split-lines">
              {preview.lines.map((line) => (
                <li key={line.email} className={line.found ? '' : 'missing'}>
                  <span>
                    {line.found ? line.name : line.email}
                    <small>{line.found ? line.email : 'не найден на сайте: попросите друга зарегистрироваться'}</small>
                  </span>
                  <b>{money(line.amount)}</b>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  )
}

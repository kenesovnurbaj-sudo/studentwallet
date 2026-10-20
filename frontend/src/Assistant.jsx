import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'

const HINTS = ['Как мои траты в этом месяце?', 'Где я могу сэкономить?', 'Хватит ли мне бюджета до конца месяца?']

// Плавающий чат с ИИ-ассистентом. История хранится только в памяти страницы.
export default function Assistant() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages, busy, open])

  async function send(content) {
    const value = content.trim()
    if (!value || busy) return
    const next = [...messages, { role: 'user', content: value }]
    setMessages(next)
    setText('')
    setError('')
    setBusy(true)
    try {
      const { reply } = await api.chat(next)
      setMessages([...next, { role: 'assistant', content: reply }])
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  function submit(e) {
    e.preventDefault()
    send(text)
  }

  if (!open) {
    return (
      <button type="button" className="chat-fab" onClick={() => setOpen(true)}>
        Спросить Валли
      </button>
    )
  }

  return (
    <section className="chat" aria-label="Валли, помощник по финансам">
      <header className="chat-head">
        <strong>Валли</strong>
        <span>
          {messages.length > 0 && (
            <button type="button" className="link light" onClick={() => setMessages([])}>
              Очистить
            </button>
          )}
          <button type="button" className="chat-close" onClick={() => setOpen(false)} aria-label="Закрыть чат">
            ×
          </button>
        </span>
      </header>

      <div className="chat-body" aria-live="polite">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p>Привет! Я Валли, помощник по вашим финансам. Я вижу бюджет и последние траты, так что могу подсказать, где можно сэкономить. Спросите что-нибудь:</p>
            {HINTS.map((hint) => (
              <button key={hint} type="button" className="chat-hint" onClick={() => send(hint)} disabled={busy}>
                {hint}
              </button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <p key={i} className={`bubble ${m.role}`}>
            {m.content}
          </p>
        ))}
        {busy && <p className="bubble assistant typing">Валли думает…</p>}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <div ref={endRef} />
      </div>

      <form className="chat-form" onSubmit={submit}>
        <label className="sr-only" htmlFor="chat-input">
          Сообщение
        </label>
        <input
          id="chat-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Напишите вопрос…"
          maxLength={2000}
          autoComplete="off"
        />
        <button className="primary" type="submit" disabled={busy || !text.trim()}>
          Отправить
        </button>
      </form>
    </section>
  )
}

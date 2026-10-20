import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'

const HINTS = ['How is my spending this month?', 'Where can I save money?', 'Will my budget last until the end of the month?']

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
        Ask WALL·E
      </button>
    )
  }

  return (
    <section className="chat" aria-label="WALL·E, your money assistant">
      <header className="chat-head">
        <strong>WALL·E</strong>
        <span>
          {messages.length > 0 && (
            <button type="button" className="link light" onClick={() => setMessages([])}>
              Clear
            </button>
          )}
          <button type="button" className="chat-close" onClick={() => setOpen(false)} aria-label="Close chat">
            ×
          </button>
        </span>
      </header>

      <div className="chat-body" aria-live="polite">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p>Hi! I’m WALL·E, your money helper. I can see your budget and recent spending, so I can point out where you could save. Ask me anything:</p>
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
        {busy && <p className="bubble assistant typing">WALL·E is thinking…</p>}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <div ref={endRef} />
      </div>

      <form className="chat-form" onSubmit={submit}>
        <label className="sr-only" htmlFor="chat-input">
          Message
        </label>
        <input
          id="chat-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type your question…"
          maxLength={2000}
          autoComplete="off"
        />
        <button className="primary" type="submit" disabled={busy || !text.trim()}>
          Send
        </button>
      </form>
    </section>
  )
}

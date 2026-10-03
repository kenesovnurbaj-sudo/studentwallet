import { useState } from 'react'
import { api, setToken } from './api.js'

export default function AuthPage({ onAuth }) {
  const [mode, setMode] = useState('login') // login | register
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const isRegister = mode === 'register'

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      if (isRegister) {
        await api.register({ email, password, full_name: fullName })
      }
      const { access_token } = await api.login({ email, password })
      setToken(access_token)
      onAuth(await api.me())
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  function switchMode() {
    setMode(isRegister ? 'login' : 'register')
    setError('')
  }

  return (
    <main className="auth">
      <div className="auth-intro">
        <h1 className="wordmark">StudentWallet</h1>
        <p>Записывайте траты за десять секунд и всегда знайте, сколько можно потратить сегодня.</p>
      </div>

      <form className="auth-form" onSubmit={submit}>
        <h2>{isRegister ? 'Создать аккаунт' : 'Войти'}</h2>

        {isRegister && (
          <label>
            Имя
            <input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              autoComplete="name"
              placeholder="Как вас зовут"
            />
          </label>
        )}

        <label>
          Email
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            placeholder="name@example.com"
          />
        </label>

        <label>
          Пароль
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={isRegister ? 'new-password' : 'current-password'}
            placeholder="Не короче 8 символов"
          />
        </label>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <button className="primary" type="submit" disabled={busy}>
          {busy ? 'Подождите…' : isRegister ? 'Создать аккаунт' : 'Войти'}
        </button>

        <button className="link" type="button" onClick={switchMode}>
          {isRegister ? 'Уже есть аккаунт? Войти' : 'Нет аккаунта? Зарегистрироваться'}
        </button>
      </form>
    </main>
  )
}

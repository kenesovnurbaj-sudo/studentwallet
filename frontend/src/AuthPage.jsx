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
        <p>Log your spending in ten seconds and always know how much you can spend today.</p>
      </div>

      <form className="auth-form" onSubmit={submit}>
        <h2>{isRegister ? 'Create account' : 'Log in'}</h2>

        {isRegister && (
          <label>
            Name
            <input
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              autoComplete="name"
              placeholder="What should we call you?"
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
          Password
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete={isRegister ? 'new-password' : 'current-password'}
            placeholder="At least 8 characters"
          />
        </label>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <button className="primary" type="submit" disabled={busy}>
          {busy ? 'Please wait…' : isRegister ? 'Create account' : 'Log in'}
        </button>

        <button className="link" type="button" onClick={switchMode}>
          {isRegister ? 'Already have an account? Log in' : 'No account? Sign up'}
        </button>
      </form>
    </main>
  )
}

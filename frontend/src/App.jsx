import { useEffect, useState } from 'react'
import { api, getToken, clearToken, setUnauthorizedHandler } from './api.js'
import AuthPage from './AuthPage.jsx'
import Dashboard from './Dashboard.jsx'

export default function App() {
  const [user, setUser] = useState(null)
  const [checking, setChecking] = useState(Boolean(getToken()))

  useEffect(() => {
    // Если сервер ответил 401 (токен устарел), возвращаем пользователя на экран входа
    setUnauthorizedHandler(() => {
      clearToken()
      setUser(null)
    })

    if (!getToken()) return
    api
      .me()
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setChecking(false))
  }, [])

  const logout = () => {
    clearToken()
    setUser(null)
  }

  if (checking) return <div className="boot">Loading…</div>
  if (!user) return <AuthPage onAuth={setUser} />
  return <Dashboard user={user} onLogout={logout} />
}

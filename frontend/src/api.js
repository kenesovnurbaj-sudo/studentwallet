// Все обращения к backend собраны здесь. Адреса совпадают с Swagger (/docs).

const TOKEN_KEY = 'studentwallet_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (token) => localStorage.setItem(TOKEN_KEY, token)
export const clearToken = () => localStorage.removeItem(TOKEN_KEY)

let onUnauthorized = null
export const setUnauthorizedHandler = (fn) => {
  onUnauthorized = fn
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

const KNOWN_ERRORS = {
  'Invalid email or password': 'Неверный email или пароль',
  'Email already registered': 'Этот email уже зарегистрирован. Попробуйте войти',
  'User is blocked': 'Аккаунт заблокирован администратором',
  'Unknown category': 'Выбрана неизвестная категория',
  'Not authenticated': 'Войдите в аккаунт',
  'Invalid or expired token': 'Сессия закончилась. Войдите снова',
  'Could not read statement': 'Не удалось прочитать выписку. Нужен PDF Kaspi Gold на английском языке',
  'File too large': 'Файл слишком большой (максимум 5 МБ)',
  'AI unavailable': 'ИИ-ассистент сейчас недоступен. Попробуйте позже',
}

function errorText(data, status) {
  if (status === 422) return 'Проверьте поля: пароль не короче 8 символов, сумма больше нуля'
  const detail = data && data.detail
  if (typeof detail === 'string') return KNOWN_ERRORS[detail] || detail
  if (status >= 500) return 'Ошибка сервера. Попробуйте ещё раз'
  return 'Не удалось выполнить запрос'
}

async function request(path, { method = 'GET', body, auth = true } = {}) {
  const headers = {}
  const token = getToken()
  const isForm = body instanceof FormData // браузер сам выставит Content-Type с boundary
  if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json'
  if (auth && token) headers.Authorization = `Bearer ${token}`

  let res
  try {
    res = await fetch(`/api${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'Нет связи с сервером. Проверьте, что backend запущен')
  }

  if (res.status === 204) return null

  let data = null
  try {
    data = await res.json()
  } catch {
    // пустой или не-JSON ответ
  }

  if (!res.ok) {
    if (res.status === 401 && auth && token && onUnauthorized) onUnauthorized()
    throw new ApiError(res.status, errorText(data, res.status))
  }
  return data
}

export const api = {
  register: (data) => request('/auth/register', { method: 'POST', body: data, auth: false }),
  login: (data) => request('/auth/login', { method: 'POST', body: data, auth: false }),
  me: () => request('/auth/me'),
  categories: () => request('/categories'),
  expenses: (categoryId) =>
    request(`/expenses${categoryId ? `?category_id=${encodeURIComponent(categoryId)}` : ''}`),
  addExpense: (data) => request('/expenses', { method: 'POST', body: data }),
  deleteExpense: (id) => request(`/expenses/${id}`, { method: 'DELETE' }),
  setBudget: (data) => request('/budgets', { method: 'PUT', body: data }),
  importKaspi: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('/import/kaspi', { method: 'POST', body: form })
  },
  importCommit: (rows) => request('/import/commit', { method: 'POST', body: { rows } }),
  chat: (messages) => request('/assistant/chat', { method: 'POST', body: { messages } }),
  summary: (month) => request(`/budget/summary?month=${encodeURIComponent(month)}`),
}

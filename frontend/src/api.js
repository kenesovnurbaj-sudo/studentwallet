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
  'Invalid email or password': 'Wrong email or password',
  'Email already registered': 'This email is already registered. Try logging in',
  'User is blocked': 'Your account was blocked by an administrator',
  'Unknown category': 'Unknown category selected',
  'Not authenticated': 'Please log in',
  'Invalid or expired token': 'Your session has expired. Please log in again',
  'Could not read statement': 'Could not read the statement. A Kaspi Gold PDF in English is required',
  'Could not find an amount': 'Could not find an amount. Include a number, for example “lunch 2500”',
  'No budget set for this month': 'Set a monthly budget first',
  'File too large': 'File is too large (5 MB max)',
  'AI unavailable': 'WALL·E is unavailable right now. Please try again later',
}

function errorText(data, status) {
  if (status === 422) return 'Check the fields: password must be at least 8 characters, amount must be greater than zero'
  const detail = data && data.detail
  if (typeof detail === 'string') return KNOWN_ERRORS[detail] || detail
  if (status >= 500) return 'Server error. Please try again'
  return 'The request failed'
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
    throw new ApiError(0, 'Cannot reach the server. Check that the backend is running')
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
  bulkCategory: (ids, categoryId) =>
    request('/expenses/bulk-category', { method: 'POST', body: { ids, category_id: categoryId } }),
  deleteExpense: (id) => request(`/expenses/${id}`, { method: 'DELETE' }),
  setBudget: (data) => request('/budgets', { method: 'PUT', body: data }),
  budgetSplit: (month) => request(`/ai/budget-split?month=${encodeURIComponent(month)}`),
  saveBudgetSplit: (month, items) => request('/budgets/split', { method: 'PUT', body: { month, items } }),
  parseExpense: (text) => request('/ai/parse-expense', { method: 'POST', body: { text } }),
  importKaspi: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('/import/kaspi', { method: 'POST', body: form })
  },
  importCommit: (rows) => request('/import/commit', { method: 'POST', body: { rows } }),
  chat: (messages) => request('/assistant/chat', { method: 'POST', body: { messages } }),
  categoryBalances: (month) => request(`/budget/categories?month=${encodeURIComponent(month)}`),
  forecast: (month) => request(`/budget/forecast?month=${encodeURIComponent(month)}`),
  summary: (month) => request(`/budget/summary?month=${encodeURIComponent(month)}`),
}

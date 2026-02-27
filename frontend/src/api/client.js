import axios from 'axios'

// Ensure the API base URL always ends with /api
let _baseUrl = import.meta.env.VITE_API_BASE_URL || '/api'
if (_baseUrl !== '/api' && !_baseUrl.endsWith('/api')) {
  _baseUrl = _baseUrl.replace(/\/+$/, '') + '/api'
}
const API_BASE_URL = _baseUrl

const client = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000, // 30s — Render free-tier can be slow on first request
})

// ── In-memory token store (NOT localStorage) ──────────────────────────────
// Tokens are held in JS memory only. This means:
// - XSS cannot read tokens from localStorage/sessionStorage
// - Tokens survive page navigation but NOT full tab close/refresh
// - On page refresh, the refresh token in sessionStorage re-authenticates
//
// Trade-off: user must re-login after closing the tab. This is the secure default.
let _accessToken = null

export function setAccessToken(token) {
  _accessToken = token
}

export function getAccessToken() {
  return _accessToken
}

export function clearTokens() {
  _accessToken = null
  sessionStorage.removeItem('flow_refresh_token')
  // Clear any legacy localStorage tokens from before this migration
  localStorage.removeItem('flow_token')
  localStorage.removeItem('flow_refresh_token')
}

export function setRefreshToken(token) {
  // sessionStorage is scoped to the tab and not accessible cross-tab.
  // It's cleared when the tab closes, which is safer than localStorage.
  sessionStorage.setItem('flow_refresh_token', token)
}

export function getRefreshToken() {
  return sessionStorage.getItem('flow_refresh_token')
}

// ── Attach access token to every request ──────────────────────────────────
client.interceptors.request.use(
  (config) => {
    if (_accessToken) {
      config.headers.Authorization = `Bearer ${_accessToken}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// ── Flag to avoid multiple concurrent refresh attempts ────────────────────
let isRefreshing = false
let refreshSubscribers = []

function subscribeTokenRefresh(cb) {
  refreshSubscribers.push(cb)
}
function onTokenRefreshed(newToken) {
  refreshSubscribers.forEach(cb => cb(newToken))
  refreshSubscribers = []
}

// ── Response interceptor: auto-refresh on 401 ────────────────────────────
client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // If 401 and not the refresh/login route itself, try refresh
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/login') &&
      !originalRequest.url?.includes('/auth/refresh')
    ) {
      const refreshToken = getRefreshToken()

      if (refreshToken) {
        if (isRefreshing) {
          // Queue this request until the refresh completes
          return new Promise((resolve) => {
            subscribeTokenRefresh((newToken) => {
              originalRequest.headers.Authorization = `Bearer ${newToken}`
              resolve(client(originalRequest))
            })
          })
        }

        originalRequest._retry = true
        isRefreshing = true

        try {
          const res = await axios.post(`${API_BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          })
          const newAccess = res.data.access_token
          const newRefresh = res.data.refresh_token

          setAccessToken(newAccess)
          if (newRefresh) setRefreshToken(newRefresh)

          originalRequest.headers.Authorization = `Bearer ${newAccess}`
          onTokenRefreshed(newAccess)
          return client(originalRequest)
        } catch (refreshErr) {
          // Refresh failed — full logout
          clearTokens()
          localStorage.removeItem('flow_username')
          localStorage.removeItem('flow_hunter_name')
          window.location.href = '/login'
          return Promise.reject(refreshErr)
        } finally {
          isRefreshing = false
        }
      }

      // No refresh token at all — logout
      clearTokens()
      localStorage.removeItem('flow_username')
      localStorage.removeItem('flow_hunter_name')
      window.location.href = '/login'
    }

    return Promise.reject(error)
  }
)

export default client

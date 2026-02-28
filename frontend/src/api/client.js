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
  localStorage.removeItem('flow_token')
  localStorage.removeItem('flow_refresh_token')
}

export function setRefreshToken(token) {
  sessionStorage.setItem('flow_refresh_token', token)
}

export function getRefreshToken() {
  return sessionStorage.getItem('flow_refresh_token')
}

// ── Pluggable force-logout handler ────────────────────────────────────────
// AuthContext registers a callback so the interceptor can trigger a React-aware
// logout instead of doing window.location.href (which destroys React state).
let _onForceLogout = null

export function setForceLogoutHandler(fn) {
  _onForceLogout = fn
}

function forceLogout() {
  clearTokens()
  localStorage.removeItem('flow_username')
  localStorage.removeItem('flow_hunter_name')
  if (_onForceLogout) {
    _onForceLogout()
  } else if (window.location.pathname !== '/login') {
    // Fallback only if no React handler registered AND not already on /login
    window.location.href = '/login'
  }
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

// ── Token refresh queue ───────────────────────────────────────────────────
let isRefreshing = false
let refreshSubscribers = []

function subscribeTokenRefresh(cb) {
  refreshSubscribers.push(cb)
}

function onTokenRefreshed(newToken) {
  refreshSubscribers.forEach(cb => cb.resolve(newToken))
  refreshSubscribers = []
}

function onRefreshFailed(err) {
  refreshSubscribers.forEach(cb => cb.reject(err))
  refreshSubscribers = []
}

// ── Response interceptor: auto-refresh on 401 ────────────────────────────
client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/login') &&
      !originalRequest.url?.includes('/auth/register') &&
      !originalRequest.url?.includes('/auth/refresh')
    ) {
      const refreshToken = getRefreshToken()

      if (refreshToken) {
        if (isRefreshing) {
          // Queue this request — resolve or reject when refresh settles
          return new Promise((resolve, reject) => {
            subscribeTokenRefresh({
              resolve: (newToken) => {
                originalRequest.headers.Authorization = `Bearer ${newToken}`
                resolve(client(originalRequest))
              },
              reject: (err) => reject(err),
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
          onRefreshFailed(refreshErr)
          forceLogout()
          return Promise.reject(refreshErr)
        } finally {
          isRefreshing = false
        }
      }

      // No refresh token at all
      forceLogout()
    }

    return Promise.reject(error)
  }
)

export default client

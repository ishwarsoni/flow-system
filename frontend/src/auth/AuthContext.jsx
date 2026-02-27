import React, { createContext, useState, useEffect } from 'react'
import {
  setAccessToken, getAccessToken, clearTokens,
  setRefreshToken, getRefreshToken,
} from '../api/client'

export const AuthContext = createContext(null)

/**
 * Safely decode a JWT payload. Returns null on any failure.
 */
function safeDecodeJWT(token) {
  try {
    const base64 = token.split('.')[1]
    return JSON.parse(atob(base64))
  } catch {
    return null
  }
}

/**
 * Check if a JWT is expired (with 30s buffer).
 */
function isTokenExpired(token) {
  const payload = safeDecodeJWT(token)
  if (!payload?.exp) return true
  return Date.now() / 1000 > payload.exp - 30
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(null)
  const [loading, setLoading] = useState(true)

  // ── Restore session ───────────────────────────────────────────────────
  // Access token is in-memory (lost on refresh), but we attempt to silently
  // re-authenticate via the refresh token stored in sessionStorage.
  useEffect(() => {
    async function restoreSession() {
      try {
        // Check if we still have an in-memory access token (unlikely after refresh)
        const memToken = getAccessToken()
        if (memToken && !isTokenExpired(memToken)) {
          setToken(memToken)
          const decoded = safeDecodeJWT(memToken)
        const savedHunterName = localStorage.getItem('flow_hunter_name')
          if (decoded) {
            setUser({ ...decoded, hunter_name: savedHunterName || decoded?.sub || 'Hunter' })
          }
          setLoading(false)
          return
        }

        // Try silent refresh using sessionStorage refresh token
        const refreshToken = getRefreshToken()
        if (refreshToken) {
          try {
            const { default: axios } = await import('axios')
            const res = await axios.post('/api/auth/refresh', {
              refresh_token: refreshToken,
            })
            storeSession(res.data)
          } catch {
            // Refresh token invalid/expired — clear everything
            clearAllStorage()
          }
        } else {
          // Also try migrating from legacy localStorage if present
          const legacyToken = localStorage.getItem('flow_token')
          const legacyRefresh = localStorage.getItem('flow_refresh_token')
          if (legacyRefresh) {
            try {
              const { default: axios } = await import('axios')
              const res = await axios.post('/api/auth/refresh', {
                refresh_token: legacyRefresh,
              })
              // Clear legacy storage
              localStorage.removeItem('flow_token')
              localStorage.removeItem('flow_refresh_token')
              storeSession(res.data)
            } catch {
              clearAllStorage()
            }
          } else if (legacyToken) {
            // Legacy access-only token — just clear it
            localStorage.removeItem('flow_token')
          }
        }
      } catch (err) {
        console.error('Session restore failed:', err)
        clearAllStorage()
      }
      setLoading(false)
    }
    restoreSession()
  }, [])

  function clearAllStorage() {
    clearTokens()
    localStorage.removeItem('flow_hunter_name')
    setToken(null)
    setUser(null)
  }

  function storeSession(data) {
    const accessToken = data.access_token || data.token
    const refreshTokenValue = data.refresh_token
    if (!accessToken) throw new Error('No token received from server')

    setAccessToken(accessToken)
    if (refreshTokenValue) setRefreshToken(refreshTokenValue)

    const hunterName = data.user?.hunter_name
    if (hunterName) localStorage.setItem('flow_hunter_name', hunterName)

    setToken(accessToken)
    const decoded = safeDecodeJWT(accessToken)
    setUser({
      ...(decoded || {}),
      hunter_name: hunterName || decoded?.sub || 'Hunter',
    })
  }

  // ── Login ─────────────────────────────────────────────────────────────
  const login = async (email, password) => {
    const { authAPI } = await import('../api')
    const response = await authAPI.login({ email, password })
    storeSession(response.data)
    return response.data
  }

  // ── Register + auto-login ─────────────────────────────────────────────
  const register = async (email, password, hunter_name) => {
    const { authAPI } = await import('../api')
    await authAPI.register({ email, password, hunter_name: hunter_name || 'Hunter' })
    const loginResponse = await authAPI.login({ email, password })
    storeSession(loginResponse.data)
    return loginResponse.data
  }

  // ── Logout ────────────────────────────────────────────────────────────
  const logout = async () => {
    // Server-side token revocation (best effort)
    try {
      const refreshToken = getRefreshToken()
      if (refreshToken) {
        const { default: client } = await import('../api/client')
        await client.post('/auth/logout', { refresh_token: refreshToken })
      }
    } catch {
      // Continue even if server call fails
    }
    clearAllStorage()
  }

  const value = {
    user,
    token,
    loading,
    isAuthenticated: Boolean(token),
    login,
    register,
    logout,
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}



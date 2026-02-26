import React, { createContext, useState, useEffect } from 'react'

export const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    try {
      const savedToken = localStorage.getItem('flow_token')
      const savedUsername = localStorage.getItem('flow_username')
      const savedHunterName = localStorage.getItem('flow_hunter_name')
      if (savedToken) {
        setToken(savedToken)
        const decoded = JSON.parse(atob(savedToken.split('.')[1]))
        setUser({ ...decoded, username: savedUsername || undefined, hunter_name: savedHunterName || savedUsername || undefined })
      }
    } catch (err) {
      console.error('Token decode failed:', err)
      localStorage.removeItem('flow_token')
      localStorage.removeItem('flow_username')
    }
    setLoading(false)
  }, [])

  const login = async (email, password) => {
    const { authAPI } = await import('../api')
    const response = await authAPI.login({ email, password })
    const newToken = response.data.access_token || response.data.token
    if (!newToken) {
      throw new Error('No token received from server')
    }
    localStorage.setItem('flow_token', newToken)
    const username = response.data.user?.username
    const hunterName = response.data.user?.hunter_name
    if (username) localStorage.setItem('flow_username', username)
    if (hunterName) localStorage.setItem('flow_hunter_name', hunterName)
    setToken(newToken)
    try {
      const decoded = JSON.parse(atob(newToken.split('.')[1]))
      setUser({ ...decoded, username: username || email, hunter_name: hunterName || username || email })
    } catch (err) {
      setUser({ sub: email, username: username || email, hunter_name: hunterName || username || email })
    }
    return response.data
  }

  const register = async (username, email, password, hunter_name) => {
    const { authAPI } = await import('../api')
    // Step 1: Register the user
    await authAPI.register({ username, email, password, hunter_name: hunter_name || 'Hunter' })
    // Step 2: Registration succeeded — now auto-login to get a token
    const loginResponse = await authAPI.login({ email, password })
    const newToken = loginResponse.data.access_token || loginResponse.data.token
    if (!newToken) {
      throw new Error('No token received from server')
    }
    localStorage.setItem('flow_token', newToken)
    const registeredUsername = loginResponse.data.user?.username || username
    const registeredHunterName = loginResponse.data.user?.hunter_name || hunter_name
    if (registeredUsername) localStorage.setItem('flow_username', registeredUsername)
    if (registeredHunterName) localStorage.setItem('flow_hunter_name', registeredHunterName)
    setToken(newToken)
    try {
      const decoded = JSON.parse(atob(newToken.split('.')[1]))
      setUser({ ...decoded, username: registeredUsername || email, hunter_name: registeredHunterName || registeredUsername || email })
    } catch (err) {
      setUser({ sub: email, username: registeredUsername || email, hunter_name: registeredHunterName || registeredUsername || email })
    }
    return loginResponse.data
  }

  const logout = () => {
    localStorage.removeItem('flow_token')
    localStorage.removeItem('flow_username')
    localStorage.removeItem('flow_hunter_name')
    setToken(null)
    setUser(null)
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



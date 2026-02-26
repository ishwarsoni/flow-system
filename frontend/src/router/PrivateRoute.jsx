import React from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export function PrivateRoute() {
  const { isAuthenticated, loading } = useAuth()

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        backgroundColor: '#f9fafb',
        fontFamily: 'sans-serif',
      }}>
        <p style={{ color: '#6b7280', fontSize: '16px' }}>Loading...</p>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}

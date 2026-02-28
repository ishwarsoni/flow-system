import React from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export function PrivateRoute() {
  const { isAuthenticated, loading } = useAuth()

  if (loading) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        backgroundColor: '#02050f',
        gap: 12,
      }}>
        <div style={{
          width: 28, height: 28,
          border: '2px solid rgba(0,212,255,0.2)',
          borderTop: '2px solid #00d4ff',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite',
        }} />
        <span style={{
          fontFamily: "'Orbitron', monospace",
          fontSize: 10,
          letterSpacing: 3,
          color: 'rgba(0,212,255,0.4)',
        }}>
          RESTORING SESSION...
        </span>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}

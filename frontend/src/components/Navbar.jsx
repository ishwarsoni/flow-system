import React from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export default function Navbar() {
  const { logout, user } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <nav style={{
      backgroundColor: '#fff',
      borderBottom: '2px solid #e5e7eb',
      padding: '16px 24px',
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center',
    }}>
      <div style={{
        fontSize: '24px',
        fontWeight: 'bold',
        color: '#3b82f6',
        letterSpacing: '2px',
      }}>
        FLOW
      </div>
      <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
        {user && (
          <span style={{ color: '#6b7280', fontSize: '14px' }}>
            {user.sub || 'User'}
          </span>
        )}
        <button
          onClick={handleLogout}
          style={{
            padding: '8px 16px',
            backgroundColor: '#ef4444',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            fontSize: '14px',
            fontWeight: '500',
          }}
        >
          Logout
        </button>
      </div>
    </nav>
  )
}

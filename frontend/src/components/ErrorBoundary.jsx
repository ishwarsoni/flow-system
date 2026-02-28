import React from 'react'

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, info) {
    console.error('ErrorBoundary caught:', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#0a0a0f',
          padding: '20px',
          fontFamily: "'Orbitron', monospace",
        }}>
          <div style={{
            textAlign: 'center',
            maxWidth: '500px',
            backgroundColor: 'rgba(4,12,30,0.9)',
            padding: '32px',
            borderRadius: '4px',
            border: '1px solid rgba(255,32,64,0.35)',
            boxShadow: '0 0 24px rgba(255,32,64,0.15)',
          }}>
            <h1 style={{ color: '#ff2040', fontSize: '18px', marginBottom: '12px', letterSpacing: '2px' }}>
              [ SYSTEM ERROR ]
            </h1>
            <p style={{ color: '#b8d8f0', marginBottom: '16px', fontSize: '13px', fontFamily: 'monospace' }}>
              {this.state.error?.message || 'An unexpected error occurred'}
            </p>
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null })
                window.location.href = '/'
              }}
              style={{
                padding: '10px 24px',
                backgroundColor: 'rgba(0,212,255,0.08)',
                color: '#00d4ff',
                border: '1px solid rgba(0,212,255,0.4)',
                borderRadius: '2px',
                cursor: 'pointer',
                fontSize: '12px',
                fontFamily: "'Orbitron', monospace",
                letterSpacing: '2px',
              }}
            >
              [ RELOAD ]
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

export default ErrorBoundary

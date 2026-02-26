import React, { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export default function LoginPage() {
  const navigate = useNavigate()
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      setError(err.response?.data?.detail || 'Authentication failed.')
      setLoading(false)
    }
  }

  return (
    <div style={s.page}>
      <div style={s.scanline} />

      <div style={s.panel}>
        <div style={s.corner} data-corner="tl" />
        <div style={s.corner} data-corner="tr" />
        <div style={s.corner} data-corner="bl" />
        <div style={s.corner} data-corner="br" />

        <div style={s.header}>
          <div style={s.systemTag}>[ SYSTEM ]</div>
          <div style={s.title}>AWAKENING SEQUENCE</div>
          <div style={s.subtitle}>HUNTER AUTHENTICATION REQUIRED</div>
        </div>

        {error && (
          <div style={s.errBox}>
            <span style={s.errTag}>[ ERROR ]</span>
            <span style={s.errMsg}>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} style={s.form}>
          <div style={s.fieldGroup}>
            <label style={s.label}>HUNTER ID (EMAIL)</label>
            <input
              type="email" value={email} onChange={e => setEmail(e.target.value)}
              required placeholder="hunter@system.net" style={s.input}
            />
          </div>

          <div style={s.fieldGroup}>
            <label style={s.label}>PASSPHRASE</label>
            <div style={s.pwWrap}>
              <input
                type={showPw ? 'text' : 'password'} value={password}
                onChange={e => setPassword(e.target.value)}
                required placeholder="" style={{ ...s.input, paddingRight: 44 }}
              />
              <button type="button" onClick={() => setShowPw(!showPw)} style={s.pwToggle}>
                {showPw ? '' : ''}
              </button>
            </div>
          </div>

          <button type="submit" disabled={loading} style={{ ...s.submitBtn, ...(loading ? s.submitDisabled : {}) }}>
            {loading ? (
              <span style={s.loadingRow}><span style={s.spinner} /> AUTHENTICATING...</span>
            ) : '[ ENTER THE SYSTEM ]'}
          </button>
        </form>

        <div style={s.footer}>
          <span style={s.footerText}>NOT REGISTERED?</span>
          <Link to="/register" style={s.footerLink}>[ AWAKEN NOW ]</Link>
        </div>
      </div>

      <div style={s.brandWatermark}>FLOW SYSTEM v1.0</div>
    </div>
  )
}

const s = {
  page: {
    minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
    background: '#02050f', position: 'relative', overflow: 'hidden', padding: 20,
  },
  scanline: {
    position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 0,
    background: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,212,255,0.015) 2px, rgba(0,212,255,0.015) 4px)',
  },
  panel: {
    position: 'relative', zIndex: 1, width: '100%', maxWidth: 440,
    background: 'rgba(4,12,30,0.96)', border: '1px solid rgba(0,212,255,0.35)',
    padding: '40px 40px 32px', boxShadow: '0 0 60px rgba(0,212,255,0.08), inset 0 0 40px rgba(0,212,255,0.02)',
  },
  corner: { display: 'none' },
  header: { textAlign: 'center', marginBottom: 32 },
  systemTag: { fontFamily: "'Orbitron',monospace", fontSize: 10, color: 'rgba(0,212,255,0.45)', letterSpacing: 6, marginBottom: 12 },
  title: { fontFamily: "'Orbitron',monospace", fontSize: 22, fontWeight: 900, color: '#e8f4ff', letterSpacing: 3, marginBottom: 6 },
  subtitle: { fontFamily: "'Orbitron',monospace", fontSize: 9, color: 'rgba(0,212,255,0.4)', letterSpacing: 3 },
  errBox: { padding: '10px 14px', background: 'rgba(255,32,64,0.08)', border: '1px solid rgba(255,32,64,0.3)', marginBottom: 20, display: 'flex', gap: 10, alignItems: 'flex-start', borderRadius: 1 },
  errTag: { fontFamily: "'Orbitron',monospace", fontSize: 9, color: '#ff2040', letterSpacing: 2, whiteSpace: 'nowrap', marginTop: 1 },
  errMsg: { fontSize: 12, color: '#ff8090', lineHeight: 1.4 },
  form: { display: 'flex', flexDirection: 'column', gap: 18 },
  fieldGroup: { display: 'flex', flexDirection: 'column', gap: 6 },
  label: { fontFamily: "'Orbitron',monospace", fontSize: 9, color: 'rgba(0,212,255,0.5)', letterSpacing: 2.5 },
  input: {
    padding: '11px 14px', background: 'rgba(0,212,255,0.03)',
    border: '1px solid rgba(0,212,255,0.2)', color: '#e8f4ff', fontSize: 14,
    outline: 'none', borderRadius: 1, fontFamily: 'inherit', transition: 'border-color 0.2s',
  },
  pwWrap: { position: 'relative' },
  pwToggle: { position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'rgba(0,212,255,0.4)', cursor: 'pointer', fontSize: 16, padding: 2 },
  submitBtn: {
    padding: '13px 0', marginTop: 8,
    background: 'rgba(0,212,255,0.07)', border: '1px solid rgba(0,212,255,0.5)',
    color: '#00d4ff', fontFamily: "'Orbitron',monospace", fontSize: 12, letterSpacing: 3,
    cursor: 'pointer', transition: 'all 0.2s', boxShadow: '0 0 20px rgba(0,212,255,0.1)',
  },
  submitDisabled: { opacity: 0.5, cursor: 'not-allowed' },
  loadingRow: { display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 },
  spinner: { display: 'inline-block', width: 14, height: 14, border: '2px solid rgba(0,212,255,0.2)', borderTop: '2px solid #00d4ff', borderRadius: '50%', animation: 'spin 0.8s linear infinite' },
  footer: { display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, marginTop: 24 },
  footerText: { fontFamily: "'Orbitron',monospace", fontSize: 9, color: 'rgba(0,212,255,0.3)', letterSpacing: 2 },
  footerLink: { fontFamily: "'Orbitron',monospace", fontSize: 9, color: '#00d4ff', letterSpacing: 2, textDecoration: 'none' },
  brandWatermark: { position: 'fixed', bottom: 20, right: 20, fontFamily: "'Orbitron',monospace", fontSize: 9, color: 'rgba(0,212,255,0.15)', letterSpacing: 3 },
}

import React, { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export default function RegisterPage() {
  const navigate = useNavigate()
  const { register } = useAuth()
  const [form, setForm] = useState({ hunter_name: '', email: '', password: '', confirmPassword: '' })
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const update = field => e => setForm(prev => ({ ...prev, [field]: e.target.value }))

  const checks = [
    { label: 'MIN 8 CHARACTERS', ok: form.password.length >= 8 },
    { label: 'CONTAINS UPPERCASE', ok: /[A-Z]/.test(form.password) },
    { label: 'CONTAINS LOWERCASE', ok: /[a-z]/.test(form.password) },
    { label: 'CONTAINS DIGIT', ok: /\d/.test(form.password) },
    { label: 'CONTAINS SPECIAL (!@#$...)', ok: /[!@#$%^&*()\-_=+\[\]{}|;:'",.<>?\/`~]/.test(form.password) },
    { label: 'PASSWORDS MATCH', ok: form.password.length > 0 && form.password === form.confirmPassword },
  ]
  const hunterNameOk = form.hunter_name.length >= 3 && form.hunter_name.length <= 20 && /^[a-zA-Z]+$/.test(form.hunter_name)
  const allOk = checks.every(c => c.ok) && form.email.includes('@') && hunterNameOk

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!allOk) return
    setError('')
    setLoading(true)
    try {
      await register(form.email, form.password, form.hunter_name)
      navigate('/dashboard', { replace: true })
    } catch (err) {
      if (!err.response) {
        // Network error — CORS blocked or server unreachable
        setError('Cannot reach the server. Please check your connection and try again.')
      } else {
        const detail = err.response?.data?.detail
        if (Array.isArray(detail)) {
          // Pydantic 422 validation errors — extract readable messages
          const msgs = detail.map(d => d.msg || d.message || JSON.stringify(d)).join('; ')
          setError(msgs)
        } else {
          setError(typeof detail === 'string' ? detail : 'Registration failed.')
        }
      }
      setLoading(false)
    }
  }

  return (
    <div style={s.page}>
      <div style={s.scanline} />
      <div style={s.panel}>
        <div style={s.header}>
          <div style={s.systemTag}>[ SYSTEM ]</div>
          <div style={s.title}>HUNTER REGISTRATION</div>
          <div style={s.subtitle}>BEGIN YOUR AWAKENING SEQUENCE</div>
        </div>

        {error && (
          <div style={s.errBox}>
            <span style={s.errTag}>[ ERROR ]</span>
            <span style={s.errMsg}>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} style={s.form} autoComplete="on">
          <div style={s.fieldGroup}>
            <label style={s.label}>HUNTER NAME</label>
            <input type="text" name="name" autoComplete="name" value={form.hunter_name} onChange={update('hunter_name')} required placeholder="Jinwoo" style={s.input} minLength={3} maxLength={20} />
            {form.hunter_name.length > 0 && !/^[a-zA-Z]+$/.test(form.hunter_name) && (
              <span style={{ fontSize: 10, color: '#ff2040', fontFamily: "'Orbitron',monospace", letterSpacing: 1 }}>LETTERS ONLY (A-Z)</span>
            )}
          </div>
          <div style={s.fieldGroup}>
            <label style={s.label}>HUNTER ID (EMAIL)</label>
            <input type="email" name="email" autoComplete="email" value={form.email} onChange={update('email')} required placeholder="hunter@system.net" style={s.input} />
          </div>
          <div style={s.fieldGroup}>
            <label style={s.label}>PASSPHRASE</label>
            <div style={s.pwWrap}>
              <input type={showPw ? 'text' : 'password'} name="password" autoComplete="new-password" value={form.password} onChange={update('password')} required placeholder="" style={{ ...s.input, paddingRight: 44 }} />
              <button type="button" onClick={() => setShowPw(!showPw)} style={s.pwToggle}>{showPw ? '' : ''}</button>
            </div>
          </div>
          <div style={s.fieldGroup}>
            <label style={s.label}>CONFIRM PASSPHRASE</label>
            <input type="password" name="confirm-password" autoComplete="new-password" value={form.confirmPassword} onChange={update('confirmPassword')} required placeholder="" style={s.input} />
          </div>

          {form.password.length > 0 && (
            <div style={s.checkList}>
              {checks.map(c => (
                <div key={c.label} style={s.checkItem}>
                  <span style={{ ...s.checkDot, color: c.ok ? '#00ff88' : 'rgba(0,212,255,0.2)' }}>{c.ok ? '' : ''}</span>
                  <span style={{ ...s.checkLabel, color: c.ok ? '#00ff88' : 'rgba(0,212,255,0.3)' }}>{c.label}</span>
                </div>
              ))}
            </div>
          )}

          <button type="submit" disabled={loading || !allOk} style={{ ...s.submitBtn, ...(loading || !allOk ? s.submitDisabled : {}) }}>
            {loading ? (
              <span style={s.loadingRow}><span style={s.spinner} /> REGISTERING...</span>
            ) : '[ AWAKEN NOW ]'}
          </button>
        </form>

        <div style={s.footer}>
          <span style={s.footerText}>ALREADY A HUNTER?</span>
          <Link to="/login" style={s.footerLink}>[ SIGN IN ]</Link>
        </div>
      </div>
      <div style={s.brandWatermark}>FLOW SYSTEM v1.0</div>
    </div>
  )
}

const s = {
  page: { minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#02050f', position: 'relative', overflow: 'hidden', padding: 20 },
  scanline: { position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 0, background: 'repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,212,255,0.015) 2px,rgba(0,212,255,0.015) 4px)' },
  panel: { position: 'relative', zIndex: 1, width: '100%', maxWidth: 440, background: 'rgba(4,12,30,0.96)', border: '1px solid rgba(0,212,255,0.35)', padding: '40px 40px 32px', boxShadow: '0 0 60px rgba(0,212,255,0.08)' },
  header: { textAlign: 'center', marginBottom: 28 },
  systemTag: { fontFamily: "'Orbitron',monospace", fontSize: 10, color: 'rgba(0,212,255,0.45)', letterSpacing: 6, marginBottom: 12 },
  title: { fontFamily: "'Orbitron',monospace", fontSize: 20, fontWeight: 900, color: '#e8f4ff', letterSpacing: 3, marginBottom: 6 },
  subtitle: { fontFamily: "'Orbitron',monospace", fontSize: 9, color: 'rgba(0,212,255,0.4)', letterSpacing: 3 },
  errBox: { padding: '10px 14px', background: 'rgba(255,32,64,0.08)', border: '1px solid rgba(255,32,64,0.3)', marginBottom: 20, display: 'flex', gap: 10, alignItems: 'flex-start' },
  errTag: { fontFamily: "'Orbitron',monospace", fontSize: 9, color: '#ff2040', letterSpacing: 2, whiteSpace: 'nowrap' },
  errMsg: { fontSize: 12, color: '#ff8090', lineHeight: 1.4 },
  form: { display: 'flex', flexDirection: 'column', gap: 14 },
  fieldGroup: { display: 'flex', flexDirection: 'column', gap: 5 },
  label: { fontFamily: "'Orbitron',monospace", fontSize: 9, color: 'rgba(0,212,255,0.5)', letterSpacing: 2.5 },
  input: { padding: '10px 14px', background: 'rgba(0,212,255,0.03)', border: '1px solid rgba(0,212,255,0.2)', color: '#e8f4ff', fontSize: 14, outline: 'none', fontFamily: 'inherit' },
  pwWrap: { position: 'relative' },
  pwToggle: { position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'rgba(0,212,255,0.4)', cursor: 'pointer', fontSize: 16 },
  checkList: { display: 'flex', flexDirection: 'column', gap: 5, padding: '10px 14px', background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(0,212,255,0.08)' },
  checkItem: { display: 'flex', alignItems: 'center', gap: 10 },
  checkDot: { fontSize: 10 },
  checkLabel: { fontFamily: "'Orbitron',monospace", fontSize: 9, letterSpacing: 1.5 },
  submitBtn: { padding: '13px 0', marginTop: 8, background: 'rgba(0,212,255,0.07)', border: '1px solid rgba(0,212,255,0.5)', color: '#00d4ff', fontFamily: "'Orbitron',monospace", fontSize: 12, letterSpacing: 3, cursor: 'pointer' },
  submitDisabled: { opacity: 0.4, cursor: 'not-allowed' },
  loadingRow: { display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 },
  spinner: { display: 'inline-block', width: 14, height: 14, border: '2px solid rgba(0,212,255,0.2)', borderTop: '2px solid #00d4ff', borderRadius: '50%', animation: 'spin 0.8s linear infinite' },
  footer: { display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, marginTop: 24 },
  footerText: { fontFamily: "'Orbitron',monospace", fontSize: 9, color: 'rgba(0,212,255,0.3)', letterSpacing: 2 },
  footerLink: { fontFamily: "'Orbitron',monospace", fontSize: 9, color: '#00d4ff', letterSpacing: 2, textDecoration: 'none' },
  brandWatermark: { position: 'fixed', bottom: 20, right: 20, fontFamily: "'Orbitron',monospace", fontSize: 9, color: 'rgba(0,212,255,0.15)', letterSpacing: 3 },
}

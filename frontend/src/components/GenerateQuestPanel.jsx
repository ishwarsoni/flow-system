/**
 * GenerateQuestPanel.jsx
 *
 * Template-based quest generation panel.
 * User picks domain + difficulty → calls POST /quests/generate.
 * This is the PRIMARY way to create quests. "No quest may exist without a template."
 */
import React, { useState, useCallback } from 'react'
import { questsAPI } from '../api'

const DOMAINS = [
  { key: 'mind',     icon: '◈', color: '#00d4ff', label: 'MIND' },
  { key: 'body',     icon: '⚡', color: '#ff2040', label: 'BODY' },
  { key: 'core',     icon: '◉', color: '#00ff88', label: 'CORE' },
  { key: 'control',  icon: '◆', color: '#7c3aed', label: 'CONTROL' },
  { key: 'presence', icon: '◇', color: '#ffd700', label: 'PRESENCE' },
  { key: 'system',   icon: '⬡', color: '#e2e8f0', label: 'SYSTEM' },
]

const TIERS = [
  { key: 'easy',         label: 'EASY',    color: '#00ff88', rank: 'F', desc: '≤60 min · Low stakes' },
  { key: 'intermediate', label: 'INTER',   color: '#00d4ff', rank: 'C', desc: '≤120 min · Moderate' },
  { key: 'hard',         label: 'HARD',    color: '#ffd700', rank: 'A', desc: '≤180 min · Metrics required' },
  { key: 'extreme',      label: 'EXTREME', color: '#ff2040', rank: 'S', desc: '≤240 min · 24h cooldown · 3/week' },
]

export default function GenerateQuestPanel({ onGenerated, onClose, allowedDifficulties }) {
  const [domain, setDomain]       = useState('mind')
  const [difficulty, setDifficulty] = useState('easy')
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState(null)
  const [result, setResult]       = useState(null)

  const domainDef = DOMAINS.find(d => d.key === domain) || DOMAINS[0]

  const handleGenerate = useCallback(async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await questsAPI.generate({ domain, difficulty })
      setResult(res.data)
      onGenerated?.(res.data)
    } catch (err) {
      const detail = err?.response?.data?.detail || 'Generation failed'
      const status = err?.response?.status
      if (status === 429) {
        setError(`⏳ ${detail}`)
      } else if (status === 404) {
        setError(`○ ${detail}`)
      } else {
        setError(detail)
      }
    } finally {
      setLoading(false)
    }
  }, [domain, difficulty, onGenerated])

  return (
    <div style={{
      background: '#0a0a0f',
      border: `1px solid ${domainDef.color}22`,
      borderRadius: 8,
      padding: '24px',
      boxShadow: `inset 0 0 40px ${domainDef.color}06`,
    }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
        <div>
          <div style={{ color: '#00ff88', fontSize: 10, fontFamily: 'monospace', letterSpacing: '0.2em', marginBottom: 4 }}>
            TEMPLATE-BASED GENERATION
          </div>
          <div style={{ color: '#475569', fontSize: 10, fontFamily: 'monospace', letterSpacing: '0.06em' }}>
            Select domain and difficulty. The System assigns your quest from the template registry.
          </div>
        </div>
        {onClose && (
          <button onClick={onClose} style={{
            background: 'transparent', border: '1px solid #1e293b', color: '#475569',
            padding: '4px 10px', borderRadius: 3, cursor: 'pointer',
            fontFamily: 'monospace', fontSize: 10,
          }}>✗</button>
        )}
      </div>

      {/* Domain selector */}
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>DOMAIN</label>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {DOMAINS.map(d => (
            <button
              key={d.key}
              type="button"
              onClick={() => setDomain(d.key)}
              style={{
                background: domain === d.key ? `${d.color}18` : '#0d0d14',
                border: `1px solid ${domain === d.key ? d.color + 'aa' : '#1e293b'}`,
                borderRadius: 4,
                padding: '6px 12px',
                cursor: 'pointer',
                color: domain === d.key ? d.color : '#475569',
                fontFamily: 'monospace',
                fontSize: 10,
                fontWeight: domain === d.key ? 700 : 400,
                letterSpacing: '0.1em',
                transition: 'all 0.15s',
              }}
            >
              <span style={{ marginRight: 4 }}>{d.icon}</span>{d.label}
            </button>
          ))}
        </div>
      </div>

      {/* Difficulty selector */}
      <div style={{ marginBottom: 20 }}>
        <label style={labelStyle}>DIFFICULTY TIER</label>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {TIERS.map(t => {
            const locked = allowedDifficulties && !allowedDifficulties.includes(t.key)
            return (
            <button
              key={t.key}
              type="button"
              onClick={() => !locked && setDifficulty(t.key)}
              style={{
                background: locked ? '#0d0d14' : difficulty === t.key ? `${t.color}18` : '#0d0d14',
                border: `1px solid ${locked ? '#1e293b44' : difficulty === t.key ? t.color + 'aa' : '#1e293b'}`,
                borderRadius: 4,
                padding: '8px 14px',
                cursor: locked ? 'not-allowed' : 'pointer',
                color: locked ? '#1e293b' : difficulty === t.key ? t.color : '#475569',
                fontFamily: 'monospace',
                fontSize: 10,
                fontWeight: difficulty === t.key ? 700 : 400,
                letterSpacing: '0.1em',
                transition: 'all 0.15s',
                textAlign: 'left',
                opacity: locked ? 0.4 : 1,
              }}
            >
              <div>{locked ? '🔒' : `[${t.rank}]`} {t.label}</div>
              <div style={{ fontSize: 8, opacity: 0.6, marginTop: 2 }}>{locked ? 'RANK LOCKED' : t.desc}</div>
            </button>
            )
          })}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          background: '#ff204012', border: '1px solid #ff204044',
          borderRadius: 4, padding: '10px 14px', marginBottom: 16,
          color: '#ff2040', fontSize: 11, fontFamily: 'monospace', lineHeight: 1.5,
        }}>
          {error}
        </div>
      )}

      {/* Success result */}
      {result && (
        <div style={{
          background: '#00ff8808', border: '1px solid #00ff8830',
          borderRadius: 4, padding: '10px 14px', marginBottom: 16,
          color: '#00ff88', fontSize: 11, fontFamily: 'monospace', lineHeight: 1.6,
        }}>
          <div style={{ fontWeight: 700 }}>◆ {result.quest?.title || 'Quest generated'}</div>
          <div style={{ color: '#475569', fontSize: 10, marginTop: 4 }}>{result.message}</div>
        </div>
      )}

      {/* Generate button */}
      <button
        onClick={handleGenerate}
        disabled={loading}
        style={{
          width: '100%',
          background: loading ? '#1e293b' : `${domainDef.color}18`,
          border: `1px solid ${loading ? '#334155' : domainDef.color + '66'}`,
          color: loading ? '#475569' : domainDef.color,
          padding: '12px 20px',
          borderRadius: 4,
          cursor: loading ? 'wait' : 'pointer',
          fontFamily: 'monospace',
          fontSize: 12,
          fontWeight: 700,
          letterSpacing: '0.15em',
          transition: 'all 0.15s',
        }}
      >
        {loading ? 'GENERATING...' : '◆ GENERATE QUEST'}
      </button>
    </div>
  )
}

const labelStyle = {
  display: 'block',
  color: '#475569',
  fontSize: 9,
  fontFamily: 'monospace',
  letterSpacing: '0.15em',
  fontWeight: 700,
  marginBottom: 6,
}

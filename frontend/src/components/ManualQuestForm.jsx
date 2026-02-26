/**
 * ManualQuestForm.jsx
 *
 * Form for creating manual quests in the FLOW system.
 * Enforces the same rules as system quests:
 *   - Domain selection (6 domains)
 *   - Difficulty tier selection (4 tiers)
 *   - Metrics definition (required for Hard/Extreme)
 *   - Duration within tier limits
 *   - No comfort tasks — reviewed by system
 */
import React, { useState, useCallback } from 'react'

const DOMAINS = [
  { key: 'mind',     icon: '◈', color: '#00d4ff', label: 'MIND' },
  { key: 'body',     icon: '⚡', color: '#ff2040', label: 'BODY' },
  { key: 'core',     icon: '◉', color: '#00ff88', label: 'CORE' },
  { key: 'control',  icon: '◆', color: '#7c3aed', label: 'CONTROL' },
  { key: 'presence', icon: '◇', color: '#ffd700', label: 'PRESENCE' },
  { key: 'system',   icon: '⬡', color: '#e2e8f0', label: 'SYSTEM' },
]

const TIERS = [
  { key: 'easy',         label: 'EASY',    color: '#00ff88', rank: 'F', maxMin: 60,  metricsReq: false },
  { key: 'intermediate', label: 'INTER',   color: '#00d4ff', rank: 'C', maxMin: 120, metricsReq: false },
  { key: 'hard',         label: 'HARD',    color: '#ffd700', rank: 'A', maxMin: 180, metricsReq: true  },
  { key: 'extreme',      label: 'EXTREME', color: '#ff2040', rank: 'S', maxMin: 240, metricsReq: true  },
]

const STAT_OPTIONS = [
  { key: 'strength',     label: 'STR' },
  { key: 'intelligence', label: 'INT' },
  { key: 'vitality',     label: 'VIT' },
  { key: 'charisma',     label: 'CHA' },
  { key: 'mana',         label: 'MAN' },
]

const METRICS_HINTS = {
  mind:     'pages_read, problems_solved, notes_written, concepts_mapped',
  body:     'reps, sets, weight_kg, distance_km, time_active_min',
  core:     'meals_logged, hours_slept, water_ml, stretch_minutes',
  control:  'focus_minutes, distractions_blocked, sessions_completed',
  presence: 'interactions, words_spoken, presentations, feedback_received',
  system:   'tasks_completed, files_organized, items_cleaned, minutes_planned',
}

export default function ManualQuestForm({ onSubmit, isSubmitting = false, error = null }) {
  const [domain, setDomain]     = useState('mind')
  const [tier, setTier]         = useState('easy')
  const [title, setTitle]       = useState('')
  const [desc, setDesc]         = useState('')
  const [duration, setDuration] = useState('')
  const [stat, setStat]         = useState('intelligence')
  const [metricsJson, setMetricsJson] = useState('')

  const tierDef = TIERS.find(t => t.key === tier) || TIERS[0]
  const domainDef = DOMAINS.find(d => d.key === domain) || DOMAINS[0]

  const handleSubmit = useCallback((e) => {
    e.preventDefault()

    // Parse metrics
    let metricsDef = null
    if (tierDef.metricsReq && metricsJson.trim()) {
      try {
        metricsDef = JSON.parse(metricsJson)
      } catch {
        // Parse as key=value pairs
        const pairs = {}
        metricsJson.split(',').forEach(part => {
          const [k, v] = part.split('=').map(s => s.trim())
          if (k) pairs[k] = v || 'required'
        })
        if (Object.keys(pairs).length > 0) metricsDef = pairs
      }
    }

    const data = {
      title: title.trim(),
      description: desc.trim() || undefined,
      difficulty: tier,
      primary_stat: stat,
      domain,
      estimated_minutes: duration ? parseInt(duration, 10) : undefined,
      time_limit_minutes: duration ? parseInt(duration, 10) : undefined,
      metrics_required: tierDef.metricsReq,
      metrics_definition: metricsDef,
    }

    onSubmit?.(data)
  }, [title, desc, tier, stat, domain, duration, metricsJson, tierDef, onSubmit])

  return (
    <form onSubmit={handleSubmit} style={{
      background: '#0a0a0f',
      border: `1px solid ${domainDef.color}22`,
      borderRadius: 8,
      padding: '24px',
      boxShadow: `inset 0 0 40px ${domainDef.color}06`,
    }}>
      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ color: '#ffd700', fontSize: 10, fontFamily: 'monospace', letterSpacing: '0.2em', marginBottom: 4 }}>
          MANUAL QUEST CREATION
        </div>
        <div style={{ color: '#475569', fontSize: 10, fontFamily: 'monospace', letterSpacing: '0.06em' }}>
          Manual quests are as strict as system quests. No comfort tasks.
        </div>
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

      {/* Tier selector */}
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>DIFFICULTY TIER</label>
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {TIERS.map(t => (
            <button
              key={t.key}
              type="button"
              onClick={() => { setTier(t.key); if (duration && parseInt(duration) > t.maxMin) setDuration(String(t.maxMin)) }}
              style={{
                background: tier === t.key ? `${t.color}18` : '#0d0d14',
                border: `1px solid ${tier === t.key ? t.color + 'aa' : '#1e293b'}`,
                borderRadius: 4,
                padding: '6px 12px',
                cursor: 'pointer',
                color: tier === t.key ? t.color : '#475569',
                fontFamily: 'monospace',
                fontSize: 10,
                fontWeight: tier === t.key ? 700 : 400,
                letterSpacing: '0.1em',
                transition: 'all 0.15s',
              }}
            >
              [{t.rank}] {t.label}
              <span style={{ marginLeft: 6, fontSize: 8, opacity: 0.7 }}>≤{t.maxMin}m</span>
            </button>
          ))}
        </div>

        {/* Tier info */}
        <div style={{ marginTop: 6, display: 'flex', gap: 8 }}>
          {tierDef.metricsReq && (
            <span style={infoBadge('#ffd700')}>⚡ METRICS REQUIRED</span>
          )}
          {tier === 'extreme' && (
            <>
              <span style={infoBadge('#ff2040')}>24H COOLDOWN</span>
              <span style={infoBadge('#ff2040')}>3/WEEK LIMIT</span>
            </>
          )}
        </div>
      </div>

      {/* Title */}
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>QUEST TITLE</label>
        <input
          value={title}
          onChange={e => setTitle(e.target.value)}
          required
          minLength={5}
          maxLength={200}
          placeholder="Specific, measurable action (e.g. 'Complete 5 algorithm problems on LeetCode')"
          style={inputStyle}
        />
        <div style={{ color: '#334155', fontSize: 9, fontFamily: 'monospace', marginTop: 3 }}>
          Vague titles like "be productive" or "work on stuff" will be rejected.
        </div>
      </div>

      {/* Description */}
      <div style={{ marginBottom: 16 }}>
        <label style={labelStyle}>DESCRIPTION (optional)</label>
        <textarea
          value={desc}
          onChange={e => setDesc(e.target.value)}
          maxLength={1000}
          rows={2}
          placeholder="What specifically will you do? What proves effort?"
          style={{ ...inputStyle, resize: 'none', minHeight: 50 }}
        />
      </div>

      {/* Duration + Stat in a row */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 140 }}>
          <label style={labelStyle}>DURATION (minutes)</label>
          <input
            type="number"
            value={duration}
            onChange={e => setDuration(e.target.value)}
            min={1}
            max={tierDef.maxMin}
            placeholder={`1 – ${tierDef.maxMin}`}
            style={inputStyle}
          />
        </div>
        <div style={{ flex: 1, minWidth: 140 }}>
          <label style={labelStyle}>PRIMARY STAT</label>
          <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
            {STAT_OPTIONS.map(s => (
              <button
                key={s.key}
                type="button"
                onClick={() => setStat(s.key)}
                style={{
                  background: stat === s.key ? '#ffd70018' : '#0d0d14',
                  border: `1px solid ${stat === s.key ? '#ffd700aa' : '#1e293b'}`,
                  borderRadius: 3,
                  padding: '4px 8px',
                  cursor: 'pointer',
                  color: stat === s.key ? '#ffd700' : '#475569',
                  fontFamily: 'monospace',
                  fontSize: 9,
                  fontWeight: stat === s.key ? 700 : 400,
                  letterSpacing: '0.08em',
                }}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Metrics definition (for Hard/Extreme) */}
      {tierDef.metricsReq && (
        <div style={{ marginBottom: 16 }}>
          <label style={labelStyle}>METRICS DEFINITION — what must you submit?</label>
          <textarea
            value={metricsJson}
            onChange={e => setMetricsJson(e.target.value)}
            required
            rows={2}
            placeholder={METRICS_HINTS[domain] || 'Define your measurable proof'}
            style={{ ...inputStyle, resize: 'none', minHeight: 50 }}
          />
          <div style={{ color: '#334155', fontSize: 9, fontFamily: 'monospace', marginTop: 3 }}>
            Format: key=value pairs or JSON. E.g. push_ups=target, sets=target
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{
          background: '#ff204012', border: '1px solid #ff204044',
          borderRadius: 4, padding: '8px 12px', marginBottom: 16,
          color: '#ff2040', fontSize: 11, fontFamily: 'monospace', lineHeight: 1.5,
        }}>
          {error}
        </div>
      )}

      {/* Submit */}
      <button
        type="submit"
        disabled={isSubmitting || !title.trim()}
        style={{
          width: '100%',
          background: isSubmitting ? '#1e293b' : `${domainDef.color}18`,
          border: `1px solid ${isSubmitting ? '#334155' : domainDef.color + '66'}`,
          color: isSubmitting ? '#475569' : domainDef.color,
          padding: '10px 20px',
          borderRadius: 4,
          cursor: isSubmitting ? 'wait' : 'pointer',
          fontFamily: 'monospace',
          fontSize: 12,
          fontWeight: 700,
          letterSpacing: '0.15em',
          transition: 'all 0.15s',
        }}
      >
        {isSubmitting ? 'CREATING...' : '◆ CREATE QUEST'}
      </button>
    </form>
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

const inputStyle = {
  width: '100%',
  background: '#0d0d14',
  border: '1px solid #1e293b',
  borderRadius: 3,
  padding: '8px 12px',
  color: '#e2e8f0',
  fontFamily: 'monospace',
  fontSize: 12,
  outline: 'none',
  boxSizing: 'border-box',
  transition: 'border-color 0.15s',
}

function infoBadge(color) {
  return {
    color,
    fontSize: 8,
    fontFamily: 'monospace',
    letterSpacing: '0.08em',
    fontWeight: 700,
    border: `1px solid ${color}30`,
    background: `${color}10`,
    padding: '2px 7px',
    borderRadius: 2,
  }
}

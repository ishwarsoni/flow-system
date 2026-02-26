import React, { useState, useEffect, useCallback } from 'react'
import { adaptiveAPI } from '../api'

// ── Domain definitions ─────────────────────────────────────────────────────────

const DOMAINS = [
  { key: 'mind',     name: 'MIND',     icon: '◈', color: '#00d4ff', glow: '0 0 20px rgba(0,212,255,0.4)',   stat: 'INTELLIGENCE' },
  { key: 'body',     name: 'BODY',     icon: '⚡', color: '#ff2040', glow: '0 0 20px rgba(255,32,64,0.4)',   stat: 'STRENGTH'     },
  { key: 'core',     name: 'CORE',     icon: '◉', color: '#00ff88', glow: '0 0 20px rgba(0,255,136,0.4)',  stat: 'VITALITY'     },
  { key: 'control',  name: 'CONTROL',  icon: '◆', color: '#7c3aed', glow: '0 0 20px rgba(124,58,237,0.4)', stat: 'MANA'         },
  { key: 'presence', name: 'PRESENCE', icon: '◇', color: '#ffd700', glow: '0 0 20px rgba(255,215,0,0.4)',  stat: 'CHARISMA'     },
  { key: 'system',   name: 'SYSTEM',   icon: '⬡', color: '#e2e8f0', glow: '0 0 20px rgba(226,232,240,0.3)', stat: 'INTELLIGENCE' },
]

const TIERS = [
  { key: 'easy',         label: 'EASY',    color: '#00ff88', glow: '0 0 12px rgba(0,255,136,0.35)',  rank: 'F' },
  { key: 'intermediate', label: 'INTER',   color: '#00d4ff', glow: '0 0 12px rgba(0,212,255,0.35)', rank: 'C' },
  { key: 'hard',         label: 'HARD',    color: '#ffd700', glow: '0 0 12px rgba(255,215,0,0.35)',  rank: 'A' },
  { key: 'extreme',      label: 'EXTREME', color: '#ff2040', glow: '0 0 16px rgba(255,32,64,0.45)', rank: 'S' },
]

// ── Toast ──────────────────────────────────────────────────────────────────────

function Toast({ toast }) {
  if (!toast) return null
  const bg = toast.type === 'success' ? '#00ff88' : toast.type === 'error' ? '#ff2040' : '#00d4ff'
  return (
    <div style={{
      position: 'fixed', top: 24, right: 24, zIndex: 9999,
      background: '#0a0a0f', border: `1px solid ${bg}`,
      boxShadow: `0 0 24px ${bg}40`, padding: '12px 20px',
      borderRadius: 4, color: bg, fontFamily: 'monospace',
      fontSize: 13, letterSpacing: '0.05em', maxWidth: 380, lineHeight: 1.5,
    }}>
      {toast.message}
    </div>
  )
}

// ── Tier card ──────────────────────────────────────────────────────────────────

function TierCard({ tier, quest, domainColor, isChosen, isChoosing, onChoose, minTier, allowedDifficulties }) {
  if (!quest) return null
  const tierDef   = TIERS.find(t => t.key === tier)
  const order     = ['easy', 'intermediate', 'hard', 'extreme']
  // Lock tiers BELOW minimum AND tiers NOT in allowed difficulties (rank gate)
  const belowMin  = order.indexOf(tier) < order.indexOf(minTier || 'easy')
  const rankLocked = allowedDifficulties && !allowedDifficulties.includes(tier)
  const locked    = belowMin || rankLocked
  const border    = isChosen ? domainColor : tierDef.color

  return (
    <div
      onClick={() => !locked && !isChoosing && onChoose(tier)}
      style={{
        background: isChosen ? `linear-gradient(135deg, ${domainColor}18, #0a0a0f 60%)` : '#0d0d14',
        border: `1px solid ${border}${isChosen ? 'cc' : '44'}`,
        boxShadow: isChosen ? tierDef.glow : 'none',
        borderRadius: 6, padding: '14px 16px',
        cursor: locked ? 'not-allowed' : isChoosing ? 'wait' : 'pointer',
        opacity: locked ? 0.35 : 1,
        transition: 'all 0.2s ease', position: 'relative', overflow: 'hidden',
      }}
    >
      <div style={{ position: 'absolute', top: 10, right: 12, color: tierDef.color, fontSize: 10, fontFamily: 'monospace', letterSpacing: '0.1em', fontWeight: 700, opacity: 0.7 }}>
        [{tierDef.rank}]
      </div>
      <div style={{ color: tierDef.color, fontSize: 10, fontFamily: 'monospace', letterSpacing: '0.15em', fontWeight: 700, marginBottom: 6 }}>
        {locked ? '🔒 ' : ''}{tierDef.label}
      </div>
      <div style={{ color: '#e2e8f0', fontSize: 13, fontFamily: 'monospace', lineHeight: 1.45, marginBottom: 6, fontWeight: 500 }}>
        {quest.title}
      </div>
      {quest.description && (
        <div style={{ color: '#64748b', fontSize: 11, fontFamily: 'monospace', lineHeight: 1.4, marginBottom: 10 }}>
          {quest.description}
        </div>
      )}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <span style={{ color: '#ffd700', fontSize: 11, fontFamily: 'monospace', background: '#ffd70018', border: '1px solid #ffd70030', padding: '2px 8px', borderRadius: 2 }}>
          +{quest.xp_reward} XP
        </span>
        {quest.primary_stat && (
          <span style={{ color: '#94a3b8', fontSize: 10, fontFamily: 'monospace', letterSpacing: '0.08em' }}>
            {quest.primary_stat.toUpperCase()}
          </span>
        )}
        {(tier === 'hard' || tier === 'extreme') && (
          <span style={{ color: '#ffd700', fontSize: 9, fontFamily: 'monospace', border: '1px solid rgba(255,215,0,0.25)', padding: '1px 7px', borderRadius: 2, letterSpacing: '0.08em' }}>
            ⚡ METRICS REQ
          </span>
        )}
        {tier === 'extreme' && (
          <span style={{ color: '#ff2040', fontSize: 9, fontFamily: 'monospace', border: '1px solid rgba(255,32,64,0.25)', padding: '1px 7px', borderRadius: 2, letterSpacing: '0.08em' }}>
            24H CD · 3/WK
          </span>
        )}
        {isChoosing && <span style={{ color: '#64748b', fontSize: 10, fontFamily: 'monospace' }}>processing...</span>}
        {isChosen && <span style={{ color: domainColor, fontSize: 10, fontFamily: 'monospace' }}>✓ LOCKED IN</span>}
      </div>
    </div>
  )
}

// ── Domain panel ───────────────────────────────────────────────────────────────

function DomainPanel({ domain, trio, chosen, choosingTier, onChoose, allowedDifficulties }) {
  const minTier = trio?.minimum_choosable_tier || 'easy'
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, paddingBottom: 12, borderBottom: `1px solid ${domain.color}22`, marginBottom: 2 }}>
        <span style={{ color: domain.color, fontSize: 20 }}>{domain.icon}</span>
        <div>
          <div style={{ color: domain.color, fontSize: 13, fontFamily: 'monospace', fontWeight: 700, letterSpacing: '0.15em' }}>{domain.name}</div>
          <div style={{ color: '#475569', fontSize: 10, fontFamily: 'monospace', letterSpacing: '0.08em' }}>{domain.stat} DOMAIN</div>
        </div>
        {trio && (
          <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
            <div style={{ color: '#475569', fontSize: 10, fontFamily: 'monospace', letterSpacing: '0.06em' }}>
              MINDSET {trio.mindset_tier?.toUpperCase()} · PHASE {trio.phase?.toUpperCase()}
            </div>
            {trio.force_challenge_active && (
              <div style={{ color: '#ff2040', fontSize: 10, fontFamily: 'monospace', letterSpacing: '0.08em', marginTop: 2 }}>
                ⚠ FORCE CHALLENGE ACTIVE
              </div>
            )}
          </div>
        )}
      </div>

      {trio ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {TIERS.map(({ key }) => (
            <TierCard
              key={key} tier={key} quest={trio[key]}
              domainColor={domain.color}
              isChosen={chosen?.tier === key}
              isChoosing={choosingTier === key}
              onChoose={(t) => onChoose(domain.key, t, trio.session_id)}
              minTier={minTier}
              allowedDifficulties={allowedDifficulties || trio?.allowed_difficulties}
            />
          ))}
        </div>
      ) : (
        <div style={{ color: '#475569', fontFamily: 'monospace', fontSize: 12, padding: '20px 0', textAlign: 'center', letterSpacing: '0.08em' }}>
          [NO QUESTS AVAILABLE]
        </div>
      )}

      {trio?.custom_quests?.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <div style={{ color: '#475569', fontSize: 10, fontFamily: 'monospace', letterSpacing: '0.1em', marginBottom: 6 }}>— CUSTOM MODULES —</div>
          {trio.custom_quests.map((cq, i) => (
            <div key={cq.custom_quest_id || i} style={{ background: '#0d0d14', border: '1px solid #1e293b', borderRadius: 4, padding: '10px 14px', marginBottom: 6 }}>
              <div style={{ color: '#94a3b8', fontSize: 12, fontFamily: 'monospace' }}>{cq.title}</div>
              <div style={{ color: '#ffd700', fontSize: 10, fontFamily: 'monospace', marginTop: 4 }}>+{cq.xp_reward} XP</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────────────────────

export default function AdaptiveQuestsPage() {
  const [panel,        setPanel]        = useState(null)
  const [loading,      setLoading]      = useState(true)
  const [error,        setError]        = useState(null)
  const [activeDomain, setActiveDomain] = useState('mind')
  const [choosingMap,  setChoosingMap]  = useState({})
  const [chosen,       setChosen]       = useState({})
  const [toast,        setToast]        = useState(null)

  const loadPanel = useCallback(async (force = false) => {
    setLoading(true); setError(null)
    try {
      const res = await adaptiveAPI.getDaily(force)
      setPanel(res.data)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to load domain panels')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadPanel() }, [loadPanel])
  useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(null), 3000); return () => clearTimeout(t) }, [toast])

  const handleChoose = useCallback(async (domainKey, tier, sessionId) => {
    setChoosingMap(prev => ({ ...prev, [domainKey]: tier }))
    try {
      const res = await adaptiveAPI.chooseTier({ session_id: sessionId, chosen_tier: tier })
      const data = res.data
      setChosen(prev => ({ ...prev, [domainKey]: { tier, quest_id: data.quest_id, title: data.quest_title } }))
      const metricsNote = (tier === 'hard' || tier === 'extreme') ? ' — SUBMIT METRICS TO COMPLETE' : ''
      const cooldownNote = tier === 'extreme' ? ' [24H CD · 3/WK]' : ''
      setToast({ type: 'success', message: `[${domainKey.toUpperCase()}/${tier.toUpperCase()}] ${data.quest_title} — MISSION ACCEPTED${metricsNote}${cooldownNote}` })
    } catch (err) {
      setToast({ type: 'error', message: err?.response?.data?.detail || `Failed to lock in ${tier}` })
    } finally {
      setChoosingMap(prev => { const n = { ...prev }; delete n[domainKey]; return n })
    }
  }, [])

  const activeDef = DOMAINS.find(d => d.key === activeDomain)

  return (
    <div style={{ minHeight: '100vh', background: 'radial-gradient(ellipse at top, #0f0f1a 0%, #05050a 100%)', padding: '24px 16px', fontFamily: 'monospace' }}>
      <Toast toast={toast} />

      {/* Header */}
      <div style={{ maxWidth: 900, margin: '0 auto', marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <div style={{ color: '#00d4ff', fontSize: 11, letterSpacing: '0.2em', fontWeight: 700, marginBottom: 4 }}>SYSTEM / DAILY MODULES</div>
            <h1 style={{ color: '#e2e8f0', fontSize: 22, fontWeight: 700, letterSpacing: '0.08em', margin: 0 }}>DOMAIN OPERATIONS</h1>
          </div>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            {panel && <div style={{ color: '#475569', fontSize: 10, letterSpacing: '0.1em' }}>PHASE: {panel.phase?.toUpperCase()} · {panel.date}</div>}
            <button
              onClick={loadPanel} disabled={loading}
              style={{ background: 'transparent', border: '1px solid #1e293b', color: loading ? '#475569' : '#94a3b8', padding: '6px 14px', borderRadius: 3, cursor: loading ? 'wait' : 'pointer', fontSize: 11, letterSpacing: '0.1em', fontFamily: 'monospace' }}
            >
              {loading ? 'LOADING...' : '↺ REFRESH'}
            </button>
            <button
              onClick={() => loadPanel(true)} disabled={loading}
              style={{ background: 'transparent', border: '1px solid rgba(255,215,0,0.25)', color: loading ? '#475569' : '#ffd700', padding: '6px 14px', borderRadius: 3, cursor: loading ? 'wait' : 'pointer', fontSize: 11, letterSpacing: '0.1em', fontFamily: 'monospace' }}
              title="Clear cached sessions and generate fresh quests from current templates"
            >
              ⟳ NEW QUESTS
            </button>
          </div>
        </div>
      </div>

      {/* Domain tabs */}
      <div style={{ maxWidth: 900, margin: '0 auto', marginBottom: 20 }}>
        <div style={{ display: 'flex', gap: 2, flexWrap: 'wrap', borderBottom: '1px solid #1e293b' }}>
          {DOMAINS.map(d => {
            const isActive = d.key === activeDomain
            return (
              <button key={d.key} onClick={() => setActiveDomain(d.key)} style={{
                background: isActive ? `${d.color}14` : 'transparent',
                border: 'none', borderBottom: isActive ? `2px solid ${d.color}` : '2px solid transparent',
                color: isActive ? d.color : '#475569',
                padding: '8px 16px', cursor: 'pointer', fontSize: 11,
                fontFamily: 'monospace', letterSpacing: '0.12em',
                fontWeight: isActive ? 700 : 400, transition: 'all 0.15s', position: 'relative',
              }}>
                <span style={{ marginRight: 6 }}>{d.icon}</span>{d.name}
                {!!chosen[d.key] && <span style={{ position: 'absolute', top: 4, right: 4, width: 6, height: 6, borderRadius: '50%', background: d.color, opacity: 0.8 }} />}
              </button>
            )
          })}
        </div>
      </div>

      {/* Content */}
      <div style={{ maxWidth: 900, margin: '0 auto' }}>
        {loading && (
          <div style={{ textAlign: 'center', padding: '60px 0', color: '#475569', fontSize: 12, letterSpacing: '0.15em' }}>
            <div style={{ color: '#00d4ff', fontSize: 14, marginBottom: 8 }}>◈</div>
            INITIALIZING DOMAIN PANELS...
          </div>
        )}
        {error && !loading && (
          <div style={{ background: '#0d0d14', border: '1px solid #ff204044', borderRadius: 6, padding: '20px', color: '#ff2040', fontSize: 12, letterSpacing: '0.08em', textAlign: 'center' }}>
            <div style={{ marginBottom: 8, fontSize: 18 }}>✗</div>
            {error}
            <div style={{ marginTop: 12 }}>
              <button onClick={loadPanel} style={{ background: '#ff204018', border: '1px solid #ff204044', color: '#ff2040', padding: '6px 16px', borderRadius: 3, cursor: 'pointer', fontSize: 11, fontFamily: 'monospace', letterSpacing: '0.1em' }}>RETRY</button>
            </div>
          </div>
        )}
        {!loading && !error && panel && activeDef && (
          <div style={{ background: '#0a0a0f', border: `1px solid ${activeDef.color}22`, borderRadius: 8, padding: '24px', boxShadow: `inset 0 0 40px ${activeDef.color}06` }}>
            <DomainPanel
              domain={activeDef}
              trio={panel.panels?.[activeDomain]}
              chosen={chosen[activeDomain]}
              choosingTier={choosingMap[activeDomain]}
              onChoose={handleChoose}
              allowedDifficulties={panel.allowed_difficulties}
            />
          </div>
        )}
      </div>

      {/* Domain status grid */}
      {!loading && !error && panel && (
        <div style={{ maxWidth: 900, margin: '24px auto 0' }}>
          <div style={{ color: '#1e293b', fontSize: 10, letterSpacing: '0.15em', marginBottom: 12, textAlign: 'center' }}>— DOMAIN STATUS OVERVIEW —</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 8 }}>
            {DOMAINS.map(d => {
              const hasTrio = !!panel.panels?.[d.key]
              const c       = chosen[d.key]
              return (
                <button key={d.key} onClick={() => setActiveDomain(d.key)} style={{
                  background: activeDomain === d.key ? `${d.color}14` : '#0a0a0f',
                  border: `1px solid ${activeDomain === d.key ? d.color + '66' : '#1e293b'}`,
                  borderRadius: 5, padding: '10px 12px', cursor: 'pointer', textAlign: 'left', transition: 'all 0.15s', fontFamily: 'monospace',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                    <span style={{ color: d.color, fontSize: 14 }}>{d.icon}</span>
                    <span style={{ color: activeDomain === d.key ? d.color : '#94a3b8', fontSize: 10, fontWeight: 700, letterSpacing: '0.12em' }}>{d.name}</span>
                  </div>
                  <div style={{ color: c ? d.color : hasTrio ? '#475569' : '#2d3748', fontSize: 9, letterSpacing: '0.08em' }}>
                    {c ? `✓ ${c.tier.toUpperCase()}` : hasTrio ? 'READY' : 'NO DATA'}
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      )}

      <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }`}</style>
    </div>
  )
}

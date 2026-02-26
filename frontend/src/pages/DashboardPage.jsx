import React, { useState, useEffect } from 'react'
import { playerAPI } from '../api'

const STAT_COLORS = {
  strength:     { main: '#ff4060', bar: 'linear-gradient(90deg,#ff204080,#ff4060)' },
  intelligence: { main: '#00d4ff', bar: 'linear-gradient(90deg,#00d4ff40,#00d4ff)' },
  vitality:     { main: '#00ff88', bar: 'linear-gradient(90deg,#00ff8840,#00ff88)' },
  charisma:     { main: '#ffd700', bar: 'linear-gradient(90deg,#ffd70040,#ffd700)' },
  mana:         { main: '#7c3aed', bar: 'linear-gradient(90deg,#7c3aed40,#7c3aed)' },
}
const STAT_LABELS = { strength: 'STR', intelligence: 'INT', vitality: 'VIT', charisma: 'CHA', mana: 'MAN' }

const RANK_COLORS = {
  E:'#6b7280', D:'#60a5fa', C:'#34d399', B:'#fbbf24', A:'#f97316', S:'#ff2040', SS:'#a855f7', SSS:'#ec4899',
}

export default function DashboardPage() {
  const [profile, setProfile] = useState(null)
  const [shadow, setShadow] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [allocating, setAllocating] = useState(false)
  const [pendingPoints, setPendingPoints] = useState({})

  useEffect(() => { loadProfile() }, [])

  async function loadProfile() {
    try {
      setLoading(true)
      const [profRes, shadowRes] = await Promise.all([
        playerAPI.getProfile(),
        playerAPI.getShadow().catch(() => null),
      ])
      setProfile(profRes.data)
      if (shadowRes) setShadow(shadowRes.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load player data')
    } finally {
      setLoading(false)
    }
  }

  async function handleAllocate() {
    const total = Object.values(pendingPoints).reduce((a, b) => a + b, 0)
    if (total === 0) return
    try {
      setAllocating(true)
      await playerAPI.allocateStats(pendingPoints)
      setPendingPoints({})
      await loadProfile()
    } catch (err) {
      setError(err.response?.data?.detail || 'Allocation failed')
    } finally {
      setAllocating(false)
    }
  }

  function addPoint(stat) {
    const totalPending = Object.values(pendingPoints).reduce((a, b) => a + b, 0)
    if (totalPending >= (profile?.skill_points || 0)) return
    setPendingPoints({ ...pendingPoints, [stat]: (pendingPoints[stat] || 0) + 1 })
  }

  function removePoint(stat) {
    if (!pendingPoints[stat]) return
    const next = { ...pendingPoints }
    next[stat] = (next[stat] || 0) - 1
    if (next[stat] <= 0) delete next[stat]
    setPendingPoints(next)
  }

  if (loading) return (
    <div style={s.loadWrap}>
      <div style={s.loadSpinner} />
      <p style={s.loadText}>[ LOADING PLAYER DATA... ]</p>
    </div>
  )

  if (error) return (
    <div style={s.loadWrap}>
      <p style={{ color: '#ff2040', fontFamily: "'Orbitron',monospace", fontSize: 14 }}>ERROR: {error}</p>
      <button onClick={loadProfile} style={s.retryBtn}>[ RETRY ]</button>
    </div>
  )

  if (!profile) return null

  const xpPct = profile.xp_for_next_level > 0 ? Math.min(100, (profile.xp_current / profile.xp_for_next_level) * 100) : 0
  const hpPct = profile.hp_max > 0 ? (profile.hp_current / profile.hp_max) * 100 : 100
  const mpPct = profile.mp_max > 0 ? (profile.mp_current / profile.mp_max) * 100 : 100
  const fatPct = Math.min(100, profile.fatigue || 0)
  const rankColor = RANK_COLORS[profile.rank] || '#6b7280'
  const totalPending = Object.values(pendingPoints).reduce((a, b) => a + b, 0)

  return (
    <div style={s.page}>

      <div style={s.statusHeader}>
        <div style={s.slHeaderLabel}>[ STATUS WINDOW ]</div>
        <div style={s.headerLine} />
      </div>

      <div style={s.identityPanel}>
        <div style={{ ...s.rankOrb, borderColor: rankColor, boxShadow: `0 0 28px ${rankColor}60` }}>
          <span style={{ ...s.rankGlyph, color: rankColor }}>{profile.rank}</span>
        </div>
        <div style={s.idMeta}>
          <div style={s.idName}>{profile.hunter_name}</div>
          <div style={{ ...s.idTitle, color: rankColor }}>{profile.rank}-Rank {profile.current_title || profile.rank_title}</div>
          <div style={s.idLevelNum}>LV.{profile.level}</div>
        </div>
        <div style={s.econBlock}>
          {profile.skill_points > 0 && (
            <div style={{ ...s.econItem, borderColor: 'rgba(124,58,237,0.4)' }}>
              <span style={{ ...s.econLabel, color: '#a78bfa' }}>SKILL PTS</span>
              <span style={{ ...s.econVal, color: '#a78bfa' }}>{profile.skill_points}</span>
            </div>
          )}
        </div>
      </div>

      <div style={s.xpPanel}>
        <div style={s.xpRow}>
          <span style={s.xpLabel}>EXP</span>
          <div style={s.xpBarOuter}>
            <div style={{ ...s.xpBarFill, width: `${xpPct}%` }} />
          </div>
          <span style={s.xpNums}>{profile.xp_current} / {profile.xp_for_next_level}</span>
        </div>
        {profile.streak_xp_bonus_percent > 0 && (
          <span style={s.streakBadge}>STREAK BONUS +{profile.streak_xp_bonus_percent}%</span>
        )}
      </div>

      <div style={s.vitalsGrid}>
        <VitalBar label="HP" current={profile.hp_current} max={profile.hp_max} pct={hpPct} color="#ff2040" />
        <VitalBar label="MP" current={profile.mp_current} max={profile.mp_max} pct={mpPct} color="#00d4ff" />
        <VitalBar label="FATIGUE" current={Math.round(profile.fatigue || 0)} max={100} pct={fatPct} color="#ffd700" warn />
      </div>

      <div style={s.statsPanel}>
        <div style={s.panelHeader}>
          <span style={s.panelTitle}>[ CORE STATS ]</span>
          {profile.skill_points > 0 && (
            <span style={s.spAvail}>{profile.skill_points} POINTS AVAILABLE</span>
          )}
        </div>
        <div style={s.statsGrid}>
          {Object.entries(STAT_COLORS).map(([stat, col]) => {
            const val = profile[stat] || 0
            const pending = pendingPoints[stat] || 0
            const total = val + pending
            return (
              <div key={stat} style={s.statRow}>
                <span style={{ ...s.statLabel, color: col.main }}>{STAT_LABELS[stat]}</span>
                <div style={s.statBarWrap}>
                  <div style={s.statBarBg}>
                    <div style={{ ...s.statBarFill, width: `${Math.min(100, val)}%`, background: col.bar }} />
                    {pending > 0 && (
                      <div style={{ ...s.statBarPend, left: `${Math.min(100, val)}%`, width: `${Math.min(100 - val, pending * 2)}%` }} />
                    )}
                  </div>
                </div>
                <span style={{ ...s.statVal, color: pending > 0 ? col.main : '#b8d8f0' }}>
                  {total.toFixed(1)}{pending > 0 && <span style={s.pendingTag}>+{pending}</span>}
                </span>
                {profile.skill_points > 0 && (
                  <div style={s.allocBtns}>
                    <button onClick={() => removePoint(stat)} disabled={!pending} style={s.allocMinus}>-</button>
                    <button onClick={() => addPoint(stat)} disabled={totalPending >= profile.skill_points} style={s.allocPlus}>+</button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
        {totalPending > 0 && (
          <button onClick={handleAllocate} disabled={allocating} style={s.confirmBtn}>
            {allocating ? '[ PROCESSING... ]' : `[ CONFIRM ALLOCATION — ${totalPending} PTS ]`}
          </button>
        )}
      </div>

      <div style={s.statusGrid}>
        <StatusCard label="[ STREAK ]" value={`${profile.streak_days} DAYS`} icon="" accent="#ff6b35" />
        <StatusCard label="[ REPUTATION ]" value={profile.reputation} icon="" accent="#ffd700" />
        <StatusCard label="[ ACTIVE DUNGEONS ]" value={`${profile.daily_quest_count} ACTIVE`} icon="" accent="#00d4ff" />
        {profile.next_rank && (
          <StatusCard label="[ NEXT RANK ]" value={`${profile.next_rank.rank} — ${profile.next_rank.levels_away}LV`} icon="" accent={RANK_COLORS[profile.next_rank.rank]} />
        )}
        {profile.punishment_active > 0 && (
          <StatusCard label="[ PUNISHMENT ]" value={`${profile.punishment_active}h`} icon="" accent="#ff2040" danger />
        )}
      </div>

      {shadow && <ShadowRivalWidget shadow={shadow} />}

      <div style={{ ...s.rankPanel, borderColor: `${rankColor}40` }}>
        <div style={{ ...s.rankPanelBadge, color: rankColor, borderColor: rankColor, boxShadow: `0 0 16px ${rankColor}40` }}>{profile.rank}</div>
        <div>
          <div style={s.rankPanelTitle}>{profile.rank_title}</div>
          <div style={s.rankBonuses}>
            <span style={s.rankBonus}>XP {profile.rank_xp_multiplier}x</span>
            <span style={s.rankBonus}>+SP PER QUEST</span>
            {profile.special_quests_unlocked && <span style={{ ...s.rankBonus, color: '#ffd700' }}>SPECIAL QUESTS UNLOCKED</span>}
          </div>
        </div>
      </div>

    </div>
  )
}

function VitalBar({ label, current, max, pct, color, warn }) {
  const barColor = warn ? (pct > 60 ? '#ff2040' : pct > 30 ? '#ffd700' : '#00ff88') : color
  return (
    <div style={s.vitalCard}>
      <div style={s.vitalTop}>
        <span style={{ ...s.vitalLabel, color: barColor }}>{label}</span>
        <span style={s.vitalNums}>{current} / {max}</span>
      </div>
      <div style={s.vitalBarOuter}>
        <div style={{ ...s.vitalBarFill, width: `${pct}%`, background: `linear-gradient(90deg,${barColor}60,${barColor})`, boxShadow: `0 0 10px ${barColor}50` }} />
      </div>
    </div>
  )
}

function StatusCard({ label, value, icon, accent, danger }) {
  return (
    <div style={{ ...s.statusCard, borderColor: danger ? 'rgba(255,32,64,0.35)' : 'rgba(0,212,255,0.15)', background: danger ? 'rgba(255,32,64,0.06)' : 'rgba(0,8,20,0.7)' }}>
      <span style={s.statusIcon}>{icon}</span>
      <div>
        <div style={{ ...s.statusLabel2, color: danger ? '#ff2040' : 'rgba(0,212,255,0.6)' }}>{label}</div>
        <div style={{ ...s.statusVal, color: accent || '#e8f4ff' }}>{value}</div>
      </div>
    </div>
  )
}

function ShadowRivalWidget({ shadow }) {
  const stats = ['strength', 'intelligence', 'vitality', 'charisma', 'mana']
  const statColors = { strength: '#ff4444', intelligence: '#9b59b6', vitality: '#2ecc71', charisma: '#f39c12', mana: '#3498db' }
  const isLeading = (stat) => shadow.leading_stats.includes(stat)
  const isTrailing = (stat) => shadow.trailing_stats.includes(stat)

  const maxStat = Math.max(
    ...stats.map(st => Math.max(shadow.shadow_stats[st] || 0, shadow.real_stats[st] || 0)),
    1
  )

  return (
    <div style={{ padding: '20px 22px', background: 'rgba(4,12,30,0.9)', border: '1px solid rgba(255,32,64,0.35)', borderRadius: 2, display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontFamily: "'Orbitron',monospace", fontSize: 11, color: '#ff2040', letterSpacing: 3 }}>[ SHADOW RIVAL ]</span>
        <span style={{ fontFamily: "'Orbitron',monospace", fontSize: 9, color: 'rgba(255,32,64,0.5)', letterSpacing: 2 }}>
          {shadow.gap_xp > 0 ? `BEHIND BY ${shadow.gap_xp.toLocaleString()} XP` : `AHEAD BY ${Math.abs(shadow.gap_xp).toLocaleString()} XP`}
        </span>
      </div>

      {/* Motivational message */}
      <div style={{ fontSize: 13, color: '#b8d8f0', fontStyle: 'italic', borderLeft: '2px solid rgba(255,32,64,0.5)', paddingLeft: 12 }}>
        {shadow.motivational_message}
      </div>

      {/* Level comparison */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 10, alignItems: 'center' }}>
        <div style={{ textAlign: 'center', padding: '10px 0', border: '1px solid rgba(255,32,64,0.25)', background: 'rgba(255,32,64,0.05)', borderRadius: 2 }}>
          <div style={{ fontFamily: "'Orbitron',monospace", fontSize: 8, color: 'rgba(255,32,64,0.6)', letterSpacing: 2, marginBottom: 4 }}>SHADOW</div>
          <div style={{ fontFamily: "'Orbitron',monospace", fontSize: 22, fontWeight: 900, color: '#ff2040' }}>LV {shadow.shadow_level}</div>
          <div style={{ fontFamily: "'Orbitron',monospace", fontSize: 10, color: 'rgba(255,32,64,0.7)', letterSpacing: 2 }}>{shadow.shadow_rank}</div>
        </div>
        <div style={{ fontFamily: "'Orbitron',monospace", fontSize: 11, color: 'rgba(255,255,255,0.2)', textAlign: 'center' }}>VS</div>
        <div style={{ textAlign: 'center', padding: '10px 0', border: '1px solid rgba(0,212,255,0.25)', background: 'rgba(0,212,255,0.05)', borderRadius: 2 }}>
          <div style={{ fontFamily: "'Orbitron',monospace", fontSize: 8, color: 'rgba(0,212,255,0.6)', letterSpacing: 2, marginBottom: 4 }}>YOU</div>
          <div style={{ fontFamily: "'Orbitron',monospace", fontSize: 22, fontWeight: 900, color: '#00d4ff' }}>LV {shadow.real_level}</div>
          <div style={{ fontFamily: "'Orbitron',monospace", fontSize: 10, color: 'rgba(0,212,255,0.7)', letterSpacing: 2 }}>{shadow.real_rank}</div>
        </div>
      </div>

      {/* Stat comparison bars */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ fontFamily: "'Orbitron',monospace", fontSize: 9, color: 'rgba(255,255,255,0.3)', letterSpacing: 2, marginBottom: 2 }}>[ STAT COMPARISON ]</div>
        {stats.map(stat => {
          const shadowVal = shadow.shadow_stats[stat] || 0
          const realVal = shadow.real_stats[stat] || 0
          const shadowPct = (shadowVal / maxStat) * 100
          const realPct = (realVal / maxStat) * 100
          const color = statColors[stat]
          const trailing = isTrailing(stat)
          const leading = isLeading(stat)
          return (
            <div key={stat} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{ fontFamily: "'Orbitron',monospace", fontSize: 9, fontWeight: 700, letterSpacing: 2, width: 32, color: trailing ? '#ff2040' : leading ? '#2ecc71' : '#b8d8f0', flexShrink: 0 }}>
                {stat.slice(0, 3).toUpperCase()}
                {trailing && <span style={{ marginLeft: 2, fontSize: 8 }}>▼</span>}
                {leading && <span style={{ marginLeft: 2, fontSize: 8 }}>▲</span>}
              </div>
              {/* Shadow bar (left, fills left-to-right in red) */}
              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 3 }}>
                <div style={{ height: 5, background: 'rgba(255,255,255,0.04)', borderRadius: 1, overflow: 'hidden' }}>
                  <div style={{ width: `${shadowPct}%`, height: '100%', background: 'rgba(255,32,64,0.55)', borderRadius: 1 }} />
                </div>
                <div style={{ height: 5, background: 'rgba(255,255,255,0.04)', borderRadius: 1, overflow: 'hidden' }}>
                  <div style={{ width: `${realPct}%`, height: '100%', background: color, borderRadius: 1, opacity: 0.85 }} />
                </div>
              </div>
              <div style={{ fontFamily: "'Orbitron',monospace", fontSize: 9, color: '#b8d8f0', width: 50, textAlign: 'right', flexShrink: 0 }}>
                <span style={{ color: 'rgba(255,32,64,0.7)' }}>{shadowVal.toFixed(0)}</span>
                <span style={{ color: 'rgba(255,255,255,0.2)' }}> / </span>
                <span style={{ color }}>{realVal.toFixed(0)}</span>
              </div>
            </div>
          )
        })}
        <div style={{ display: 'flex', gap: 16, marginTop: 4 }}>
          <span style={{ fontFamily: "'Orbitron',monospace", fontSize: 8, color: 'rgba(255,32,64,0.6)', letterSpacing: 1 }}>▬ SHADOW</span>
          <span style={{ fontFamily: "'Orbitron',monospace", fontSize: 8, color: 'rgba(0,212,255,0.6)', letterSpacing: 1 }}>▬ YOU</span>
          {shadow.gap_days > 0 && (
            <span style={{ fontFamily: "'Orbitron',monospace", fontSize: 8, color: 'rgba(255,165,0,0.7)', letterSpacing: 1, marginLeft: 'auto' }}>
              ~{shadow.gap_days} DAYS TO CATCH UP
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

const s = {
  page: { padding: '12px 10px', maxWidth: 1100, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 12 },
  loadWrap: { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 20 },
  loadSpinner: { width: 44, height: 44, border: '2px solid rgba(0,212,255,0.1)', borderTop: '2px solid #00d4ff', borderRadius: '50%', animation: 'spin 1s linear infinite' },
  loadText: { fontFamily: "'Orbitron',monospace", fontSize: 11, color: 'rgba(0,212,255,0.4)', letterSpacing: 3 },
  retryBtn: { padding: '8px 24px', background: 'transparent', border: '1px solid rgba(0,212,255,0.4)', color: '#00d4ff', fontFamily: "'Orbitron',monospace", fontSize: 11, cursor: 'pointer', letterSpacing: 2 },
  statusHeader: { display: 'flex', alignItems: 'center', gap: 16 },
  slHeaderLabel: { fontFamily: "'Orbitron',monospace", fontSize: 10, color: 'rgba(0,212,255,0.45)', letterSpacing: 4, whiteSpace: 'nowrap' },
  headerLine: { flex: 1, height: 1, background: 'linear-gradient(90deg,rgba(0,212,255,0.3),transparent)' },
  identityPanel: { display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', padding: '14px 14px', background: 'rgba(4,12,30,0.9)', border: '1px solid rgba(0,212,255,0.2)', borderRadius: 2 },
  rankOrb: { width: 52, height: 52, borderRadius: 2, border: '2px solid', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.6)', flexShrink: 0 },
  rankGlyph: { fontFamily: "'Orbitron',monospace", fontSize: 28, fontWeight: 900 },
  idMeta: { flex: 1 },
  idName: { fontFamily: "'Orbitron',monospace", fontSize: 16, fontWeight: 700, color: '#e8f4ff', letterSpacing: 2 },
  idTitle: { fontSize: 12, fontWeight: 600, letterSpacing: 1, marginTop: 2 },
  idLevelNum: { fontFamily: "'Orbitron',monospace", fontSize: 22, fontWeight: 900, color: '#00d4ff', marginTop: 6 },
  econBlock: { display: 'flex', gap: 12, flexWrap: 'wrap' },
  econItem: { padding: '8px 14px', border: '1px solid rgba(0,212,255,0.2)', borderRadius: 2, background: 'rgba(0,212,255,0.04)', textAlign: 'center' },
  econLabel: { display: 'block', fontFamily: "'Orbitron',monospace", fontSize: 9, color: 'rgba(0,212,255,0.5)', letterSpacing: 2, marginBottom: 2 },
  econVal: { fontFamily: "'Orbitron',monospace", fontSize: 16, fontWeight: 700, color: '#ffd700' },
  xpPanel: { padding: '10px 18px', background: 'rgba(4,12,30,0.7)', border: '1px solid rgba(0,212,255,0.12)', borderRadius: 2, display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' },
  xpRow: { flex: 1, display: 'flex', alignItems: 'center', gap: 12 },
  xpLabel: { fontFamily: "'Orbitron',monospace", fontSize: 10, color: 'rgba(0,212,255,0.6)', letterSpacing: 2, whiteSpace: 'nowrap' },
  xpBarOuter: { flex: 1, height: 8, background: 'rgba(0,212,255,0.07)', borderRadius: 1, overflow: 'hidden', border: '1px solid rgba(0,212,255,0.12)' },
  xpBarFill: { height: '100%', background: 'linear-gradient(90deg,#0062ff,#00d4ff)', transition: 'width 0.8s ease', boxShadow: '0 0 12px rgba(0,212,255,0.5)' },
  xpNums: { fontFamily: "'Orbitron',monospace", fontSize: 10, color: '#b8d8f0', whiteSpace: 'nowrap' },
  streakBadge: { fontFamily: "'Orbitron',monospace", fontSize: 9, color: '#ff6b35', letterSpacing: 2 },
  vitalsGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(160px,1fr))', gap: 8 },
  vitalCard: { padding: '12px 16px', background: 'rgba(4,12,30,0.8)', border: '1px solid rgba(0,212,255,0.12)', borderRadius: 2 },
  vitalTop: { display: 'flex', justifyContent: 'space-between', marginBottom: 8 },
  vitalLabel: { fontFamily: "'Orbitron',monospace", fontSize: 10, fontWeight: 700, letterSpacing: 2 },
  vitalNums: { fontSize: 12, color: '#b8d8f0', fontWeight: 600 },
  vitalBarOuter: { height: 6, background: 'rgba(255,255,255,0.05)', borderRadius: 1, overflow: 'hidden' },
  vitalBarFill: { height: '100%', borderRadius: 1, transition: 'width 0.6s ease' },
  statsPanel: { padding: '14px 14px', background: 'rgba(4,12,30,0.9)', border: '1px solid rgba(0,212,255,0.2)', borderRadius: 2 },
  panelHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  panelTitle: { fontFamily: "'Orbitron',monospace", fontSize: 11, color: 'rgba(0,212,255,0.6)', letterSpacing: 3 },
  spAvail: { fontFamily: "'Orbitron',monospace", fontSize: 9, color: '#7c3aed', letterSpacing: 2, padding: '3px 10px', border: '1px solid rgba(124,58,237,0.3)' },
  statsGrid: { display: 'flex', flexDirection: 'column', gap: 12 },
  statRow: { display: 'flex', alignItems: 'center', gap: 12 },
  statLabel: { fontFamily: "'Orbitron',monospace", fontSize: 10, fontWeight: 700, letterSpacing: 2, width: 34, flexShrink: 0 },
  statBarWrap: { flex: 1 },
  statBarBg: { height: 6, background: 'rgba(255,255,255,0.04)', borderRadius: 1, position: 'relative', overflow: 'visible' },
  statBarFill: { position: 'absolute', top: 0, left: 0, height: '100%', borderRadius: 1, transition: 'width 0.5s ease' },
  statBarPend: { position: 'absolute', top: 0, height: '100%', background: 'rgba(124,58,237,0.35)', borderRadius: 1 },
  statVal: { fontFamily: "'Orbitron',monospace", fontSize: 12, fontWeight: 700, width: 70, textAlign: 'right', flexShrink: 0 },
  pendingTag: { fontSize: 9, color: '#7c3aed', marginLeft: 4 },
  allocBtns: { display: 'flex', gap: 4, flexShrink: 0 },
  allocMinus: { width: 36, height: 36, background: 'transparent', border: '1px solid rgba(0,212,255,0.2)', color: '#b8d8f0', cursor: 'pointer', fontSize: 16, fontWeight: 700, borderRadius: 2 },
  allocPlus: { width: 36, height: 36, background: 'rgba(0,212,255,0.08)', border: '1px solid rgba(0,212,255,0.3)', color: '#00d4ff', cursor: 'pointer', fontSize: 16, fontWeight: 700, borderRadius: 2 },
  confirmBtn: { marginTop: 16, width: '100%', padding: '12px 0', background: 'rgba(0,212,255,0.07)', border: '1px solid rgba(0,212,255,0.4)', color: '#00d4ff', fontFamily: "'Orbitron',monospace", fontSize: 11, letterSpacing: 2, cursor: 'pointer' },
  statusGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))', gap: 8 },
  statusCard: { padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 12, borderRadius: 2, border: '1px solid' },
  statusIcon: { fontSize: 22 },
  statusLabel2: { fontFamily: "'Orbitron',monospace", fontSize: 9, letterSpacing: 2, marginBottom: 3 },
  statusVal: { fontSize: 14, fontWeight: 700 },
  rankPanel: { padding: '14px 20px', display: 'flex', alignItems: 'center', gap: 18, background: 'rgba(4,12,30,0.8)', border: '1px solid', borderRadius: 2 },
  rankPanelBadge: { fontFamily: "'Orbitron',monospace", fontSize: 28, fontWeight: 900, padding: '6px 16px', border: '1px solid' },
  rankPanelTitle: { fontSize: 14, color: '#b8d8f0', fontWeight: 600, marginBottom: 6 },
  rankBonuses: { display: 'flex', gap: 16, flexWrap: 'wrap' },
  rankBonus: { fontFamily: "'Orbitron',monospace", fontSize: 10, color: 'rgba(0,212,255,0.6)', letterSpacing: 1 },
}

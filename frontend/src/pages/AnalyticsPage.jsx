import React, { useState, useEffect } from 'react'
import { analyticsAPI } from '../api'

const STAT_COLS = {
  strength: '#ff4060', intelligence: '#00d4ff', vitality: '#00ff88', charisma: '#ffd700', mana: '#7c3aed',
}
const STAT_LBLS = { strength: 'STR', intelligence: 'INT', vitality: 'VIT', charisma: 'CHA', mana: 'MAN' }

export default function AnalyticsPage() {
  const [overview, setOverview] = useState(null)
  const [history, setHistory] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function load() {
      try {
        setLoading(true)
        // Fetch independently so a history failure does not block the overview
        const ovRes = await analyticsAPI.getOverview()
        setOverview(ovRes.data)
        try {
          const histRes = await analyticsAPI.getHistory()
          setHistory(histRes.data)
        } catch (histErr) {
          console.warn('History fetch failed:', histErr)
          // history is optional — page still renders with overview
        }
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load system records')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) return (
    <div style={s.loadWrap}><div style={s.spinner} /><p style={s.loadText}>[ LOADING SYSTEM RECORDS... ]</p></div>
  )
  if (error) return <div style={s.errBox}>{error}</div>
  if (!overview) return null

  const stats = ['strength', 'intelligence', 'vitality', 'charisma', 'mana']

  return (
    <div style={s.page}>
      <div style={s.pageHeader}>
        <span style={s.pageTag}>[ SYSTEM RECORDS ]</span>
        <div style={s.headerLine} />
      </div>

      <div style={s.metricGrid}>
        <SLCard label="LEVEL" value={overview.level} sub={`RANK ${overview.rank}`} accent="#00d4ff" />
        <SLCard label="TOTAL XP" value={(overview.xp_total_earned || 0).toLocaleString()} sub={`${overview.xp_to_next_level || 0} TO NEXT`} accent="#7c3aed" />
        <SLCard label="SKILL PTS" value={(overview.skill_points || 0).toLocaleString()} accent="#a78bfa" />
        <SLCard label="HP" value={`${overview.hp_current}/${overview.hp_max}`} accent="#ff2040" />
        <SLCard label="MP" value={`${overview.mp_current}/${overview.mp_max}`} accent="#00d4ff" />
        <SLCard label="FATIGUE" value={`${Math.round(overview.fatigue || 0)}%`} accent={overview.fatigue > 60 ? '#ff2040' : '#ffd700'} />
      </div>

      <div style={s.panel}>
        <div style={s.panelHeader}><span style={s.panelTag}>[ STAT ANALYSIS ]</span></div>
        <div style={s.statList}>
          {stats.map(stat => {
            const val = overview[stat] || 0
            return (
              <div key={stat} style={s.statRow}>
                <span style={{ ...s.statLbl, color: STAT_COLS[stat] }}>{STAT_LBLS[stat]}</span>
                <div style={s.statBarBg}>
                  <div style={{ ...s.statBarFill, width: `${Math.min(100, val)}%`, background: `linear-gradient(90deg,${STAT_COLS[stat]}40,${STAT_COLS[stat]})`, boxShadow: `0 0 8px ${STAT_COLS[stat]}40` }} />
                </div>
                <span style={{ ...s.statVal, color: STAT_COLS[stat] }}>{val.toFixed(1)}</span>
              </div>
            )
          })}
        </div>
        <div style={s.statMeta}>
          <span style={s.statMetaItem}>STRONGEST: <span style={{ color: STAT_COLS[overview.strongest_stat] }}>{(overview.strongest_stat || '').toUpperCase()} {(overview.strongest_stat_value || 0).toFixed(1)}</span></span>
          <span style={s.statMetaItem}>WEAKEST: <span style={{ color: STAT_COLS[overview.weakest_stat] }}>{(overview.weakest_stat || '').toUpperCase()} {(overview.weakest_stat_value || 0).toFixed(1)}</span></span>
        </div>
      </div>

      <div style={s.panel}>
        <div style={s.panelHeader}><span style={s.panelTag}>[ 7-DAY PERFORMANCE ]</span></div>
        <div style={s.weekGrid}>
          <SLCard label="XP EARNED" value={overview.xp_earned_7days || 0} accent="#7c3aed" small />
          <SLCard label="COMPLETED" value={overview.quests_completed_7days || overview.tasks_completed_7days || 0} accent="#00ff88" small />
          <SLCard label="FAILED" value={overview.quests_failed_7days || overview.tasks_failed_7days || 0} accent="#ff2040" small />
        </div>
        {history && (
          <div style={s.chart}>
            <div style={s.chartTitle}>[ DAILY XP FLOW ]</div>
            <div style={s.chartBars}>
              {(history.dates || []).map((dateStr, i) => {
                const xp = (history.xp_by_day || [])[i] || 0
                const maxXP = Math.max(...(history.xp_by_day || [1]), 1)
                const h = (xp / maxXP) * 100
                const day = new Date(dateStr).toLocaleDateString('en', { weekday: 'short' }).toUpperCase()
                return (
                  <div key={dateStr} style={s.chartCol}>
                    <span style={s.chartVal}>{xp}</span>
                    <div style={s.chartBarOuter}>
                      <div style={{ ...s.chartBarFill, height: `${Math.max(2, h)}%` }} />
                    </div>
                    <span style={s.chartDay}>{day}</span>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>

      <div style={s.streakRow}>
        <div style={s.streakCard}>
          <span style={s.streakIcon}></span>
          <div>
            <div style={s.streakVal}>{overview.current_streak_days || 0}</div>
            <div style={s.streakLbl}>CURRENT STREAK</div>
          </div>
        </div>
        <div style={s.streakCard}>
          <span style={s.streakIcon}></span>
          <div>
            <div style={s.streakVal}>{overview.longest_streak_days || 0}</div>
            <div style={s.streakLbl}>BEST STREAK</div>
          </div>
        </div>
      </div>
    </div>
  )
}

function SLCard({ label, value, sub, accent, small }) {
  return (
    <div style={{ ...s.slCard, borderColor: `${accent}25` }}>
      <div style={{ ...s.slCardLabel, color: `${accent}80` }}>{label}</div>
      <div style={{ ...s.slCardVal, color: accent, fontSize: small ? 18 : 22 }}>{value}</div>
      {sub && <div style={s.slCardSub}>{sub}</div>}
    </div>
  )
}

const s = {
  page: { padding: '12px 10px', maxWidth: 1000, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 12 },
  loadWrap: { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '60vh', gap: 20 },
  spinner: { width: 36, height: 36, border: '2px solid rgba(0,212,255,0.1)', borderTop: '2px solid #00d4ff', borderRadius: '50%', animation: 'spin 1s linear infinite' },
  loadText: { fontFamily: "'Orbitron',monospace", fontSize: 11, color: 'rgba(0,212,255,0.4)', letterSpacing: 3 },
  errBox: { padding: 16, background: 'rgba(255,32,64,0.08)', border: '1px solid rgba(255,32,64,0.3)', color: '#ff6070', borderRadius: 1, margin: 24 },
  pageHeader: { display: 'flex', alignItems: 'center', gap: 16 },
  pageTag: { fontFamily: "'Orbitron',monospace", fontSize: 11, color: 'rgba(0,212,255,0.5)', letterSpacing: 4, whiteSpace: 'nowrap' },
  headerLine: { flex: 1, height: 1, background: 'linear-gradient(90deg,rgba(0,212,255,0.3),transparent)' },
  metricGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(100px,1fr))', gap: 8 },
  weekGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(90px,1fr))', gap: 8, marginBottom: 12 },
  slCard: { padding: '12px 16px', background: 'rgba(4,12,30,0.85)', border: '1px solid', borderRadius: 2 },
  slCardLabel: { fontFamily: "'Orbitron',monospace", fontSize: 8, letterSpacing: 2, marginBottom: 6 },
  slCardVal: { fontFamily: "'Orbitron',monospace", fontWeight: 800 },
  slCardSub: { fontFamily: "'Orbitron',monospace", fontSize: 8, color: 'rgba(0,212,255,0.3)', letterSpacing: 1, marginTop: 2 },
  panel: { padding: '18px 20px', background: 'rgba(4,12,30,0.9)', border: '1px solid rgba(0,212,255,0.18)', borderRadius: 2 },
  panelHeader: { marginBottom: 16 },
  panelTag: { fontFamily: "'Orbitron',monospace", fontSize: 10, color: 'rgba(0,212,255,0.5)', letterSpacing: 3 },
  statList: { display: 'flex', flexDirection: 'column', gap: 10 },
  statRow: { display: 'flex', alignItems: 'center', gap: 12 },
  statLbl: { fontFamily: "'Orbitron',monospace", fontSize: 10, fontWeight: 700, width: 34, letterSpacing: 1 },
  statBarBg: { flex: 1, height: 6, background: 'rgba(255,255,255,0.04)', borderRadius: 1, overflow: 'hidden' },
  statBarFill: { height: '100%', borderRadius: 1, transition: 'width 0.5s ease' },
  statVal: { fontFamily: "'Orbitron',monospace", fontSize: 11, fontWeight: 700, width: 40, textAlign: 'right' },
  statMeta: { display: 'flex', gap: 24, marginTop: 14, flexWrap: 'wrap' },
  statMetaItem: { fontFamily: "'Orbitron',monospace", fontSize: 9, color: 'rgba(0,212,255,0.4)', letterSpacing: 1.5 },
  chart: { marginTop: 8 },
  chartTitle: { fontFamily: "'Orbitron',monospace", fontSize: 9, color: 'rgba(0,212,255,0.4)', letterSpacing: 3, marginBottom: 12 },
  chartBars: { display: 'flex', gap: 8, alignItems: 'flex-end', height: 140 },
  chartCol: { flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 },
  chartVal: { fontFamily: "'Orbitron',monospace", fontSize: 9, color: 'rgba(0,212,255,0.4)' },
  chartBarOuter: { width: '100%', flex: 1, background: 'rgba(0,212,255,0.05)', border: '1px solid rgba(0,212,255,0.08)', position: 'relative' },
  chartBarFill: { position: 'absolute', bottom: 0, left: 0, width: '100%', background: 'linear-gradient(180deg,#00d4ff,#0062ff60)', transition: 'height 0.5s ease' },
  chartDay: { fontFamily: "'Orbitron',monospace", fontSize: 8, color: 'rgba(0,212,255,0.3)' },
  streakRow: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 },
  streakCard: { padding: '12px 14px', background: 'rgba(4,12,30,0.85)', border: '1px solid rgba(0,212,255,0.15)', borderRadius: 2, display: 'flex', alignItems: 'center', gap: 12 },
  streakIcon: { fontSize: 28 },
  streakVal: { fontFamily: "'Orbitron',monospace", fontSize: 30, fontWeight: 900, color: '#e8f4ff' },
  streakLbl: { fontFamily: "'Orbitron',monospace", fontSize: 9, color: 'rgba(0,212,255,0.4)', letterSpacing: 2, marginTop: 4 },
}

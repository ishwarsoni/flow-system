/**
 * TrustProfileCard.jsx
 *
 * Displays the player's current trust tier, score, and key stats.
 * Shown in the player profile page.
 */
import React, { useEffect, useState } from 'react'
import { getTrustProfile } from '../api/verification'

const TIER_CONFIG = {
  low:    { label: 'Low Trust',    color: 'text-red-400',    bg: 'bg-red-900/20',    border: 'border-red-500/40',    bar: 'bg-red-500'    },
  normal: { label: 'Normal Trust', color: 'text-blue-400',   bg: 'bg-blue-900/20',   border: 'border-blue-500/40',   bar: 'bg-blue-500'   },
  high:   { label: 'High Trust',   color: 'text-green-400',  bg: 'bg-green-900/20',  border: 'border-green-500/40',  bar: 'bg-green-500'  },
}

function Stat({ label, value, valueClass = 'text-white' }) {
  return (
    <div className="text-center">
      <p className={`text-lg font-bold ${valueClass}`}>{value}</p>
      <p className="text-gray-500 text-xs">{label}</p>
    </div>
  )
}

export default function TrustProfileCard() {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getTrustProfile()
      .then(setProfile)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="bg-gray-900 border border-gray-700 rounded-2xl p-5 animate-pulse h-32" />
  )
  if (!profile) return null

  const tier = profile.trust_tier?.toLowerCase() ?? 'normal'
  const cfg  = TIER_CONFIG[tier] ?? TIER_CONFIG.normal
  const pct  = Math.round(profile.trust_score)

  const successRate = profile.total_sessions > 0
    ? Math.round((profile.verified_sessions / profile.total_sessions) * 100)
    : 0

  return (
    <div className={`rounded-2xl border ${cfg.border} ${cfg.bg} p-5 space-y-4`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-gray-400 text-xs uppercase tracking-widest mb-0.5">Trust Level</p>
          <h3 className={`text-xl font-bold ${cfg.color}`}>{cfg.label}</h3>
        </div>
        <div className="text-right">
          <p className={`text-3xl font-bold ${cfg.color}`}>{pct}</p>
          <p className="text-gray-500 text-xs">/ 100</p>
        </div>
      </div>

      {/* Score bar */}
      <div className="w-full bg-gray-700 rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all ${cfg.bar}`}
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-4 gap-3 pt-1">
        <Stat label="Sessions"    value={profile.total_sessions} />
        <Stat label="Pass Rate"   value={`${successRate}%`}
              valueClass={successRate >= 70 ? 'text-green-400' : 'text-yellow-400'} />
        <Stat label="Hard Fails"  value={profile.hard_fail_count}
              valueClass={profile.hard_fail_count > 0 ? 'text-red-400' : 'text-green-400'} />
        <Stat label="Flags"       value={profile.flag_count}
              valueClass={profile.flag_count > 0 ? 'text-orange-400' : 'text-green-400'} />
      </div>

      {/* Audit mode warning */}
      {profile.audit_mode && (
        <div className="bg-red-900/30 border border-red-500/30 rounded-lg px-3 py-2">
          <p className="text-red-400 text-sm font-medium">⚠ Account in Audit Mode</p>
          <p className="text-gray-400 text-xs mt-0.5">
            All completions are heavily scrutinised. Build a consistent record to exit.
          </p>
        </div>
      )}

      {/* Tier explanation */}
      <p className="text-gray-500 text-xs leading-relaxed">
        {tier === 'low'    && 'All quests require output proof and random checks. Complete consistently to raise your score.'}
        {tier === 'normal' && 'Standard verification applies. 15% of sessions include a spot check.'}
        {tier === 'high'   && 'Light verification. Casual quests may skip output requirements. Keep it up.'}
      </p>
    </div>
  )
}

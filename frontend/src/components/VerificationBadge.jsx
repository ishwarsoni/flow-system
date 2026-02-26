/**
 * VerificationBadge.jsx
 *
 * Displays the outcome of the verification engine:
 *  - Score breakdown (time, output, consistency, behaviour)
 *  - Decision (PASS / SOFT_FAIL / HARD_FAIL / AUDIT)
 *  - XP awarded / penalised
 *  - Flags raised
 *  - Trust delta
 */
import React from 'react'

const DECISION_CONFIG = {
  pass:      { label: 'Verified ✓',       color: 'text-green-400',  border: 'border-green-500/40', bg: 'bg-green-900/20' },
  soft_fail: { label: 'Partial Credit',   color: 'text-yellow-400', border: 'border-yellow-500/40',bg: 'bg-yellow-900/20' },
  hard_fail: { label: 'Failed',           color: 'text-red-400',    border: 'border-red-500/40',   bg: 'bg-red-900/20' },
  audit:     { label: 'Under Review',     color: 'text-orange-400', border: 'border-orange-500/40',bg: 'bg-orange-900/20' },
}

function ScoreBar({ label, score }) {
  const pct = Math.round((score ?? 0) * 100)
  const color =
    pct >= 70 ? 'bg-green-500' :
    pct >= 45 ? 'bg-yellow-500' :
    'bg-red-500'
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-gray-400">
        <span>{label}</span>
        <span className={pct >= 60 ? 'text-green-400' : 'text-red-400'}>{pct}%</span>
      </div>
      <div className="w-full bg-gray-700 rounded-full h-1.5">
        <div className={`h-1.5 rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function VerificationBadge({ log }) {
  if (!log) return null

  const decision = log.decision?.toLowerCase() ?? 'hard_fail'
  const cfg      = DECISION_CONFIG[decision] ?? DECISION_CONFIG.hard_fail
  const totalPct = Math.round((log.verification_score ?? 0) * 100)

  return (
    <div className={`rounded-2xl border ${cfg.border} ${cfg.bg} p-5 space-y-5`}>

      {/* Decision header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-gray-400 text-xs uppercase tracking-widest mb-0.5">Result</p>
          <h3 className={`text-2xl font-bold ${cfg.color}`}>{cfg.label}</h3>
        </div>
        <div className="text-center">
          <p className={`text-4xl font-bold ${cfg.color}`}>{totalPct}</p>
          <p className="text-gray-500 text-xs">/ 100</p>
        </div>
      </div>

      {/* Score breakdown */}
      <div className="space-y-2.5">
        <ScoreBar label="Time Gate"   score={log.time_score} />
        <ScoreBar label="Output Proof" score={log.output_score} />
        <ScoreBar label="Consistency"  score={log.consistency_score} />
        <ScoreBar label="Behaviour"    score={log.behavior_score} />
      </div>

      {/* XP */}
      <div className="grid grid-cols-2 gap-3">
        {log.xp_awarded > 0 && (
          <div className="bg-green-900/30 border border-green-500/30 rounded-xl p-3 text-center">
            <p className="text-green-400 text-xl font-bold">+{log.xp_awarded} XP</p>
            <p className="text-gray-400 text-xs">Awarded</p>
          </div>
        )}
        {log.xp_penalty > 0 && (
          <div className="bg-red-900/30 border border-red-500/30 rounded-xl p-3 text-center">
            <p className="text-red-400 text-xl font-bold">−{log.xp_penalty} XP</p>
            <p className="text-gray-400 text-xs">Penalty</p>
          </div>
        )}
      </div>

      {/* Trust delta */}
      {log.trust_delta !== 0 && (
        <div className="flex items-center gap-2 text-sm">
          <span className="text-gray-400">Trust:</span>
          <span className={log.trust_delta > 0 ? 'text-green-400' : 'text-red-400'}>
            {log.trust_delta > 0 ? '+' : ''}{log.trust_delta.toFixed(1)}
          </span>
          {log.trust_score_after !== null && (
            <span className="text-gray-500 text-xs">→ {log.trust_score_after.toFixed(0)}</span>
          )}
        </div>
      )}

      {/* Failure reason */}
      {log.failure_reason && (
        <p className="text-red-400 text-sm bg-red-900/20 border border-red-500/20 rounded-lg p-3">
          {log.failure_reason}
        </p>
      )}

      {/* Flags */}
      {log.flags_raised?.length > 0 && (
        <div>
          <p className="text-gray-500 text-xs mb-1.5">Flags raised:</p>
          <div className="flex flex-wrap gap-1.5">
            {log.flags_raised.map(f => (
              <span key={f} className="px-2 py-0.5 bg-orange-900/30 border border-orange-500/30
                                       rounded-full text-orange-400 text-xs">
                {f.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Reward multiplier */}
      {log.reward_multiplier < 1 && log.reward_multiplier > 0 && (
        <p className="text-yellow-400 text-xs">
          ⚡ Partial reward applied ({Math.round(log.reward_multiplier * 100)}%)
        </p>
      )}
    </div>
  )
}

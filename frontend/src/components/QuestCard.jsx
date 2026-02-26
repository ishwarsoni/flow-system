/**
 * QuestCard.jsx — Mobile-first quest card with accordion details
 *
 * - Compact by default on mobile: title + domain + tier + XP visible
 * - Tap to expand description + metadata + actions
 * - Touch targets ≥ 44px for all interactive elements
 * - Wrapped in React.memo to avoid unnecessary re-renders in lists
 */
import React, { useState, memo, useCallback } from 'react'

const DOMAIN_CONFIG = {
  mind:     { icon: '◈', color: '#00d4ff', label: 'MIND' },
  body:     { icon: '⚡', color: '#ff2040', label: 'BODY' },
  core:     { icon: '◉', color: '#00ff88', label: 'CORE' },
  control:  { icon: '◆', color: '#7c3aed', label: 'CONTROL' },
  presence: { icon: '◇', color: '#ffd700', label: 'PRESENCE' },
  system:   { icon: '⬡', color: '#e2e8f0', label: 'SYSTEM' },
}

const TIER_CONFIG = {
  easy:         { color: '#00ff88', label: 'EASY',    rank: 'F' },
  intermediate: { color: '#00d4ff', label: 'INTER',   rank: 'C' },
  hard:         { color: '#ffd700', label: 'HARD',    rank: 'A' },
  extreme:      { color: '#ff2040', label: 'EXTREME', rank: 'S' },
  trivial:      { color: '#475569', label: 'TRIVIAL', rank: '-' },
  medium:       { color: '#00d4ff', label: 'MEDIUM',  rank: 'C' },
}

const STATUS_CONFIG = {
  pending:     { color: '#94a3b8', label: 'PENDING',     icon: '○' },
  in_progress: { color: '#00d4ff', label: 'IN PROGRESS', icon: '◎' },
  completed:   { color: '#00ff88', label: 'COMPLETED',   icon: '✓' },
  failed:      { color: '#ff2040', label: 'FAILED',      icon: '✗' },
  expired:     { color: '#ff2040', label: 'EXPIRED',     icon: '⊘' },
  abandoned:   { color: '#475569', label: 'ABANDONED',   icon: '—' },
}

const QuestCard = memo(function QuestCard({
  quest,
  onComplete,
  onFail,
  onDelete,
  onSubmitMetrics,
  isActionsDisabled = false,
}) {
  const [expanded, setExpanded] = useState(false)
  const [metricsOpen, setMetricsOpen] = useState(false)
  const [metricsInput, setMetricsInput] = useState('')

  const domain = DOMAIN_CONFIG[quest.domain] || { icon: '?', color: '#475569', label: quest.domain?.toUpperCase() || 'UNKNOWN' }
  const tier = TIER_CONFIG[quest.difficulty] || TIER_CONFIG.easy
  const statusCfg = STATUS_CONFIG[quest.status] || STATUS_CONFIG.pending

  const isActive = quest.status === 'pending' || quest.status === 'in_progress'
  const canDelete = quest.is_manual && quest.status === 'pending'
  const needsMetrics = quest.metrics_required && !quest.metrics_submitted && isActive
  const canComplete = isActive && (!quest.metrics_required || quest.metrics_submitted)

  const handleMetricsSubmit = useCallback(() => {
    if (!metricsInput.trim()) return
    try {
      const parsed = JSON.parse(metricsInput)
      onSubmitMetrics?.(quest.id, parsed)
      setMetricsOpen(false)
      setMetricsInput('')
    } catch {
      const pairs = {}
      metricsInput.split(',').forEach(part => {
        const [k, v] = part.split('=').map(s => s.trim())
        if (k && v) pairs[k] = isNaN(Number(v)) ? v : Number(v)
      })
      if (Object.keys(pairs).length > 0) {
        onSubmitMetrics?.(quest.id, pairs)
        setMetricsOpen(false)
        setMetricsInput('')
      }
    }
  }, [metricsInput, onSubmitMetrics, quest.id])

  const effectiveXP = Math.round(quest.base_xp_reward * (quest.performance_multiplier || 1.0))

  const toggleExpand = useCallback(() => setExpanded(v => !v), [])

  return (
    <div className="qc-card" style={{
      borderColor: isActive ? tier.color + '44' : '#1e293b',
      boxShadow: isActive ? `inset 0 0 30px ${tier.color}08` : 'none',
    }}>
      {/* ── Compact header — always visible, tappable ─── */}
      <button
        type="button"
        className="qc-header"
        onClick={toggleExpand}
        aria-expanded={expanded}
      >
        <div className="qc-header-left">
          <span className="qc-domain-icon" style={{ color: domain.color }}>{domain.icon}</span>
          <div className="qc-header-text">
            <h3 className="qc-title">{quest.title}</h3>
            <div className="qc-header-meta">
              <span className="qc-badge-inline" style={{ color: domain.color }}>{domain.label}</span>
              <span className="qc-badge-inline" style={{ color: tier.color }}>{tier.rank}</span>
              <span className="qc-badge-inline" style={{ color: '#ffd700' }}>+{effectiveXP}</span>
              {quest.is_manual && <span className="qc-badge-inline" style={{ color: '#64748b' }}>M</span>}
            </div>
          </div>
        </div>
        <div className="qc-header-right">
          <span className="qc-status-dot" style={{ background: statusCfg.color }} />
          <span className="qc-chevron" data-open={expanded}>▾</span>
        </div>
      </button>

      {/* ── Expanded body — accordion ─── */}
      {expanded && (
        <div className="qc-body">
          {/* Description */}
          {quest.description && (
            <p className="qc-desc">{quest.description}</p>
          )}

          {/* Metadata badges */}
          <div className="qc-badges">
            <span className="qc-badge" style={badgeColor('#ffd700')}>+{effectiveXP} XP</span>
            <span className="qc-badge" style={badgeColor(tier.color)}>{tier.label} [{tier.rank}]</span>
            <span className="qc-badge" style={badgeColor(statusCfg.color)}>{statusCfg.icon} {statusCfg.label}</span>

            {quest.time_limit_minutes && (
              <span className="qc-badge" style={badgeColor('#00d4ff')}>
                ⏱ {quest.time_limit_minutes}m
                {quest.max_duration_minutes && ` / ${quest.max_duration_minutes}m`}
              </span>
            )}
            {!quest.time_limit_minutes && quest.max_duration_minutes && (
              <span className="qc-badge" style={badgeColor('#00d4ff')}>⏱ max {quest.max_duration_minutes}m</span>
            )}

            {quest.metrics_required && (
              <span className="qc-badge" style={badgeColor(quest.metrics_submitted ? '#00ff88' : '#ffd700')}>
                {quest.metrics_submitted ? '✓ METRICS' : '⚡ METRICS REQ'}
              </span>
            )}

            <span className="qc-badge" style={badgeColor('#94a3b8')}>
              {quest.verification_type === 'metrics' ? '📊 METRICS' : quest.verification_type === 'output' ? '📝 OUTPUT' : '📋 LOG'}
            </span>

            {quest.cooldown_hours > 0 && (
              <span className="qc-badge" style={badgeColor('#ff2040')}>{quest.cooldown_hours}H CD</span>
            )}
            {quest.weekly_limit && (
              <span className="qc-badge" style={badgeColor('#ff2040')}>{quest.weekly_limit}/WK</span>
            )}
            {quest.metrics_verified === true && <span className="qc-badge" style={badgeColor('#00ff88')}>✓ VERIFIED</span>}
            {quest.metrics_verified === false && <span className="qc-badge" style={badgeColor('#ff2040')}>✗ REJECTED</span>}
            {quest.metrics_submitted && quest.metrics_verified === null && <span className="qc-badge" style={badgeColor('#ffd700')}>⏳ REVIEW</span>}
          </div>

          {/* Metrics submission */}
          {needsMetrics && (
            <div className="qc-metrics-section">
              {!metricsOpen ? (
                <button onClick={() => setMetricsOpen(true)} className="qc-action-btn" style={actionColor('#ffd700')}>
                  📊 SUBMIT METRICS
                </button>
              ) : (
                <div className="qc-metrics-form">
                  <div className="qc-metrics-hint">FORMAT: key=value, key=value  OR  JSON</div>
                  <textarea
                    value={metricsInput}
                    onChange={e => setMetricsInput(e.target.value)}
                    placeholder='push_ups=80, pull_ups=25, sets=4'
                    rows={2}
                    className="qc-metrics-input"
                  />
                  <div className="qc-metrics-btns">
                    <button onClick={handleMetricsSubmit} className="qc-action-btn" style={actionColor('#00ff88')}>SUBMIT</button>
                    <button onClick={() => setMetricsOpen(false)} className="qc-action-btn" style={actionColor('#475569')}>CANCEL</button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Action buttons */}
          {isActive && (
            <div className="qc-actions">
              {canComplete && (
                <button
                  onClick={() => onComplete?.(quest.id)}
                  disabled={isActionsDisabled}
                  className="qc-action-btn qc-action-btn--complete"
                  style={actionColor('#00ff88')}
                >
                  ✓ COMPLETE
                </button>
              )}
              <button
                onClick={() => onFail?.(quest.id)}
                disabled={isActionsDisabled}
                className="qc-action-btn qc-action-btn--fail"
                style={actionColor('#ff2040')}
              >
                ✗ FAIL
              </button>
              {canDelete && (
                <button
                  onClick={() => onDelete?.(quest.id)}
                  disabled={isActionsDisabled}
                  className="qc-action-btn qc-action-btn--delete"
                  style={actionColor('#ff2040')}
                >
                  🗑 DELETE
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
})

export default QuestCard

/* Inline style helpers — only used for dynamic color props */
function badgeColor(color) {
  return {
    color,
    borderColor: color + '30',
    backgroundColor: color + '10',
  }
}

function actionColor(color) {
  return {
    color,
    borderColor: color + '44',
    backgroundColor: color + '10',
  }
}

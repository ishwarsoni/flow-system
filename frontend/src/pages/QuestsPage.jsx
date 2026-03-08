/**
 * QuestsPage.jsx
 *
 * Main quest management page for FLOW.
 * Features:
 *   - Quest list with filterable cards showing all FLOW metadata
 *   - Manual quest creation form (collapsible)
 *   - Status filters (all, pending, in_progress, completed, failed)
 *   - Quest actions: complete, fail, delete (manual only), submit metrics
 */
import React, { useState, useEffect, useCallback } from 'react'
import QuestCard from '../components/QuestCard'
import ManualQuestForm from '../components/ManualQuestForm'
import GenerateQuestPanel from '../components/GenerateQuestPanel'
import { questsAPI, playerAPI } from '../api'

const STATUS_FILTERS = [
  { key: null, label: 'ACTIVE' },     // Default — pending + in_progress only
  { key: 'completed', label: 'DONE' },
  { key: 'failed', label: 'FAILED' },
  { key: 'expired', label: 'EXPIRED' },
]

export default function QuestsPage() {
  const [quests, setQuests] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [statusFilter, setStatusFilter] = useState(null)
  const [panelMode, setPanelMode] = useState(null) // 'generate' | 'manual' | null
  const [createError, setCreateError] = useState(null)
  const [isCreating, setIsCreating] = useState(false)
  const [actionLoading, setActionLoading] = useState(null) // quest id being acted on
  const [toast, setToast] = useState(null)
  const [allowedDifficulties, setAllowedDifficulties] = useState(['easy'])
  const [defaultsCleared, setDefaultsCleared] = useState(false)
  const [clearingDefaults, setClearingDefaults] = useState(false)

  // ── Load profile for allowed difficulties ───────────────────────────────────
  useEffect(() => {
    playerAPI.getProfile().then(res => {
      const ad = res.data?.allowed_difficulties
      if (ad && ad.length) setAllowedDifficulties(ad)
    }).catch(() => { })
  }, [])

  // ── Load quests ─────────────────────────────────────────────────────────────
  const loadQuests = useCallback(async (skipAutoGen = false) => {
    setLoading(true)
    setError(null)
    try {
      const params = {}
      if (statusFilter) params.status = statusFilter
      if (skipAutoGen || defaultsCleared) params.skip_auto_generate = true
      const res = await questsAPI.list(params)
      setQuests(res.data.items)
      setTotal(res.data.total)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to load quests')
    } finally {
      setLoading(false)
    }
  }, [statusFilter, defaultsCleared])

  useEffect(() => { loadQuests() }, [loadQuests])
  useEffect(() => { if (!toast) return; const t = setTimeout(() => setToast(null), 4000); return () => clearTimeout(t) }, [toast])

  // ── Create quest ────────────────────────────────────────────────────────────
  const handleCreate = useCallback(async (data) => {
    setIsCreating(true)
    setCreateError(null)
    try {
      await questsAPI.create(data)
      setToast({ type: 'success', message: `Quest created: ${data.title}` })
      setPanelMode(null)
      loadQuests()
    } catch (err) {
      setCreateError(err?.response?.data?.detail || 'Failed to create quest')
    } finally {
      setIsCreating(false)
    }
  }, [loadQuests])

  // ── Complete quest ──────────────────────────────────────────────────────────
  const handleComplete = useCallback(async (questId) => {
    setActionLoading(questId)
    try {
      const res = await questsAPI.complete(questId)
      const xp = res.data.xp_earned || 0
      setToast({ type: 'success', message: `Quest completed! +${xp} XP earned.` })
      loadQuests()
    } catch (err) {
      setToast({ type: 'error', message: err?.response?.data?.detail || 'Completion failed' })
    } finally {
      setActionLoading(null)
    }
  }, [loadQuests])

  // ── Fail quest ──────────────────────────────────────────────────────────────
  const handleFail = useCallback(async (questId) => {
    setActionLoading(questId)
    try {
      await questsAPI.fail(questId)
      setToast({ type: 'error', message: 'Quest failed. Penalties applied.' })
      loadQuests()
    } catch (err) {
      setToast({ type: 'error', message: err?.response?.data?.detail || 'Failed to mark quest' })
    } finally {
      setActionLoading(null)
    }
  }, [loadQuests])

  // ── Delete quest ────────────────────────────────────────────────────────────
  const handleDelete = useCallback(async (questId) => {
    setActionLoading(questId)
    try {
      await questsAPI.delete(questId)
      setToast({ type: 'success', message: 'Quest removed.' })
      loadQuests()
    } catch (err) {
      setToast({ type: 'error', message: err?.response?.data?.detail || 'Delete failed' })
    } finally {
      setActionLoading(null)
    }
  }, [loadQuests])

  // ── Submit metrics ──────────────────────────────────────────────────────────
  const handleSubmitMetrics = useCallback(async (questId, metrics) => {
    setActionLoading(questId)
    try {
      await questsAPI.submitMetrics(questId, metrics)
      setToast({ type: 'success', message: 'Metrics submitted. Quest eligible for completion.' })
      loadQuests()
    } catch (err) {
      setToast({ type: 'error', message: err?.response?.data?.detail || 'Metrics submission failed' })
    } finally {
      setActionLoading(null)
    }
  }, [loadQuests])

  // ── Clear default quests ────────────────────────────────────────────────────
  const handleClearDefaults = useCallback(async () => {
    setClearingDefaults(true)
    try {
      const res = await questsAPI.clearDefaults()
      const count = res.data?.deleted_count || 0
      setDefaultsCleared(true)
      setToast({ type: 'success', message: `${count} default quest(s) cleared. Create your own quests now.` })
      setPanelMode('manual')
      loadQuests(true)
    } catch (err) {
      setToast({ type: 'error', message: err?.response?.data?.detail || 'Failed to clear defaults' })
    } finally {
      setClearingDefaults(false)
    }
  }, [loadQuests])

  // ── Count manual quests ─────────────────────────────────────────────────────
  const manualCount = quests.filter(q => q.is_manual).length

  return (
    <div className="qp-container">
      {/* Toast */}
      {toast && <Toast toast={toast} />}

      {/* Header */}
      <div className="qp-inner">
        <div className="qp-header">
          <div>
            <div style={{ color: '#ffd700', fontSize: 11, letterSpacing: '0.2em', fontWeight: 700, marginBottom: 4, fontFamily: "'Orbitron',monospace" }}>
              SYSTEM / QUEST REGISTRY
            </div>
            <h1 className="qp-header-title">QUEST OPERATIONS</h1>
          </div>
          <div className="qp-header-actions">
            <span className="qp-stats">{total} TOTAL · {manualCount} MANUAL</span>
            <button
              onClick={() => setPanelMode(panelMode === 'generate' ? null : 'generate')}
              className="qp-header-btn"
              style={{
                background: panelMode === 'generate' ? '#ff204018' : '#00ff8818',
                borderColor: panelMode === 'generate' ? '#ff204044' : '#00ff8844',
                color: panelMode === 'generate' ? '#ff2040' : '#00ff88',
              }}
            >
              {panelMode === 'generate' ? '✗ CLOSE' : '◆ GENERATE'}
            </button>
            <button
              onClick={() => setPanelMode(panelMode === 'manual' ? null : 'manual')}
              className="qp-header-btn"
              style={{
                borderColor: panelMode === 'manual' ? '#ff204044' : '#ffd70044',
                background: panelMode === 'manual' ? '#ff204018' : '#ffd70018',
                color: panelMode === 'manual' ? '#ff2040' : '#ffd700',
              }}
            >
              {panelMode === 'manual' ? '✗ CLOSE' : '+ MANUAL'}
            </button>
            {/* Clear all default/system quests */}
            {quests.some(q => !q.is_manual) && (
              <button
                onClick={handleClearDefaults}
                disabled={clearingDefaults}
                className="qp-header-btn"
                style={{
                  background: clearingDefaults ? '#1e293b' : '#ff204018',
                  borderColor: '#ff204044',
                  color: clearingDefaults ? '#475569' : '#ff2040',
                  cursor: clearingDefaults ? 'wait' : 'pointer',
                }}
              >
                {clearingDefaults ? '...' : '✕ CLEAR DEFAULTS'}
              </button>
            )}
            <button
              onClick={() => loadQuests()}
              disabled={loading}
              className="qp-header-btn"
              style={{
                background: 'transparent',
                borderColor: '#1e293b',
                color: loading ? '#475569' : '#94a3b8',
                cursor: loading ? 'wait' : 'pointer',
              }}
            >
              {loading ? '...' : '↺'}
            </button>
          </div>
        </div>
      </div>

      {/* Generate panel */}
      {panelMode === 'generate' && (
        <div className="qp-inner" style={{ marginBottom: 16 }}>
          <GenerateQuestPanel
            allowedDifficulties={allowedDifficulties}
            onGenerated={() => {
              setToast({ type: 'success', message: 'Quest generated from template.' })
              setPanelMode(null)
              loadQuests()
            }}
            onClose={() => setPanelMode(null)}
          />
        </div>
      )}

      {/* Manual create form */}
      {panelMode === 'manual' && (
        <div className="qp-inner" style={{ marginBottom: 16 }}>
          <ManualQuestForm
            onSubmit={handleCreate}
            isSubmitting={isCreating}
            error={createError}
          />
        </div>
      )}

      {/* Status filters — horizontally scrollable on mobile */}
      <div className="qp-inner" style={{ marginBottom: 12 }}>
        <div className="qp-filters">
          {STATUS_FILTERS.map(f => (
            <button
              key={f.label}
              onClick={() => setStatusFilter(f.key)}
              className={`qp-filter-btn ${statusFilter === f.key ? 'qp-filter-btn--active' : ''}`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Quest list */}
      <div className="qp-inner">
        {loading && (
          <div className="qp-skeleton-list">
            {[1, 2, 3].map(i => <div key={i} className="qp-skeleton-card skeleton" />)}
          </div>
        )}

        {error && !loading && (
          <div style={{
            background: '#0d0d14', border: '1px solid #ff204044', borderRadius: 6,
            padding: 20, color: '#ff2040', fontSize: 12, letterSpacing: '0.08em', textAlign: 'center',
          }}>
            <div style={{ marginBottom: 8, fontSize: 18 }}>✗</div>
            {error}
            <div style={{ marginTop: 12 }}>
              <button onClick={loadQuests} className="qp-header-btn" style={{ borderColor: '#ff204044', color: '#ff2040', background: '#ff204018' }}>
                RETRY
              </button>
            </div>
          </div>
        )}

        {!loading && !error && quests.length === 0 && (
          <div className="qp-empty">
            <div style={{ fontSize: 24, marginBottom: 12 }}>○</div>
            {statusFilter
              ? `No ${statusFilter.replace('_', ' ').toUpperCase()} quests found.`
              : defaultsCleared
                ? 'All defaults cleared. Create your own quests below.'
                : 'No quests in your registry. Generate one above.'
            }
            {/* Auto-show manual quest creation when defaults were cleared */}
            {!statusFilter && (defaultsCleared || panelMode === null) && quests.length === 0 && !loading && (
              <div style={{ marginTop: 20, width: '100%' }}>
                {panelMode !== 'manual' ? (
                  <button
                    onClick={() => setPanelMode('manual')}
                    style={{
                      background: '#ffd70018',
                      border: '1px solid #ffd70066',
                      color: '#ffd700',
                      padding: '12px 28px',
                      borderRadius: 4,
                      cursor: 'pointer',
                      fontFamily: 'monospace',
                      fontSize: 13,
                      fontWeight: 700,
                      letterSpacing: '0.15em',
                    }}
                  >
                    + CREATE MANUAL QUEST
                  </button>
                ) : null}
              </div>
            )}
          </div>
        )}

        {!loading && !error && quests.length > 0 && (
          <div className="qp-list">
            {quests.map(quest => (
              <QuestCard
                key={quest.id}
                quest={quest}
                onComplete={handleComplete}
                onFail={handleFail}
                onDelete={handleDelete}
                onSubmitMetrics={handleSubmitMetrics}
                isActionsDisabled={actionLoading === quest.id}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function Toast({ toast }) {
  const bg = toast.type === 'success' ? '#00ff88' : toast.type === 'error' ? '#ff2040' : '#00d4ff'
  return (
    <div className="qp-toast" style={{ borderColor: bg, color: bg, boxShadow: `0 0 24px ${bg}40` }}>
      {toast.message}
    </div>
  )
}

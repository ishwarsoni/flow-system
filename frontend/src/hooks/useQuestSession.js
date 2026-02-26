/**
 * useQuestSession.js
 *
 * Central hook for managing a quest's verification lifecycle:
 *   1. Starts a session (POST /quests/{id}/start)
 *   2. Sends heartbeats every 30 s (PATCH …/session/heartbeat)
 *   3. Fetches verification status on demand
 *   4. Orchestrates submit flow (POST …/submit)
 *   5. Exposes state for output form + spot-check modal
 *
 * States: idle → active → submitting → result
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import {
  startQuest,
  sendHeartbeat,
  getVerificationStatus,
  submitQuest,
  completeQuest,
  getSpotCheckPrompt,
} from '../api/verification'
import { useActivityTracker } from './useActivityTracker'

const HEARTBEAT_INTERVAL_MS = 30_000  // 30 s

export function useQuestSession(questId) {
  const [phase, setPhase]               = useState('idle')    // idle|active|submitting|result
  const [session, setSession]           = useState(null)
  const [verificationStatus, setStatus] = useState(null)
  const [verificationResult, setResult] = useState(null)
  const [spotCheckPrompt, setSpotPrompt]= useState(null)
  const [error, setError]               = useState(null)
  const [elapsedSec, setElapsedSec]     = useState(0)

  const heartbeatRef  = useRef(null)
  const elapsedRef    = useRef(null)
  const startTimeRef  = useRef(null)

  const { consumeDeltas } = useActivityTracker()

  // ── Start ───────────────────────────────────────────────────────────────
  const start = useCallback(async () => {
    if (phase !== 'idle') return
    setError(null)
    try {
      const sess = await startQuest(questId)
      setSession(sess)
      setPhase('active')
      startTimeRef.current = Date.now()

      // Fetch spot-check prompt if needed
      if (sess.requires_spot_check) {
        try {
          const sp = await getSpotCheckPrompt(questId)
          setSpotPrompt(sp.prompt)
        } catch {
          // Prompt fetched lazily on submit if this fails
        }
      }

      // Heartbeat interval
      heartbeatRef.current = setInterval(async () => {
        const deltas = consumeDeltas()
        try {
          const updated = await sendHeartbeat(questId, deltas)
          setSession(updated)
        } catch {}
      }, HEARTBEAT_INTERVAL_MS)

      // Elapsed timer (1 s granularity)
      elapsedRef.current = setInterval(() => {
        setElapsedSec(Math.floor((Date.now() - startTimeRef.current) / 1000))
      }, 1000)

    } catch (e) {
      setError(e?.response?.data?.detail ?? 'Failed to start quest.')
    }
  }, [questId, phase, consumeDeltas])

  // ── Submit ──────────────────────────────────────────────────────────────
  const submit = useCallback(async ({ selfRating } = {}) => {
    if (phase !== 'active') return
    setPhase('submitting')
    setError(null)

    // Final heartbeat flush
    clearInterval(heartbeatRef.current)
    clearInterval(elapsedRef.current)
    const finalDeltas = consumeDeltas()

    try {
      const log = await submitQuest(questId, {
        finalActiveSec: (session?.active_time_sec ?? 0) + finalDeltas.active,
        finalIdleSec:   (session?.idle_time_sec   ?? 0) + finalDeltas.idle,
        selfRating,
      })
      setResult(log)
      setPhase('result')
    } catch (e) {
      setError(e?.response?.data?.detail ?? 'Submission failed.')
      setPhase('active')
    }
  }, [questId, phase, session, consumeDeltas])

  // ── Refresh status ──────────────────────────────────────────────────────
  const refreshStatus = useCallback(async () => {
    try {
      const s = await getVerificationStatus(questId)
      setStatus(s)
      return s
    } catch {}
  }, [questId])

  // ── Cleanup ─────────────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      clearInterval(heartbeatRef.current)
      clearInterval(elapsedRef.current)
    }
  }, [])

  // ── Derived helpers ─────────────────────────────────────────────────────
  const expectedSec   = session?.expected_duration_sec ?? 0
  const progressPct   = expectedSec > 0
    ? Math.min(100, Math.round((elapsedSec / expectedSec) * 100))
    : 0
  const windowEnd     = session?.window_end ? new Date(session.window_end) : null
  const requiresOutput      = session?.requires_output      ?? false
  const requiresSpotCheck   = session?.requires_spot_check  ?? false

  return {
    // state
    phase,
    session,
    verificationStatus,
    verificationResult,
    spotCheckPrompt,
    error,
    elapsedSec,
    expectedSec,
    progressPct,
    windowEnd,
    requiresOutput,
    requiresSpotCheck,
    // actions
    start,
    submit,
    refreshStatus,
  }
}

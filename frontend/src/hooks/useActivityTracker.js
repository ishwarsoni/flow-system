/**
 * useActivityTracker.js
 *
 * Tracks user interaction signals to distinguish genuine work from idle time.
 * Accumulates delta counters that are sent to the backend on each heartbeat.
 *
 * Signals tracked (no invasive data — GDPR-compliant):
 *  - active time (keystrokes, mouse movement, scroll, clicks)
 *  - idle time (no interaction for > 30 s)
 *  - tab-hidden time (Page Visibility API)
 *  - app-background time (visibilitychange)
 *
 * Usage:
 *   const { deltasRef, resetDeltas } = useActivityTracker()
 *   // deltasRef.current = { active, idle, tabHidden, appBg }
 */
import { useEffect, useRef, useCallback } from 'react'

const IDLE_THRESHOLD_MS = 30_000  // 30 seconds of no interaction = idle

export function useActivityTracker() {
  const deltasRef = useRef({ active: 0, idle: 0, tabHidden: 0, appBg: 0 })
  const lastEventRef     = useRef(Date.now())
  const lastTickRef      = useRef(Date.now())
  const idleRef          = useRef(false)
  const tabHiddenRef     = useRef(false)
  const tickerRef        = useRef(null)

  // Mark interaction
  const onInteraction = useCallback(() => {
    const now = Date.now()
    // If coming back from idle, credit any missed active time
    if (idleRef.current) {
      idleRef.current = false
    }
    lastEventRef.current = now
  }, [])

  // Tick every second — categorise the second as active, idle, or hidden
  const tick = useCallback(() => {
    const now = Date.now()
    const elapsed = (now - lastTickRef.current) / 1000  // seconds
    lastTickRef.current = now

    if (tabHiddenRef.current) {
      deltasRef.current.tabHidden += elapsed
      deltasRef.current.appBg    += elapsed
      return
    }

    const sinceLastEvent = now - lastEventRef.current
    if (sinceLastEvent > IDLE_THRESHOLD_MS) {
      idleRef.current = true
      deltasRef.current.idle   += elapsed
    } else {
      deltasRef.current.active += elapsed
    }
  }, [])

  // Reset and return a snapshot of accumulated deltas
  const consumeDeltas = useCallback(() => {
    const snap = {
      active:    Math.round(deltasRef.current.active),
      idle:      Math.round(deltasRef.current.idle),
      tabHidden: Math.round(deltasRef.current.tabHidden),
      appBg:     Math.round(deltasRef.current.appBg),
    }
    deltasRef.current = { active: 0, idle: 0, tabHidden: 0, appBg: 0 }
    return snap
  }, [])

  useEffect(() => {
    // Interaction listeners
    const events = ['mousemove', 'keydown', 'keyup', 'scroll', 'click', 'touchstart']
    events.forEach(e => window.addEventListener(e, onInteraction, { passive: true }))

    // Page visibility
    const onVisibilityChange = () => {
      tabHiddenRef.current = document.hidden
    }
    document.addEventListener('visibilitychange', onVisibilityChange)

    // Ticker
    tickerRef.current = setInterval(tick, 1000)

    return () => {
      events.forEach(e => window.removeEventListener(e, onInteraction))
      document.removeEventListener('visibilitychange', onVisibilityChange)
      clearInterval(tickerRef.current)
    }
  }, [onInteraction, tick])

  return { deltasRef, consumeDeltas }
}

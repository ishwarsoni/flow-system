/**
 * verification.js — API client for the Quest Verification System.
 * All quest lifecycle calls go through here.
 */
import client from './client'

// ── Session ──────────────────────────────────────────────────────────────────

/** POST /quests/{id}/start */
export const startQuest = (questId, { deviceId, userAgent } = {}) =>
  client.post(`/quests/${questId}/start`, {
    device_id: deviceId,
    user_agent: userAgent || navigator.userAgent,
  }).then(r => r.data)

/** PATCH /quests/{id}/session/heartbeat */
export const sendHeartbeat = (questId, deltas) =>
  client.patch(`/quests/${questId}/session/heartbeat`, {
    active_delta_sec:  deltas.active   ?? 0,
    idle_delta_sec:    deltas.idle     ?? 0,
    tab_hidden_delta:  deltas.tabHidden ?? 0,
    app_bg_delta:      deltas.appBg    ?? 0,
  }).then(r => r.data)

/** GET /quests/{id}/verification */
export const getVerificationStatus = (questId) =>
  client.get(`/quests/${questId}/verification`).then(r => r.data)

/** GET /quests/{id}/verification/history */
export const getVerificationHistory = (questId) =>
  client.get(`/quests/${questId}/verification/history`).then(r => r.data)

// ── Output proof ──────────────────────────────────────────────────────────────

/** POST /quests/{id}/output */
export const submitOutput = (questId, payload) =>
  client.post(`/quests/${questId}/output`, payload).then(r => r.data)

// ── Spot-check ────────────────────────────────────────────────────────────────

/** GET /quests/{id}/spot-check */
export const getSpotCheckPrompt = (questId) =>
  client.get(`/quests/${questId}/spot-check`).then(r => r.data)

/** POST /quests/{id}/output (spot-check type) */
export const submitSpotCheck = (questId, { sessionId, responseText }) =>
  submitOutput(questId, {
    output_type:   'spot_check',
    response_text: responseText,
  })

// ── Submit / complete ─────────────────────────────────────────────────────────

/** POST /quests/{id}/submit */
export const submitQuest = (questId, { finalActiveSec, finalIdleSec, selfRating } = {}) =>
  client.post(`/quests/${questId}/submit`, {
    final_active_sec: finalActiveSec,
    final_idle_sec:   finalIdleSec,
    self_rating:      selfRating,
  }).then(r => r.data)

/** POST /quests/{id}/complete */
export const completeQuest = (questId) =>
  client.post(`/quests/${questId}/complete`).then(r => r.data)

// ── Trust profile ─────────────────────────────────────────────────────────────

/** GET /player/trust */
export const getTrustProfile = () =>
  client.get('/player/trust').then(r => r.data)

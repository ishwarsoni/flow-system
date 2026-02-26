/**
 * ActiveQuestPanel.jsx
 *
 * The main verification-aware quest interaction panel.
 * Drop this component anywhere a quest can be started/completed.
 *
 * Phases:
 *   idle       → "Start Quest" button
 *   active     → timer, activity tracking, output form, spot-check modal
 *   submitting → loading state
 *   result     → VerificationBadge with outcome
 *
 * Usage:
 *   <ActiveQuestPanel quest={quest} onClose={() => {}} />
 */
import React, { useState } from 'react'
import { useQuestSession } from '../hooks/useQuestSession'
import QuestTimer          from './QuestTimer'
import QuestOutputForm     from './QuestOutputForm'
import SpotCheckModal      from './SpotCheckModal'
import VerificationBadge   from './VerificationBadge'

export default function ActiveQuestPanel({ quest, onClose }) {
  const {
    phase, session, verificationResult,
    spotCheckPrompt, error,
    elapsedSec, expectedSec, progressPct, windowEnd,
    requiresOutput, requiresSpotCheck,
    start, submit,
  } = useQuestSession(quest.id)

  const [outputDone, setOutputDone]         = useState(false)
  const [spotCheckDone, setSpotCheckDone]   = useState(false)
  const [selfRating, setSelfRating]         = useState(null)
  const [showSpotCheck, setShowSpotCheck]   = useState(false)

  // Show spot-check modal when session is active and spot check required & not done
  const shouldShowSpotCheck =
    phase === 'active' &&
    requiresSpotCheck &&
    !spotCheckDone &&
    showSpotCheck

  const canSubmit =
    phase === 'active' &&
    (!requiresOutput || outputDone) &&
    (!requiresSpotCheck || spotCheckDone)

  const handleStart = async () => {
    await start()
  }

  const handleSubmit = async () => {
    // If spot check required but modal not yet triggered
    if (requiresSpotCheck && !spotCheckDone) {
      setShowSpotCheck(true)
      return
    }
    await submit({ selfRating })
  }

  // ── Idle phase ─────────────────────────────────────────────────────────────
  if (phase === 'idle') {
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 space-y-5 max-w-xl mx-auto">
        <QuestHeader quest={quest} />
        {error && <ErrorBanner msg={error} />}
        <button
          onClick={handleStart}
          className="w-full py-3 bg-blue-600 hover:bg-blue-500 rounded-xl font-semibold
                     text-white transition-colors text-sm"
        >
          Start Quest
        </button>
        <p className="text-gray-500 text-xs text-center">
          A verified session will open. Complete at least 60% of the expected duration
          and submit proof to earn full rewards.
        </p>
      </div>
    )
  }

  // ── Result phase ───────────────────────────────────────────────────────────
  if (phase === 'result') {
    return (
      <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 space-y-5 max-w-xl mx-auto">
        <QuestHeader quest={quest} />
        <VerificationBadge log={verificationResult} />
        <button
          onClick={onClose}
          className="w-full py-2.5 bg-gray-700 hover:bg-gray-600 rounded-xl text-sm
                     font-medium text-gray-200 transition-colors"
        >
          Close
        </button>
      </div>
    )
  }

  // ── Active / submitting phase ──────────────────────────────────────────────
  return (
    <>
      {/* Spot-check modal overlay */}
      {shouldShowSpotCheck && spotCheckPrompt && (
        <SpotCheckModal
          questId={quest.id}
          prompt={spotCheckPrompt}
          onPassed={() => { setSpotCheckDone(true); setShowSpotCheck(false) }}
          onFailed={() => { setShowSpotCheck(false) }}
        />
      )}

      <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 space-y-6 max-w-xl mx-auto">
        <QuestHeader quest={quest} />

        {/* Timer */}
        <div className="bg-gray-800 rounded-xl p-4">
          <QuestTimer
            elapsedSec={elapsedSec}
            expectedSec={expectedSec}
            windowEnd={windowEnd}
          />
        </div>

        {/* Verification requirements */}
        <div className="space-y-2">
          <RequirementRow
            done={!requiresSpotCheck || spotCheckDone}
            label="Spot Check"
            visible={requiresSpotCheck}
          />
          <RequirementRow
            done={!requiresOutput || outputDone}
            label="Output Proof"
            visible={requiresOutput}
          />
        </div>

        {/* Output form */}
        {requiresOutput && !outputDone && (
          <div className="bg-gray-800 rounded-xl p-4 space-y-3">
            <h4 className="text-sm font-semibold text-gray-200">📝 Submit Proof</h4>
            <QuestOutputForm
              questId={quest.id}
              required={requiresOutput}
              onSubmitted={() => setOutputDone(true)}
            />
          </div>
        )}

        {/* Self-rating */}
        {canSubmit && (
          <div>
            <p className="text-xs text-gray-400 mb-2">Optional: rate your effort (1–5)</p>
            <div className="flex gap-2">
              {[1,2,3,4,5].map(r => (
                <button
                  key={r}
                  onClick={() => setSelfRating(r === selfRating ? null : r)}
                  className={`w-9 h-9 rounded-full text-sm font-bold transition-colors ${
                    selfRating === r
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                  }`}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>
        )}

        {error && <ErrorBanner msg={error} />}

        {/* Submit button */}
        <button
          onClick={handleSubmit}
          disabled={phase === 'submitting'}
          className={`w-full py-3 rounded-xl font-semibold text-sm transition-colors
            ${canSubmit || (requiresSpotCheck && !spotCheckDone)
              ? 'bg-green-600 hover:bg-green-500 text-white'
              : 'bg-gray-700 text-gray-500 cursor-not-allowed'
            }`}
        >
          {phase === 'submitting'
            ? 'Verifying…'
            : requiresSpotCheck && !spotCheckDone
              ? '🔍 Answer Spot Check First'
              : requiresOutput && !outputDone
                ? '📝 Submit Proof First'
                : 'Submit for Verification'}
        </button>

        <p className="text-gray-600 text-xs text-center">
          Instant completion is not allowed. All submissions are verified.
        </p>
      </div>
    </>
  )
}

// ── Internal helpers ──────────────────────────────────────────────────────────

function QuestHeader({ quest }) {
  return (
    <div>
      <div className="flex items-center gap-2 text-xs text-gray-500 mb-1">
        <span className="uppercase tracking-widest">{quest.quest_type}</span>
        <span>·</span>
        <span className="capitalize">{quest.difficulty}</span>
      </div>
      <h2 className="text-white font-bold text-lg leading-snug">{quest.title}</h2>
      {quest.description && (
        <p className="text-gray-400 text-sm mt-1">{quest.description}</p>
      )}
    </div>
  )
}

function RequirementRow({ visible, done, label }) {
  if (!visible) return null
  return (
    <div className={`flex items-center gap-2 text-sm px-3 py-2 rounded-lg
      ${done ? 'bg-green-900/20 text-green-400' : 'bg-yellow-900/20 text-yellow-400'}`}>
      <span>{done ? '✅' : '⏳'}</span>
      <span>{label}: {done ? 'Done' : 'Required'}</span>
    </div>
  )
}

function ErrorBanner({ msg }) {
  return (
    <div className="bg-red-900/30 border border-red-500/30 rounded-lg p-3 text-red-400 text-sm">
      {msg}
    </div>
  )
}

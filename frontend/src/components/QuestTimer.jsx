/**
 * QuestTimer.jsx
 *
 * Displays time elapsed vs expected duration with a progress bar.
 * Warns when window is about to close.
 */
import React from 'react'

function fmt(sec) {
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  if (h > 0) return `${h}h ${String(m).padStart(2,'0')}m`
  return `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
}

export default function QuestTimer({ elapsedSec, expectedSec, windowEnd }) {
  const progress = expectedSec > 0
    ? Math.min(100, (elapsedSec / expectedSec) * 100)
    : 0

  const now = Date.now()
  const windowRemainSec = windowEnd
    ? Math.max(0, Math.floor((windowEnd.getTime() - now) / 1000))
    : null

  const barColor =
    progress >= 100 ? 'bg-green-500' :
    progress >= 60  ? 'bg-blue-500'  :
    'bg-yellow-500'

  const windowWarning = windowRemainSec !== null && windowRemainSec < 300  // < 5 min

  return (
    <div className="space-y-2">
      {/* Time display */}
      <div className="flex justify-between text-sm font-mono">
        <span className="text-gray-300">
          Elapsed: <span className="text-white font-bold">{fmt(elapsedSec)}</span>
        </span>
        {expectedSec > 0 && (
          <span className="text-gray-400">
            Target: {fmt(expectedSec)}
          </span>
        )}
      </div>

      {/* Progress bar */}
      {expectedSec > 0 && (
        <div className="w-full bg-gray-700 rounded-full h-2">
          <div
            className={`h-2 rounded-full transition-all duration-1000 ${barColor}`}
            style={{ width: `${progress}%` }}
          />
        </div>
      )}

      {/* Window deadline warning */}
      {windowWarning && (
        <div className="flex items-center gap-2 text-red-400 text-xs animate-pulse">
          <span>⚠</span>
          <span>Window closes in {fmt(windowRemainSec)} — submit soon!</span>
        </div>
      )}

      {/* Minimum time reminder */}
      {progress < 60 && expectedSec > 0 && (
        <p className="text-xs text-yellow-400">
          Complete at least 60% of expected time to pass time verification.
        </p>
      )}
    </div>
  )
}

/**
 * SpotCheckModal.jsx
 *
 * Random validation prompt modal. Appears when the session requires
 * a spot check. Cannot be skipped — submitting with it open is blocked.
 */
import React, { useState, useRef } from 'react'
import { submitSpotCheck } from '../api/verification'

export default function SpotCheckModal({ questId, prompt, onPassed, onFailed }) {
  const [response, setResponse] = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)
  const startRef                = useRef(Date.now())

  const wordCount = response.trim().split(/\s+/).filter(Boolean).length
  const minWords  = 15

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (wordCount < minWords) {
      setError(`Please write at least ${minWords} words.`)
      return
    }
    setLoading(true)
    setError(null)
    try {
      await submitSpotCheck(questId, { responseText: response })
      onPassed?.()
    } catch (err) {
      const msg = err?.response?.data?.detail ?? 'Failed to submit. Try again.'
      setError(msg)
      // Don't call onFailed yet — give the player a chance to retry
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-lg bg-gray-900 border border-yellow-500/40 rounded-2xl shadow-2xl p-6 space-y-5">

        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-yellow-500/20 flex items-center justify-center text-yellow-400 text-xl">
            🔍
          </div>
          <div>
            <h2 className="text-white font-bold text-lg">Spot Check</h2>
            <p className="text-gray-400 text-sm">Answer to confirm genuine progress.</p>
          </div>
        </div>

        {/* Prompt */}
        <div className="bg-gray-800 rounded-xl p-4">
          <p className="text-gray-100 text-sm leading-relaxed">{prompt}</p>
        </div>

        {/* Response */}
        <form onSubmit={handleSubmit} className="space-y-3">
          <textarea
            value={response}
            onChange={e => setResponse(e.target.value)}
            rows={5}
            placeholder="Your answer…"
            className="w-full bg-gray-800 border border-gray-600 rounded-lg p-3 text-gray-100
                       placeholder-gray-500 focus:outline-none focus:border-yellow-500 resize-none text-sm"
          />
          <div className="flex justify-between text-xs text-gray-500">
            <span>{wordCount} / {minWords} words minimum</span>
            {wordCount >= minWords && <span className="text-green-400">✓ Ready to submit</span>}
          </div>

          {error && <p className="text-red-400 text-sm">{error}</p>}

          <button
            type="submit"
            disabled={loading || wordCount < minWords}
            className="w-full py-3 bg-yellow-600 hover:bg-yellow-500 disabled:bg-gray-700
                       disabled:text-gray-500 rounded-xl font-semibold text-sm transition-colors"
          >
            {loading ? 'Submitting…' : 'Submit Answer'}
          </button>
        </form>

        <p className="text-gray-600 text-xs text-center">
          This check helps verify authentic completion. Your response is evaluated automatically.
        </p>
      </div>
    </div>
  )
}

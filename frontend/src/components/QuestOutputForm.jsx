/**
 * QuestOutputForm.jsx
 *
 * Lets the player submit proof artifacts before finalising the quest.
 * Output type list adapts based on quest category (future: from session).
 */
import React, { useState, useRef } from 'react'
import { submitOutput } from '../api/verification'

const OUTPUT_TYPES = [
  { value: 'summary',     label: 'Summary',     hint: 'Summarise what you accomplished.' },
  { value: 'notes',       label: 'Notes',       hint: 'Share your key notes or takeaways.' },
  { value: 'explanation', label: 'Explanation', hint: 'Explain the main concept or skill practised.' },
  { value: 'plan',        label: 'Plan',        hint: 'Outline the steps you completed.' },
  { value: 'reflection',  label: 'Reflection',  hint: 'Reflect on your mindset and effort.' },
]

export default function QuestOutputForm({ questId, required, onSubmitted }) {
  const [type, setType]         = useState('summary')
  const [content, setContent]   = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)
  const [submitted, setSubmitted] = useState(false)
  const startTimeRef            = useRef(Date.now())

  const wordCount = content.trim().split(/\s+/).filter(Boolean).length
  const hint      = OUTPUT_TYPES.find(t => t.value === type)?.hint ?? ''

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (wordCount < 5) {
      setError('Please write at least 5 words.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const timeToWrite = Math.floor((Date.now() - startTimeRef.current) / 1000)
      const result = await submitOutput(questId, {
        output_type:       type,
        content,
        time_to_write_sec: timeToWrite,
      })
      setSubmitted(true)
      onSubmitted?.(result)
    } catch (err) {
      setError(err?.response?.data?.detail ?? 'Failed to submit output.')
    } finally {
      setLoading(false)
    }
  }

  if (submitted) {
    return (
      <div className="rounded-lg border border-green-500/40 bg-green-900/20 p-4 text-center">
        <div className="text-2xl mb-1">✅</div>
        <p className="text-green-400 font-medium">Output submitted successfully.</p>
        <p className="text-gray-400 text-sm mt-1">Verification will evaluate your proof.</p>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-300 mb-2">
          Proof type {required && <span className="text-red-400 ml-1">*required</span>}
        </label>
        <div className="flex flex-wrap gap-2">
          {OUTPUT_TYPES.map(t => (
            <button
              key={t.value}
              type="button"
              onClick={() => setType(t.value)}
              className={`px-3 py-1.5 rounded-full text-sm transition-colors ${
                type === t.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-sm text-gray-400 mb-1">{hint}</label>
        <textarea
          value={content}
          onChange={e => setContent(e.target.value)}
          rows={5}
          placeholder="Write your response here…"
          className="w-full bg-gray-800 border border-gray-600 rounded-lg p-3 text-gray-100
                     placeholder-gray-500 focus:outline-none focus:border-blue-500 resize-none text-sm"
        />
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>{wordCount} words</span>
          <span className={wordCount < 20 ? 'text-yellow-500' : 'text-green-500'}>
            {wordCount < 20 ? 'Write more for higher quality score.' : 'Good length.'}
          </span>
        </div>
      </div>

      {error && (
        <p className="text-red-400 text-sm">{error}</p>
      )}

      <button
        type="submit"
        disabled={loading || wordCount < 5}
        className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700
                   disabled:text-gray-500 rounded-lg text-sm font-medium transition-colors"
      >
        {loading ? 'Submitting…' : 'Submit Proof'}
      </button>
    </form>
  )
}

import { useState, useCallback } from 'react'

export default function useAsync(fn) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const run = useCallback(
    async (...args) => {
      setLoading(true)
      setError(null)
      try {
        const res = await fn(...args)
        setLoading(false)
        return { ok: true, data: res }
      } catch (err) {
        setError(err)
        setLoading(false)
        return { ok: false, error: err }
      }
    },
    [fn]
  )

  return { run, loading, error }
}

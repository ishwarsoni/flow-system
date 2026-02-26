import React from 'react'
import PropTypes from 'prop-types'

export default function StatCard({ label, value }) {
  const safe = Math.max(0, Math.min(100, Number(value || 0)))
  return (
    <div className="bg-white p-4 rounded-lg shadow">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="mt-2 flex items-center justify-between">
        <div className="text-2xl font-bold">{typeof value === 'number' ? value : value}</div>
        <div className="w-24 h-3 bg-gray-100 rounded overflow-hidden">
          <div className="h-full bg-primary" style={{ width: `${safe}%` }} />
        </div>
      </div>
    </div>
  )
}

StatCard.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
}


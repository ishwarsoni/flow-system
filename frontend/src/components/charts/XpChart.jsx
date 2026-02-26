import React from 'react'
import PropTypes from 'prop-types'
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts'

export default function XpChart({ data }) {
  return (
    <div className="bg-white p-4 rounded-lg shadow">
      <h3 className="text-sm font-semibold mb-3">XP (Last 7 days)</h3>
      <div style={{ width: '100%', height: 220 }}>
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 5, right: 12, left: -8, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 12 }} />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Line type="monotone" dataKey="xp" stroke="#4f46e5" strokeWidth={2} dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

XpChart.propTypes = {
  data: PropTypes.arrayOf(PropTypes.object).isRequired,
}

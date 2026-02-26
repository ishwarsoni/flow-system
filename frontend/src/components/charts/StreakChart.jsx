import React from 'react'
import PropTypes from 'prop-types'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts'

export default function StreakChart({ data }) {
  return (
    <div className="bg-white p-4 rounded-lg shadow">
      <h3 className="text-sm font-semibold mb-3">Consistency Trend</h3>
      <div style={{ width: '100%', height: 160 }}>
        <ResponsiveContainer>
          <AreaChart data={data} margin={{ top: 5, right: 12, left: -8, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
            <YAxis hide />
            <Tooltip />
            <Area type="monotone" dataKey="completed" stroke="#f97316" fill="#ffedd5" />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

StreakChart.propTypes = {
  data: PropTypes.arrayOf(PropTypes.object).isRequired,
}

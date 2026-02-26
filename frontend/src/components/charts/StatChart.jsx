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
  Legend,
} from 'recharts'

const COLORS = ['#4f46e5', '#06b6d4', '#10b981', '#f59e0b', '#ef4444']

export default function StatChart({ data, stats }) {
  return (
    <div className="bg-white p-4 rounded-lg shadow">
      <h3 className="text-sm font-semibold mb-3">Stat Deltas (Last 7 days)</h3>
      <div style={{ width: '100%', height: 220 }}>
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 5, right: 12, left: -8, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 12 }} />
            <YAxis />
            <Tooltip />
            <Legend />
            {stats.map((s, i) => (
              <Line
                key={s}
                type="monotone"
                dataKey={s}
                stroke={COLORS[i % COLORS.length]}
                strokeWidth={2}
                dot={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

StatChart.propTypes = {
  data: PropTypes.arrayOf(PropTypes.object).isRequired,
  stats: PropTypes.arrayOf(PropTypes.string).isRequired,
}

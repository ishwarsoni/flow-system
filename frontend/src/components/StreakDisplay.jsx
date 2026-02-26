import React from 'react'
import { Flame } from 'lucide-react'

export default function StreakDisplay({ current, longest }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {/* Current Streak */}
      <div className="bg-gradient-to-br from-orange-400 to-orange-600 rounded-lg shadow-lg p-8 text-white">
        <div className="flex items-center gap-4">
          <div className="bg-white/20 p-4 rounded-full">
            <Flame size={32} />
          </div>
          <div>
            <p className="text-sm opacity-90">Current Streak</p>
            <p className="text-4xl font-bold">{current} days</p>
            <p className="text-sm opacity-75 mt-1">Keep it going!</p>
          </div>
        </div>
      </div>

      {/* Longest Streak */}
      <div className="bg-gradient-to-br from-purple-400 to-purple-600 rounded-lg shadow-lg p-8 text-white">
        <div className="flex items-center gap-4">
          <div className="bg-white/20 p-4 rounded-full">
            <Flame size={32} />
          </div>
          <div>
            <p className="text-sm opacity-90">Longest Streak</p>
            <p className="text-4xl font-bold">{longest} days</p>
            <p className="text-sm opacity-75 mt-1">Your personal best</p>
          </div>
        </div>
      </div>
    </div>
  )
}

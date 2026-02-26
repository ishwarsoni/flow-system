import React from 'react'
import PropTypes from 'prop-types'

export default function ProfileCard({ user, level, xpCurrent, xpToNext, currentStreak, longestStreak }) {
  return (
    <div className="bg-white p-5 rounded-lg shadow">
      <div className="flex items-center gap-4">
        <div className="w-14 h-14 bg-primary/10 text-primary rounded-full flex items-center justify-center text-xl font-bold">
          {user?.username?.charAt(0)?.toUpperCase() ?? 'U'}
        </div>
        <div>
          <div className="text-lg font-semibold">{user?.username ?? user?.sub ?? 'User'}</div>
          <div className="text-sm text-gray-500">{user?.email ?? ''}</div>
        </div>
      </div>

      <div className="mt-4 space-y-3">
        <div>
          <div className="text-xs text-gray-500">Level</div>
          <div className="text-2xl font-bold">{level}</div>
        </div>
        <div>
          <div className="text-xs text-gray-500">XP</div>
          <div className="text-sm">{xpCurrent} / {xpToNext}</div>
        </div>
        <div className="flex gap-4">
          <div>
            <div className="text-xs text-gray-500">Current Streak</div>
            <div className="font-medium">{currentStreak}d</div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Longest Streak</div>
            <div className="font-medium">{longestStreak}d</div>
          </div>
        </div>
      </div>
    </div>
  )
}

ProfileCard.propTypes = {
  user: PropTypes.object,
  level: PropTypes.number,
  xpCurrent: PropTypes.number,
  xpToNext: PropTypes.number,
  currentStreak: PropTypes.number,
  longestStreak: PropTypes.number,
}

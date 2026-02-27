import React, { useState, useEffect, useCallback } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

const NAV_ITEMS = [
  { path: '/dashboard', label: 'STATUS',  icon: '◈' },
  { path: '/quests',    label: 'QUESTS',  icon: '◆' },
  { path: '/domains',   label: 'DOMAINS', icon: '◉' },
  { path: '/analytics', label: 'RECORDS', icon: '▣' },
]

function useIsMobile(breakpoint = 768) {
  const [mobile, setMobile] = useState(() => window.innerWidth < breakpoint)
  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${breakpoint - 1}px)`)
    const handler = (e) => setMobile(e.matches)
    mq.addEventListener('change', handler)
    setMobile(mq.matches)
    return () => mq.removeEventListener('change', handler)
  }, [breakpoint])
  return mobile
}

export default function Layout() {
  const { user, logout } = useAuth()
  const isMobile = useIsMobile()
  const [drawerOpen, setDrawerOpen] = useState(false)
  const location = useLocation()

  // Close drawer on navigation
  useEffect(() => { setDrawerOpen(false) }, [location.pathname])

  const toggleDrawer = useCallback(() => setDrawerOpen(o => !o), [])

  // ── MOBILE LAYOUT ──
  if (isMobile) {
    return (
      <div className="flow-mobile-layout">
        {/* Drawer overlay */}
        {drawerOpen && (
          <div className="flow-drawer-overlay" onClick={() => setDrawerOpen(false)} />
        )}

        {/* Swipeable drawer — hunter info + logout */}
        <aside className={`flow-drawer ${drawerOpen ? 'flow-drawer--open' : ''}`}>
          <div className="flow-drawer-brand">
            <span className="flow-drawer-brand-sys">[ SYSTEM ]</span>
            <span className="flow-drawer-brand-name">FLOW</span>
            <span className="flow-drawer-brand-ver">INTERFACE v2.0</span>
          </div>
          <div className="flow-drawer-divider" />
          <div className="flow-drawer-hunter">
            <div className="flow-drawer-avatar">
              {user?.hunter_name?.charAt(0).toUpperCase() || '?'}
            </div>
            <div className="flow-drawer-hunter-info">
              <div className="flow-drawer-hunter-name">{user?.hunter_name || 'Hunter'}</div>
              <div className="flow-drawer-hunter-status">◉ ONLINE</div>
            </div>
          </div>
          <div className="flow-drawer-divider" />
          <button onClick={logout} className="flow-drawer-logout">
            ⏻ DISCONNECT
          </button>
        </aside>

        {/* Mobile top bar — minimal */}
        <header className="flow-mobile-header">
          <button onClick={toggleDrawer} className="flow-mobile-hamburger" aria-label="Menu">
            ☰
          </button>
          <span className="flow-mobile-title">[ FLOW SYSTEM ]</span>
          <div style={{ width: 44 }} /> {/* Spacer for centering */}
        </header>

        {/* Scrollable content — padded for header+bottom nav */}
        <main className="flow-mobile-main">
          <Outlet />
        </main>

        {/* Fixed bottom navigation */}
        <nav className="flow-bottom-nav">
          {NAV_ITEMS.map(item => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flow-bottom-nav-item ${isActive ? 'flow-bottom-nav-item--active' : ''}`
              }
            >
              <span className="flow-bottom-nav-icon">{item.icon}</span>
              <span className="flow-bottom-nav-label">{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </div>
    )
  }

  // ── DESKTOP LAYOUT ──
  return (
    <div className="flow-desktop-layout">
      {/* Desktop sidebar */}
      <aside className="flow-sidebar">
        <div className="flow-sidebar-scan" />
        <div className="flow-sidebar-brand">
          <div className="flow-sidebar-divline" />
          <div className="flow-sidebar-brand-inner">
            <span className="flow-sidebar-brand-sys">[ SYSTEM ]</span>
            <span className="flow-sidebar-brand-name">FLOW</span>
            <span className="flow-sidebar-brand-ver">INTERFACE v2.0</span>
          </div>
          <div className="flow-sidebar-divline" />
        </div>

        <nav className="flow-sidebar-nav">
          <div className="flow-sidebar-section-label">NAVIGATION</div>
          {NAV_ITEMS.map(item => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flow-sidebar-nav-item ${isActive ? 'flow-sidebar-nav-item--active' : ''}`
              }
            >
              <span className="flow-sidebar-nav-icon">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="flow-sidebar-divider" />

        <div className="flow-sidebar-hunter">
          <div className="flow-sidebar-section-label">HUNTER</div>
          <div className="flow-sidebar-hunter-row">
            <div className="flow-sidebar-avatar">
              {user?.hunter_name?.charAt(0).toUpperCase() || '?'}
            </div>
            <div className="flow-sidebar-hunter-info">
              <div className="flow-sidebar-hunter-name">{user?.hunter_name || 'Hunter'}</div>
              <div className="flow-sidebar-hunter-status">◉ ONLINE</div>
            </div>
            <button onClick={logout} className="flow-sidebar-logout" title="Logout">⏻</button>
          </div>
        </div>
      </aside>

      {/* Desktop main content */}
      <main className="flow-desktop-main">
        <Outlet />
      </main>
    </div>
  )
}


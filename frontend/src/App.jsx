import React, { lazy, Suspense } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { PrivateRoute } from './router/PrivateRoute'
import ErrorBoundary from './components/ErrorBoundary'
import Layout from './components/Layout'

/* ── Lazy-loaded pages — only fetched when navigated to ── */
const LoginPage = lazy(() => import('./pages/LoginPage'))
const RegisterPage = lazy(() => import('./pages/RegisterPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const QuestsPage = lazy(() => import('./pages/QuestsPage'))
const AdaptiveQuestsPage = lazy(() => import('./pages/AdaptiveQuestsPage'))
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage'))

/* ── Page-level loading skeleton ── */
function PageSkeleton() {
  return (
    <div style={{
      minHeight: '60vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12,
      }}>
        <div style={{
          width: 28, height: 28, border: '2px solid rgba(0,212,255,0.2)',
          borderTop: '2px solid #00d4ff', borderRadius: '50%',
          animation: 'spin 0.8s linear infinite',
        }} />
        <span style={{
          fontFamily: "'Orbitron', monospace", fontSize: 10, letterSpacing: 3,
          color: 'rgba(0,212,255,0.4)',
        }}>
          LOADING MODULE...
        </span>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <Router>
        <AuthProvider>
          <Suspense fallback={<PageSkeleton />}>
            <Routes>
              {/* Public routes */}
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />

              {/* Protected routes with sidebar/bottom-nav layout */}
              <Route element={<PrivateRoute />}>
                <Route element={<Layout />}>
                  <Route path="/" element={<DashboardPage />} />
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/tasks" element={<Navigate to="/quests" replace />} />
                  <Route path="/quests" element={<QuestsPage />} />
                  <Route path="/domains" element={<AdaptiveQuestsPage />} />
                  <Route path="/analytics" element={<AnalyticsPage />} />
                </Route>
              </Route>

              {/* Catch-all */}
              <Route path="*" element={<Navigate to="/login" replace />} />
            </Routes>
          </Suspense>
        </AuthProvider>
      </Router>
    </ErrorBoundary>
  )
}

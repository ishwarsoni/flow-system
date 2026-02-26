import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import AnalyticsPage from './pages/AnalyticsPage'
import Layout from './components/Layout'

function PrivateRoute({ children }) {
  const { token, loading } = useAuth()
  if (loading) return <div className="flex items-center justify-center h-screen">Loading...</div>
  return token ? children : <Navigate to="/login" />
}

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          
          <Route
            element={
              <PrivateRoute>
                <Layout />
              </PrivateRoute>
            }
          >
            <Route path="/" element={<DashboardPage />} />
            <Route path="/tasks" element={<Navigate to="/quests" replace />} />
            <Route path="/analytics" element={<AnalyticsPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </AuthProvider>
    </Router>
  )
}

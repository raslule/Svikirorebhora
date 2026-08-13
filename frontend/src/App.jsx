import { BrowserRouter, Routes, Route, Navigate, NavLink, useLocation } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { AuthProvider, useAuth } from './AuthContext'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import MatchPredictor from './pages/MatchPredictor'
import TeamAnalytics from './pages/TeamAnalytics'
import LeagueInsights from './pages/LeagueInsights'
import BetTracker from './pages/BetTracker'
import BetAnalytics from './pages/BetAnalytics'
import BacktestReport from './pages/BacktestReport'

const LEAGUES = ['premier-league', 'la-liga', 'serie-a', 'ligue-1', 'bundesliga']

function ProtectedRoute({ children }) {
  const { user } = useAuth()
  return user ? children : <Navigate to="/login" replace />
}

function Sidebar() {
  const { user, logout } = useAuth()
  const initials = user?.username?.slice(0, 2).toUpperCase() || 'SO'

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="logo-mark">
          <div className="logo-icon">⚽</div>
          <div>
            <div className="logo-text">SoccerOracle</div>
            <div className="logo-sub">Match Intelligence</div>
          </div>
        </div>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section-label">Predictions</div>
        <NavLink to="/" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <span className="nav-icon">🏟️</span> Dashboard
        </NavLink>
        <NavLink to="/predictor" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <span className="nav-icon">🎯</span> Match Predictor
        </NavLink>

        <div className="nav-section-label">Analytics</div>
        <NavLink to="/teams" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <span className="nav-icon">📊</span> Team Analytics
        </NavLink>
        <NavLink to="/leagues" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <span className="nav-icon">📈</span> League Insights
        </NavLink>
        <NavLink to="/backtest" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <span className="nav-icon">🔬</span> Backtest Report
        </NavLink>

        <div className="nav-section-label">Bet Tracker</div>
        <NavLink to="/bets" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <span className="nav-icon">💰</span> Log Bets
        </NavLink>
        <NavLink to="/bet-analytics" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
          <span className="nav-icon">💹</span> P&amp;L Dashboard
        </NavLink>
      </nav>

      <div className="sidebar-footer">
        <div className="user-pill">
          <div className="user-avatar">{initials}</div>
          <div style={{ flex: 1 }}>
            <div className="user-name">{user?.username}</div>
            <div className="user-role">Analyst</div>
          </div>
          <button onClick={logout} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 16 }} title="Logout">⏻</button>
        </div>
      </div>
    </aside>
  )
}

function AppShell() {
  const { user } = useAuth()
  const location = useLocation()
  if (!user || location.pathname === '/login') return null
  return <Sidebar />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: 'var(--bg-card)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border)',
              borderRadius: '10px',
              fontSize: '13px',
            },
            success: { iconTheme: { primary: 'var(--green)', secondary: 'black' } },
            error:   { iconTheme: { primary: 'var(--red)', secondary: 'black' } },
          }}
        />
        <div className="app-shell">
          <AppShell />
          <div className="main-content">
            <Routes>
              <Route path="/login" element={<Login />} />
              <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
              <Route path="/predictor" element={<ProtectedRoute><MatchPredictor /></ProtectedRoute>} />
              <Route path="/teams" element={<ProtectedRoute><TeamAnalytics /></ProtectedRoute>} />
              <Route path="/leagues" element={<ProtectedRoute><LeagueInsights /></ProtectedRoute>} />
              <Route path="/bets" element={<ProtectedRoute><BetTracker /></ProtectedRoute>} />
              <Route path="/bet-analytics" element={<ProtectedRoute><BetAnalytics /></ProtectedRoute>} />
              <Route path="/backtest" element={<ProtectedRoute><BacktestReport /></ProtectedRoute>} />
              <Route path="*" element={<Navigate to="/" />} />
            </Routes>
          </div>
        </div>
      </BrowserRouter>
    </AuthProvider>
  )
}

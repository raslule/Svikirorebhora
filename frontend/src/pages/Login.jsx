import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { useAuth } from '../AuthContext'

export default function Login() {
  const [mode, setMode] = useState('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const { login, register, loading } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async e => {
    e.preventDefault()
    if (!username.trim() || !password.trim()) return toast.error('Please fill all fields')

    const fn = mode === 'login' ? login : register
    const res = await fn(username.trim(), password)

    if (res.ok) {
      toast.success(mode === 'login' ? 'Welcome back!' : 'Account created!')
      navigate('/')
    } else {
      toast.error(res.error)
    }
  }

  return (
    <div className="login-page">
      <div className="login-bg-orbs">
        <div className="orb orb-1" />
        <div className="orb orb-2" />
      </div>

      <div className="login-card animate-fade-in">
        <div className="login-logo">
          <div className="login-logo-icon">⚽</div>
          <div className="login-title">SoccerOracle</div>
          <div className="login-sub">European Match Intelligence Platform</div>
        </div>

        <div className="tab-bar" style={{ marginBottom: 24 }}>
          <button className={`tab-item${mode === 'login' ? ' active' : ''}`} onClick={() => setMode('login')}>Sign In</button>
          <button className={`tab-item${mode === 'register' ? ' active' : ''}`} onClick={() => setMode('register')}>Create Account</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="input-group">
            <label className="input-label">Username</label>
            <input
              id="login-username"
              className="input-field"
              placeholder="Enter username"
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoFocus
            />
          </div>
          <div className="input-group">
            <label className="input-label">Password</label>
            <input
              id="login-password"
              type="password"
              className="input-field"
              placeholder="Enter password"
              value={password}
              onChange={e => setPassword(e.target.value)}
            />
          </div>

          <button id="login-submit-btn" type="submit" className="btn btn-primary btn-full btn-lg" style={{ marginTop: 8 }} disabled={loading}>
            {loading ? <span className="spinner" /> : (mode === 'login' ? '🔑 Sign In' : '✨ Create Account')}
          </button>
        </form>

        <div className="login-footer">
          {mode === 'login'
            ? <>No account? <span onClick={() => setMode('register')}>Create one free</span></>
            : <>Already have an account? <span onClick={() => setMode('login')}>Sign in</span></>
          }
        </div>

        <div style={{ marginTop: 24, padding: '14px 16px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, letterSpacing: '0.5px', textTransform: 'uppercase', marginBottom: 8 }}>Covers</div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {['🏴󠁧󠁢󠁥󠁮󠁧󠁿 EPL', '🇪🇸 La Liga', '🇮🇹 Serie A', '🇫🇷 Ligue 1', '🇩🇪 Bundesliga'].map(l => (
              <span key={l} style={{ fontSize: 12, background: 'var(--teal-dim)', color: 'var(--teal)', padding: '3px 8px', borderRadius: 20, fontWeight: 600 }}>{l}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

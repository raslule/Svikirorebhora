import { useState, useEffect } from 'react'
import { matches as matchesApi } from '../api'
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import toast from 'react-hot-toast'

const LEAGUES = ['premier-league','la-liga','serie-a','ligue-1','bundesliga']
const LEAGUE_COLORS = { 'premier-league': '#6600FF', 'la-liga': '#FF4444', 'serie-a': '#0064FF', 'ligue-1': '#FFB800', 'bundesliga': '#FF5000' }

export default function LeagueInsights() {
  const [league, setLeague] = useState('premier-league')
  const [results, setResults] = useState([])
  const [standings, setStandings] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      matchesApi.results({ league, limit: 200 }),
      matchesApi.standings(league),
    ]).then(([r, s]) => {
      setResults(r.data)
      setStandings(s.data)
    }).catch(() => toast.error('Failed to load league data'))
    .finally(() => setLoading(false))
  }, [league])

  // Derived stats
  const totalGoals = results.reduce((s, m) => s + (m.fthg || 0) + (m.ftag || 0), 0)
  const avgGoals = results.length > 0 ? (totalGoals / results.length).toFixed(2) : 0
  const homeWins = results.filter(m => m.ftr === 'H').length
  const draws = results.filter(m => m.ftr === 'D').length
  const awayWins = results.filter(m => m.ftr === 'A').length
  const btts = results.filter(m => (m.fthg || 0) >= 1 && (m.ftag || 0) >= 1).length
  const bttsRate = results.length > 0 ? (btts / results.length * 100).toFixed(1) : 0

  const outcomeData = [
    { name: 'Home Win', value: homeWins, pct: results.length > 0 ? (homeWins/results.length*100).toFixed(0) : 0, fill: 'var(--teal)' },
    { name: 'Draw', value: draws, pct: results.length > 0 ? (draws/results.length*100).toFixed(0) : 0, fill: 'var(--amber)' },
    { name: 'Away Win', value: awayWins, pct: results.length > 0 ? (awayWins/results.length*100).toFixed(0) : 0, fill: 'var(--red)' },
  ]

  // Goal distribution (0-6+)
  const goalDist = Array.from({ length: 7 }, (_, i) => {
    const key = i < 6 ? i : '6+'
    const count = results.filter(m => {
      const tg = (m.fthg || 0) + (m.ftag || 0)
      return i < 6 ? tg === i : tg >= 6
    }).length
    return { goals: String(key), count, pct: results.length > 0 ? parseFloat((count/results.length*100).toFixed(1)) : 0 }
  })

  // Corner stats
  const avgCorners = results.length > 0
    ? ((results.reduce((s,m) => s + (m.hc||0) + (m.ac||0), 0)) / results.length).toFixed(1)
    : '—'

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">League Insights</h1>
        <p className="page-subtitle">Statistical analysis and trends from historical match data</p>
        <div className="league-tabs" style={{ marginTop: 12 }}>
          {LEAGUES.map(l => (
            <button key={l} className={`league-tab${league === l ? ' active' : ''}`} data-league={l} onClick={() => setLeague(l)}>
              {{ 'premier-league': '🏴󠁧󠁢󠁥󠁮󠁧󠁿 EPL', 'la-liga': '🇪🇸 La Liga', 'serie-a': '🇮🇹 Serie A', 'ligue-1': '🇫🇷 Ligue 1', 'bundesliga': '🇩🇪 Bundesliga' }[l]}
            </button>
          ))}
        </div>
      </div>

      <div className="page-body">
        {/* KPIs */}
        <div className="stat-grid mb-6">
          <div className="stat-card"><div className="stat-label">Matches</div><div className="stat-value">{results.length}</div><div className="stat-sub">In current season DB</div></div>
          <div className="stat-card amber"><div className="stat-label">Avg Goals</div><div className="stat-value">{avgGoals}</div><div className="stat-sub">Per match</div></div>
          <div className="stat-card green"><div className="stat-label">BTTS Rate</div><div className="stat-value">{bttsRate}%</div><div className="stat-sub">{btts} of {results.length} matches</div></div>
          <div className="stat-card"><div className="stat-label">Avg Corners</div><div className="stat-value">{avgCorners}</div><div className="stat-sub">Total per match</div></div>
        </div>

        <div className="grid-2 mb-6">
          {/* Outcome Distribution */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">⚖️ Outcome Distribution</div>
              <span className="card-badge badge-teal">{results.length} Matches</span>
            </div>
            <div className="chart-container">
              <ResponsiveContainer>
                <BarChart data={outcomeData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip formatter={(v, n) => [v, 'Matches']} contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8 }} />
                  <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                    {outcomeData.map((e, i) => (
                      <Bar key={i} fill={e.fill} />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              </ResponsiveContainer>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-around', marginTop: 12 }}>
              {outcomeData.map(d => (
                <div key={d.name} style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 20, fontWeight: 800, color: d.fill }}>{d.pct}%</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{d.name}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Goal Distribution */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">⚽ Goal Distribution</div>
              <span className="card-badge badge-amber">Total Goals/Match</span>
            </div>
            <div className="chart-container">
              <ResponsiveContainer>
                <BarChart data={goalDist}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="goals" label={{ value: 'Total Goals', position: 'insideBottom', offset: -5 }} />
                  <YAxis unit="%" />
                  <Tooltip formatter={(v) => [`${v}%`, 'Frequency']} contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8 }} />
                  <Bar dataKey="pct" fill="var(--purple)" radius={[4,4,0,0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Standings Table */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">🏆 League Standings (Current Season)</div>
            <span className="card-badge badge-green">Live from DB</span>
          </div>
          {standings.length === 0 ? (
            <div className="empty-state"><div className="empty-state-icon">📋</div><div className="empty-state-title">No standings data</div><div className="empty-state-text">Seed the database with match data first</div></div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr><th>#</th><th>Team</th><th>P</th><th>W</th><th>D</th><th>L</th><th>GF</th><th>GA</th><th>GD</th><th>Pts</th></tr>
                </thead>
                <tbody>
                  {standings.map(row => (
                    <tr key={row.team}>
                      <td><strong style={{ color: row.Pos <= 4 ? 'var(--teal)' : row.Pos >= standings.length - 2 ? 'var(--red)' : undefined }}>{row.Pos}</strong></td>
                      <td><strong>{row.team}</strong></td>
                      <td>{row.P}</td>
                      <td className="text-green">{row.W}</td>
                      <td>{row.D}</td>
                      <td className="text-red">{row.L}</td>
                      <td>{row.GF}</td>
                      <td>{row.GA}</td>
                      <td className={row.GD > 0 ? 'pl-positive' : row.GD < 0 ? 'pl-negative' : ''}>{row.GD > 0 ? '+' : ''}{row.GD}</td>
                      <td><strong className="text-teal">{row.Pts}</strong></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

import { useState, useEffect } from 'react'
import { matches as matchesApi } from '../api'
import { LineChart, Line, BarChart, Bar, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'
import toast from 'react-hot-toast'

const LEAGUES = ['premier-league','la-liga','serie-a','ligue-1','bundesliga']
const LEAGUE_COLORS = { 'premier-league': '#6600FF', 'la-liga': '#FF4444', 'serie-a': '#0064FF', 'ligue-1': '#FFB800', 'bundesliga': '#FF5000' }

export default function LeagueInsights() {
  const [league, setLeague] = useState('premier-league')
  const [season, setSeason] = useState('current')
  const [availableSeasons, setAvailableSeasons] = useState([])
  const [results, setResults] = useState([])
  const [standings, setStandings] = useState([])
  const [standingsStatus, setStandingsStatus] = useState('live')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setSeason('current')
    matchesApi.seasons(league).then(res => {
      setAvailableSeasons(res.data)
    }).catch(() => console.error("Failed to load seasons"))
  }, [league])

  useEffect(() => {
    setLoading(true)
    Promise.all([
      matchesApi.results({ league, limit: 200, season }),
      matchesApi.standings(league, season),
    ]).then(([r, s]) => {
      setResults(r.data)
      setStandings(s.data.standings || [])
      setStandingsStatus(s.data.status || 'live')
    }).catch(() => toast.error('Failed to load league data'))
    .finally(() => setLoading(false))
  }, [league, season])

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

  // Cards stats (Yellows + 2*Reds)
  const avgCards = results.length > 0
    ? ((results.reduce((s,m) => s + (m.hy||0) + (m.ay||0) + 2*((m.hr||0) + (m.ar||0)), 0)) / results.length).toFixed(1)
    : '—'

  // Total Shots stats
  const avgShots = results.length > 0
    ? ((results.reduce((s,m) => s + (m.hs||0) + (m.as_||0), 0)) / results.length).toFixed(1)
    : '—'

  // Shots on Target (SOT) stats
  const avgSot = results.length > 0
    ? ((results.reduce((s,m) => s + (m.hst||0) + (m.ast||0), 0)) / results.length).toFixed(1)
    : '—'

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">League Insights</h1>
        <p className="page-subtitle">Statistical analysis and trends from historical match data</p>
        <div className="league-tabs" style={{ marginTop: 12, display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            {LEAGUES.map(l => (
              <button key={l} className={`league-tab${league === l ? ' active' : ''}`} data-league={l} onClick={() => setLeague(l)}>
                {{ 'premier-league': '🇬🇧 EPL', 'la-liga': '🇪🇸 La Liga', 'serie-a': '🇮🇹 Serie A', 'ligue-1': '🇫🇷 Ligue 1', 'bundesliga': '🇩🇪 Bundesliga' }[l]}
              </button>
            ))}
          </div>
          <select value={season} onChange={e => setSeason(e.target.value)} style={{ padding: '6px 12px', background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text)', borderRadius: '6px', fontWeight: 600 }}>
            <option value="current">Current Season</option>
            {availableSeasons.map(s => (
              <option key={s} value={s}>20{s.substring(0, 2)}/{s.substring(2, 4)}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="page-body">
        {/* KPIs */}
        <div className="stat-grid mb-6">
          <div className="stat-card"><div className="stat-label">Matches</div><div className="stat-value">{results.length}</div><div className="stat-sub">In selected season</div></div>
          <div className="stat-card amber"><div className="stat-label">Avg Goals</div><div className="stat-value">{avgGoals}</div><div className="stat-sub">Per match</div></div>
          <div className="stat-card green"><div className="stat-label">BTTS Rate</div><div className="stat-value">{bttsRate}%</div><div className="stat-sub">{btts} of {results.length} matches</div></div>
          <div className="stat-card"><div className="stat-label">Avg Corners</div><div className="stat-value">{avgCorners}</div><div className="stat-sub">Total per match</div></div>
          <div className="stat-card rose"><div className="stat-label">Avg Cards</div><div className="stat-value">{avgCards}</div><div className="stat-sub">Total per match</div></div>
          <div className="stat-card cyan"><div className="stat-label">Avg Shots</div><div className="stat-value">{avgShots}</div><div className="stat-sub">Total per match</div></div>
          <div className="stat-card purple"><div className="stat-label">Avg SOT</div><div className="stat-value">{avgSot}</div><div className="stat-sub">On target per match</div></div>
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
                      <Cell key={`cell-${i}`} fill={e.fill} />
                    ))}
                  </Bar>
                </BarChart>
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
            <div className="card-title">🏆 League Standings</div>
            {standingsStatus === 'live' && <span className="card-badge badge-green">LIVE FROM DB</span>}
            {standingsStatus === 'not_started' && <span className="card-badge badge-gray">PRE-SEASON</span>}
            {standingsStatus === 'final' && <span className="card-badge badge-blue" style={{ background: 'rgba(0,100,255,0.2)', color: '#4499ff', border: '1px solid rgba(0,100,255,0.3)' }}>FINAL</span>}
          </div>
          {standings.length === 0 ? (
            <div className="empty-state"><div className="empty-state-icon">📋</div><div className="empty-state-title">No standings data</div><div className="empty-state-text">Awaiting season kickoff or DB sync</div></div>
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

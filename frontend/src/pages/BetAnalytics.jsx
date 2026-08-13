import { useState, useEffect } from 'react'
import { bets as betsApi } from '../api'
import toast from 'react-hot-toast'
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend
} from 'recharts'

const COLORS = ['#00D4FF','#A855F7','#00E699','#FFB800','#FF4D6D','#0080FF']

export default function BetAnalytics() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    betsApi.analytics()
      .then(r => setData(r.data))
      .catch(() => toast.error('Failed to load analytics'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
      <div className="spinner" style={{ width: 40, height: 40, borderWidth: 3 }} />
    </div>
  )

  if (!data || data.message) return (
    <div>
      <div className="page-header"><h1 className="page-title">P&L Dashboard</h1><p className="page-subtitle">Bet analytics and ROI tracking</p></div>
      <div className="page-body">
        <div className="empty-state"><div className="empty-state-icon">📊</div><div className="empty-state-title">No settled bets yet</div><div className="empty-state-text">Log bets in the Bet Tracker and mark them as WON/LOST to see analytics</div></div>
      </div>
    </div>
  )

  const { summary, by_market, by_league, monthly_pl } = data

  // Monthly P&L chart data
  const monthlyData = Object.entries(monthly_pl || {})
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([month, d]) => ({
      month: month.slice(2), // "26-08"
      pl: parseFloat(d.pl.toFixed(2)),
      bets: d.bets,
      stake: parseFloat(d.stake.toFixed(2)),
    }))

  // Cumulative P&L
  let cum = 0
  const cumulativeData = monthlyData.map(d => ({ ...d, cumulative: parseFloat((cum += d.pl).toFixed(2)) }))

  // Market pie
  const marketPie = Object.entries(by_market || {}).map(([name, d]) => ({ name, value: d.bets, pl: d.profit_loss }))

  // League bar
  const leagueBar = Object.entries(by_league || {}).map(([name, d]) => ({
    name: name.replace('-', ' ').replace(/\b\w/g, c => c.toUpperCase()).slice(0, 10),
    roi: d.roi, pl: d.profit_loss, bets: d.bets
  }))

  const roi = summary?.roi || 0
  const pl = summary?.total_profit_loss || 0

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">P&L Dashboard</h1>
        <p className="page-subtitle">Real-time betting analytics — ROI, win rate, and market breakdown</p>
      </div>

      <div className="page-body">
        {/* KPI Row */}
        <div className="grid-4 mb-6">
          <div className={`stat-card ${pl >= 0 ? 'green' : 'red'}`}>
            <div className="stat-label">Net P&L</div>
            <div className="stat-value" style={{ color: pl >= 0 ? 'var(--green)' : 'var(--red)', fontSize: 24 }}>{pl >= 0 ? '+' : ''}R{pl.toFixed(2)}</div>
            <div className="stat-sub">Total profit/loss</div>
          </div>
          <div className={`stat-card ${roi >= 0 ? '' : 'red'}`}>
            <div className="stat-label">ROI</div>
            <div className="stat-value" style={{ color: roi >= 0 ? 'var(--teal)' : 'var(--red)', fontSize: 24 }}>{roi >= 0 ? '+' : ''}{roi.toFixed(1)}%</div>
            <div className="stat-sub">on R{summary.total_stake?.toFixed(0)} staked</div>
          </div>
          <div className="stat-card amber">
            <div className="stat-label">Win Rate</div>
            <div className="stat-value" style={{ fontSize: 24 }}>{summary.win_rate?.toFixed(1)}%</div>
            <div className="stat-sub">{summary.won}W · {summary.lost}L · {summary.pending} pending</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Avg Odds</div>
            <div className="stat-value" style={{ fontSize: 24 }}>{summary.avg_odds?.toFixed(2)}</div>
            <div className="stat-sub">{summary.settled} settled bets</div>
          </div>
        </div>

        <div className="grid-2 mb-6">
          {/* Cumulative P&L Chart */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">📈 Cumulative P&L</div>
              <span className="card-badge badge-teal">Monthly</span>
            </div>
            {cumulativeData.length === 0 ? (
              <div className="empty-state"><div className="empty-state-text">No monthly data yet</div></div>
            ) : (
              <div className="chart-container">
                <ResponsiveContainer>
                  <AreaChart data={cumulativeData}>
                    <defs>
                      <linearGradient id="plGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#00D4FF" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#00D4FF" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" />
                    <YAxis />
                    <Tooltip formatter={(v) => [`R${v}`, 'Cumulative P&L']} contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8 }} />
                    <Area type="monotone" dataKey="cumulative" stroke="#00D4FF" strokeWidth={2} fill="url(#plGrad)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>

          {/* Monthly P&L bars */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">📊 Monthly P&L</div>
              <span className="card-badge badge-amber">Breakdown</span>
            </div>
            {monthlyData.length === 0 ? (
              <div className="empty-state"><div className="empty-state-text">No monthly data yet</div></div>
            ) : (
              <div className="chart-container">
                <ResponsiveContainer>
                  <BarChart data={monthlyData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" />
                    <YAxis />
                    <Tooltip formatter={(v) => [`R${v}`, 'P&L']} contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8 }} />
                    <Bar dataKey="pl" radius={[4, 4, 0, 0]}>
                      {monthlyData.map((entry, i) => (
                        <Cell key={i} fill={entry.pl >= 0 ? 'var(--green)' : 'var(--red)'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>

        <div className="grid-2">
          {/* Market Breakdown */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">🎯 Market Breakdown</div>
              <span className="card-badge badge-purple">All Markets</span>
            </div>
            {marketPie.length === 0 ? (
              <div className="empty-state"><div className="empty-state-text">No market data</div></div>
            ) : (
              <>
                <div className="chart-container-sm">
                  <ResponsiveContainer>
                    <PieChart>
                      <Pie data={marketPie} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value">
                        {marketPie.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                      </Pie>
                      <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8 }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <table className="data-table" style={{ marginTop: 8 }}>
                  <thead><tr><th>Market</th><th>Bets</th><th>Win%</th><th>P&L</th><th>ROI%</th></tr></thead>
                  <tbody>
                    {Object.entries(by_market || {}).map(([mkt, d]) => (
                      <tr key={mkt}>
                        <td><span className="card-badge badge-teal">{mkt}</span></td>
                        <td>{d.bets}</td>
                        <td>{d.win_rate}%</td>
                        <td className={d.profit_loss >= 0 ? 'pl-positive' : 'pl-negative'}>{d.profit_loss >= 0 ? '+' : ''}R{d.profit_loss.toFixed(2)}</td>
                        <td className={d.roi >= 0 ? 'pl-positive' : 'pl-negative'}>{d.roi >= 0 ? '+' : ''}{d.roi}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </div>

          {/* League Breakdown */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">🌍 League ROI</div>
              <span className="card-badge badge-green">By Competition</span>
            </div>
            {leagueBar.length === 0 ? (
              <div className="empty-state"><div className="empty-state-text">No league data</div></div>
            ) : (
              <>
                <div className="chart-container">
                  <ResponsiveContainer>
                    <BarChart data={leagueBar} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" unit="%" />
                      <YAxis type="category" dataKey="name" width={80} />
                      <Tooltip formatter={(v) => [`${v}%`, 'ROI']} contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8 }} />
                      <Bar dataKey="roi" radius={[0, 4, 4, 0]}>
                        {leagueBar.map((entry, i) => (
                          <Cell key={i} fill={entry.roi >= 0 ? COLORS[i % COLORS.length] : 'var(--red)'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <table className="data-table" style={{ marginTop: 8 }}>
                  <thead><tr><th>League</th><th>Bets</th><th>Win%</th><th>P&L</th><th>ROI%</th></tr></thead>
                  <tbody>
                    {Object.entries(by_league || {}).map(([lg, d]) => (
                      <tr key={lg}>
                        <td style={{ fontWeight: 600, fontSize: 12 }}>{lg}</td>
                        <td>{d.bets}</td>
                        <td>{d.win_rate}%</td>
                        <td className={d.profit_loss >= 0 ? 'pl-positive' : 'pl-negative'}>{d.profit_loss >= 0 ? '+' : ''}R{d.profit_loss.toFixed(2)}</td>
                        <td className={d.roi >= 0 ? 'pl-positive' : 'pl-negative'}>{d.roi >= 0 ? '+' : ''}{d.roi}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

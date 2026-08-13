import { useState, useEffect } from 'react'
import { bets as betsApi } from '../api'
import toast from 'react-hot-toast'

const MARKETS = ['1X2','BTTS Yes','BTTS No','Over 2.5','Over 3.5','Under 2.5','Corners O9.5','Corners O10.5','Fouls O20','Fouls O25']
const LEAGUES = ['premier-league','la-liga','serie-a','ligue-1','bundesliga']

const RESULTS = ['WON','LOST','VOID']

const STATUS_COLORS = { WON: 'var(--green)', LOST: 'var(--red)', VOID: 'var(--text-muted)' }

export default function BetTracker() {
  const [bets, setBets]     = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [filterLeague, setFilterLeague] = useState('')
  const [filterResult, setFilterResult] = useState('')
  const [editBet, setEditBet] = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const { data } = await betsApi.list({ league: filterLeague || undefined, result: filterResult || undefined })
      setBets(data)
    } catch { toast.error('Failed to load bets') }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [filterLeague, filterResult])

  const handleSetResult = async (bet, result) => {
    try {
      await betsApi.update(bet.id, { result })
      toast.success(`Marked as ${result}`)
      load()
    } catch { toast.error('Failed to update') }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this bet?')) return
    try {
      await betsApi.remove(id)
      toast.success('Bet deleted')
      load()
    } catch { toast.error('Failed to delete') }
  }

  const totalStake = bets.filter(b => b.result).reduce((s, b) => s + b.stake, 0)
  const totalPL    = bets.filter(b => b.result).reduce((s, b) => s + (b.profit_loss || 0), 0)

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Bet Tracker</h1>
        <p className="page-subtitle">Log, manage and track all your bets across all leagues and markets</p>
      </div>

      <div className="page-body">
        {/* Summary strip */}
        <div className="stat-grid" style={{ marginBottom: 24 }}>
          <div className="stat-card">
            <div className="stat-label">Total Bets</div>
            <div className="stat-value">{bets.length}</div>
            <div className="stat-sub">{bets.filter(b => !b.result).length} pending</div>
          </div>
          <div className={`stat-card ${totalPL >= 0 ? 'green' : 'red'}`}>
            <div className="stat-label">Net P&amp;L</div>
            <div className="stat-value" style={{ color: totalPL >= 0 ? 'var(--green)' : 'var(--red)', fontSize: 22 }}>
              {totalPL >= 0 ? '+' : ''}R{totalPL.toFixed(2)}
            </div>
            <div className="stat-sub">on R{totalStake.toFixed(2)} staked</div>
          </div>
          <div className="stat-card amber">
            <div className="stat-label">Win Rate</div>
            <div className="stat-value" style={{ fontSize: 22 }}>
              {bets.filter(b=>b.result).length > 0
                ? `${(bets.filter(b=>b.result==='WON').length / bets.filter(b=>b.result).length * 100).toFixed(0)}%`
                : '—'}
            </div>
            <div className="stat-sub">{bets.filter(b=>b.result==='WON').length}W · {bets.filter(b=>b.result==='LOST').length}L</div>
          </div>
          <div className="stat-card purple">
            <div className="stat-label">ROI</div>
            <div className="stat-value" style={{ color: totalPL >= 0 ? 'var(--green)' : 'var(--red)', fontSize: 22 }}>
              {totalStake > 0 ? `${(totalPL/totalStake*100).toFixed(1)}%` : '—'}
            </div>
            <div className="stat-sub">Return on investment</div>
          </div>
        </div>

        {/* Toolbar */}
        <div className="flex items-center justify-between mb-4" style={{ gap: 12, flexWrap: 'wrap' }}>
          <div className="flex gap-2" style={{ gap: 12 }}>
            <select className="input-field" style={{ width: 160 }} value={filterLeague} onChange={e => setFilterLeague(e.target.value)}>
              <option value="">All Leagues</option>
              {LEAGUES.map(l => <option key={l} value={l}>{l}</option>)}
            </select>
            <select className="input-field" style={{ width: 140 }} value={filterResult} onChange={e => setFilterResult(e.target.value)}>
              <option value="">All Results</option>
              <option value="WON">Won</option>
              <option value="LOST">Lost</option>
              <option value="VOID">Void</option>
            </select>
          </div>
          <button id="add-bet-btn" className="btn btn-primary" onClick={() => setShowModal(true)}>+ Log New Bet</button>
        </div>

        {/* Table */}
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          {loading ? (
            <div style={{ padding: 40, textAlign: 'center' }}><div className="spinner" style={{ margin: '0 auto', width: 32, height: 32 }} /></div>
          ) : bets.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">💰</div>
              <div className="empty-state-title">No bets logged yet</div>
              <div className="empty-state-text">Click "Log New Bet" to add your first bet</div>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Match</th>
                    <th>Market</th>
                    <th>Selection</th>
                    <th>Odds</th>
                    <th>Stake</th>
                    <th>P&amp;L</th>
                    <th>Result</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {bets.map(bet => (
                    <tr key={bet.id}>
                      <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{bet.match_date ? new Date(bet.match_date).toLocaleDateString('en-GB') : '—'}</td>
                      <td>
                        <div style={{ fontWeight: 600, fontSize: 13 }}>{bet.home_team} vs {bet.away_team}</div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{bet.league}</div>
                      </td>
                      <td><span className="card-badge badge-teal">{bet.market}</span></td>
                      <td style={{ fontWeight: 600 }}>{bet.selection}</td>
                      <td className="text-teal font-bold">{bet.odds}</td>
                      <td>R{bet.stake.toFixed(2)}</td>
                      <td className={bet.profit_loss !== null ? (bet.profit_loss >= 0 ? 'pl-positive' : 'pl-negative') : 'pl-neutral'}>
                        {bet.profit_loss !== null ? `${bet.profit_loss >= 0 ? '+' : ''}R${bet.profit_loss.toFixed(2)}` : '—'}
                      </td>
                      <td>
                        {bet.result ? (
                          <span className={`status-badge status-${bet.result}`}>{bet.result}</span>
                        ) : (
                          <div className="flex gap-2" style={{ gap: 4 }}>
                            {RESULTS.map(r => (
                              <button key={r} className={`btn btn-sm ${r==='WON'?'btn-secondary':r==='LOST'?'btn-danger':'btn-secondary'}`}
                                style={{ padding: '3px 8px', fontSize: 10 }}
                                onClick={() => handleSetResult(bet, r)}>{r}</button>
                            ))}
                          </div>
                        )}
                      </td>
                      <td>
                        <button className="btn btn-sm btn-danger" onClick={() => handleDelete(bet.id)}>✕</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {showModal && <AddBetModal onClose={() => { setShowModal(false); load() }} />}
    </div>
  )
}

function AddBetModal({ onClose }) {
  const [form, setForm] = useState({ match_date: '', league: 'premier-league', home_team: '', away_team: '', market: '1X2', selection: 'Home', odds: '', stake: '', notes: '' })
  const [saving, setSaving] = useState(false)

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const save = async () => {
    if (!form.home_team || !form.away_team || !form.odds || !form.stake) return toast.error('Fill required fields')
    setSaving(true)
    try {
      await betsApi.create({ ...form, odds: parseFloat(form.odds), stake: parseFloat(form.stake) })
      toast.success('Bet logged!')
      onClose()
    } catch { toast.error('Failed to save') }
    finally { setSaving(false) }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">Log New Bet</div>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="grid-2" style={{ gap: 12 }}>
          <div className="input-group"><label className="input-label">Date</label><input type="date" className="input-field" value={form.match_date} onChange={e=>set('match_date',e.target.value)} /></div>
          <div className="input-group">
            <label className="input-label">League</label>
            <select className="input-field" value={form.league} onChange={e=>set('league',e.target.value)}>
              {LEAGUES.map(l=><option key={l}>{l}</option>)}
            </select>
          </div>
          <div className="input-group"><label className="input-label">Home Team</label><input className="input-field" placeholder="e.g. Arsenal" value={form.home_team} onChange={e=>set('home_team',e.target.value)} /></div>
          <div className="input-group"><label className="input-label">Away Team</label><input className="input-field" placeholder="e.g. Chelsea" value={form.away_team} onChange={e=>set('away_team',e.target.value)} /></div>
          <div className="input-group">
            <label className="input-label">Market</label>
            <select className="input-field" value={form.market} onChange={e=>set('market',e.target.value)}>
              {MARKETS.map(m=><option key={m}>{m}</option>)}
            </select>
          </div>
          <div className="input-group"><label className="input-label">Selection</label><input className="input-field" placeholder="Home / Yes / Over" value={form.selection} onChange={e=>set('selection',e.target.value)} /></div>
          <div className="input-group"><label className="input-label">Odds *</label><input type="number" step="0.01" className="input-field" placeholder="e.g. 2.10" value={form.odds} onChange={e=>set('odds',e.target.value)} /></div>
          <div className="input-group"><label className="input-label">Stake (R) *</label><input type="number" step="0.01" className="input-field" placeholder="e.g. 50" value={form.stake} onChange={e=>set('stake',e.target.value)} /></div>
        </div>
        <div className="input-group"><label className="input-label">Notes</label><input className="input-field" placeholder="Optional notes..." value={form.notes} onChange={e=>set('notes',e.target.value)} /></div>
        <button className="btn btn-primary btn-full" onClick={save} disabled={saving}>{saving ? <span className="spinner" /> : '💾 Save Bet'}</button>
      </div>
    </div>
  )
}

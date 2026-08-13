/* PredictionPanel — Core shared component used on Dashboard and MatchPredictor */
import { useState } from 'react'
import { bets as betsApi } from '../api'
import toast from 'react-hot-toast'

const LEAGUE_LABELS = {
  'premier-league': '🏴󠁧󠁢󠁥󠁮󠁧󠁿 EPL',
  'la-liga':        '🇪🇸 La Liga',
  'serie-a':        '🇮🇹 Serie A',
  'ligue-1':        '🇫🇷 Ligue 1',
  'bundesliga':     '🇩🇪 Bundesliga',
}

function ProbBar({ label, pct, type, odds }) {
  return (
    <div className="prediction-row">
      <div className="pred-label">{label}</div>
      <div className="pred-bar-track">
        <div className={`pred-bar-fill ${type}`} style={{ width: `${Math.round(pct * 100)}%` }} />
      </div>
      <div className="pred-pct">{(pct * 100).toFixed(0)}%</div>
      {odds && <div className="pred-odds">{odds}x</div>}
    </div>
  )
}

function QuickBetModal({ fixture, onClose }) {
  const [market, setMarket] = useState('1X2')
  const [selection, setSelection] = useState('Home')
  const [odds, setOdds] = useState('')
  const [stake, setStake] = useState('')
  const [saving, setSaving] = useState(false)

  const MARKETS = ['1X2', 'BTTS Yes', 'BTTS No', 'Over 2.5', 'Over 3.5', 'Under 2.5', 'Corners O9.5', 'Corners O10.5', 'Fouls O20', 'Fouls O25']
  const SELECTIONS_MAP = {
    '1X2': ['Home', 'Draw', 'Away'],
    'BTTS Yes': ['Yes'], 'BTTS No': ['No'],
    'Over 2.5': ['Over'], 'Over 3.5': ['Over'], 'Under 2.5': ['Under'],
    'Corners O9.5': ['Over', 'Under'], 'Corners O10.5': ['Over', 'Under'],
    'Fouls O20': ['Over', 'Under'], 'Fouls O25': ['Over', 'Under'],
  }

  const save = async () => {
    if (!odds || !stake) return toast.error('Please enter odds and stake')
    setSaving(true)
    try {
      await betsApi.create({
        match_date: fixture.date || new Date().toISOString().split('T')[0],
        league: fixture.league,
        home_team: fixture.home_team,
        away_team: fixture.away_team,
        market, selection,
        odds: parseFloat(odds),
        stake: parseFloat(stake),
      })
      toast.success('Bet logged! 🎉')
      onClose()
    } catch {
      toast.error('Failed to save bet')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">Log Bet — {fixture.home_team} vs {fixture.away_team}</div>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="input-group">
          <label className="input-label">Market</label>
          <select className="input-field" value={market} onChange={e => { setMarket(e.target.value); setSelection(SELECTIONS_MAP[e.target.value]?.[0] || 'Home') }}>
            {MARKETS.map(m => <option key={m}>{m}</option>)}
          </select>
        </div>

        <div className="input-group">
          <label className="input-label">Selection</label>
          <select className="input-field" value={selection} onChange={e => setSelection(e.target.value)}>
            {(SELECTIONS_MAP[market] || ['Home','Draw','Away']).map(s => <option key={s}>{s}</option>)}
          </select>
        </div>

        <div className="grid-2" style={{ gap: 12 }}>
          <div className="input-group">
            <label className="input-label">Odds</label>
            <input className="input-field" type="number" step="0.01" min="1" placeholder="e.g. 2.10" value={odds} onChange={e => setOdds(e.target.value)} />
          </div>
          <div className="input-group">
            <label className="input-label">Stake (R)</label>
            <input className="input-field" type="number" step="0.01" min="0" placeholder="e.g. 50" value={stake} onChange={e => setStake(e.target.value)} />
          </div>
        </div>

        {odds && stake && (
          <div style={{ padding: '12px 16px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)', marginBottom: 16, fontSize: 13 }}>
            <span className="text-secondary">Potential return: </span>
            <span className="text-teal font-bold">R{(parseFloat(odds || 0) * parseFloat(stake || 0)).toFixed(2)}</span>
            <span className="text-secondary"> · Profit: </span>
            <span className="text-green font-bold">R{((parseFloat(odds || 0) - 1) * parseFloat(stake || 0)).toFixed(2)}</span>
          </div>
        )}

        <button className="btn btn-primary btn-full" onClick={save} disabled={saving}>
          {saving ? <span className="spinner" /> : '💾 Save Bet'}
        </button>
      </div>
    </div>
  )
}

export default function PredictionPanel({ fixture, prediction, loading }) {
  const [showBetModal, setShowBetModal] = useState(false)
  const [activeTab, setActiveTab] = useState('outcome')

  if (loading) {
    return (
      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 400 }}>
        <div style={{ textAlign: 'center' }}>
          <div className="spinner" style={{ width: 40, height: 40, borderWidth: 3, margin: '0 auto 16px' }} />
          <div className="text-secondary text-sm">Running predictions across all models...</div>
        </div>
      </div>
    )
  }

  return (
    <div className="card card-glow animate-fade-in">
      {/* Match Header */}
      <div style={{ textAlign: 'center', marginBottom: 20 }}>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, letterSpacing: 1, textTransform: 'uppercase', marginBottom: 8 }}>
          {LEAGUE_LABELS[fixture.league] || fixture.league}
        </div>
        <div style={{ fontSize: 20, fontWeight: 800, letterSpacing: -0.5 }}>
          {fixture.home_team} <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>vs</span> {fixture.away_team}
        </div>
        {fixture.date && (
          <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
            📅 {fixture.date} {fixture.time && `· ⏰ ${fixture.time?.slice(0,5)}`}
          </div>
        )}
      </div>

      {!prediction ? (
        <div className="empty-state">
          <div className="empty-state-text">Prediction loading...</div>
        </div>
      ) : (
        <>
          {/* ELO display */}
          {prediction.meta && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: 24, marginBottom: 16, fontSize: 12, color: 'var(--text-muted)' }}>
              <span>ELO: <strong style={{ color: 'var(--teal)' }}>{Math.round(prediction.meta.home_elo || 1500)}</strong></span>
              <span style={{ color: 'var(--border)' }}>·</span>
              <span>Diff: <strong style={{ color: prediction.meta.elo_diff > 0 ? 'var(--green)' : 'var(--red)' }}>
                {prediction.meta.elo_diff > 0 ? '+' : ''}{Math.round(prediction.meta.elo_diff || 0)}
              </strong></span>
              <span style={{ color: 'var(--border)' }}>·</span>
              <span>ELO: <strong style={{ color: 'var(--amber)' }}>{Math.round(prediction.meta.away_elo || 1500)}</strong></span>
            </div>
          )}

          {/* xG Display */}
          {prediction.goals && (
            <div className="xg-display">
              <div className="xg-team">
                <div className="xg-val home">{prediction.goals.xg_home?.toFixed(2)}</div>
                <div className="xg-lbl">xG Home</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{fixture.home_team}</div>
              </div>
              <div className="xg-sep">—</div>
              <div className="xg-team">
                <div className="xg-val away">{prediction.goals.xg_away?.toFixed(2)}</div>
                <div className="xg-lbl">xG Away</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{fixture.away_team}</div>
              </div>
            </div>
          )}

          {/* Tabs */}
          <div className="tab-bar" style={{ marginTop: 16 }}>
            {['outcome','goals','corners','fouls'].map(t => (
              <button key={t} className={`tab-item${activeTab === t ? ' active' : ''}`} onClick={() => setActiveTab(t)}>
                {{ outcome: '1X2', goals: 'Goals', corners: 'Corners', fouls: 'Fouls' }[t]}
              </button>
            ))}
          </div>

          <div className="prediction-section">
            {activeTab === 'outcome' && prediction.outcome && (
              <>
                <ProbBar label={fixture.home_team.split(' ')[0]} pct={prediction.outcome.prob_home} type="home" odds={prediction.outcome.implied_home_odds} />
                <ProbBar label="Draw" pct={prediction.outcome.prob_draw} type="draw" odds={prediction.outcome.implied_draw_odds} />
                <ProbBar label={fixture.away_team.split(' ')[0]} pct={prediction.outcome.prob_away} type="away" odds={prediction.outcome.implied_away_odds} />
              </>
            )}

            {activeTab === 'goals' && prediction.goals && (
              <>
                <ProbBar label="BTTS" pct={prediction.goals.prob_btts} type="btts" odds={prediction.goals.implied_btts_yes_odds} />
                <ProbBar label="Over 2.5" pct={prediction.goals.prob_over_2_5} type="over" odds={prediction.goals.implied_over25_odds} />
                <ProbBar label="Over 3.5" pct={prediction.goals.prob_over_3_5} type="over" />
              </>
            )}

            {activeTab === 'corners' && prediction.corners && (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12, fontSize: 13 }}>
                  <span className="text-secondary">Exp. Corners: <strong className="text-teal">{prediction.corners.exp_total_corners?.toFixed(1)}</strong></span>
                  <span className="text-secondary">Home: <strong>{prediction.corners.exp_home_corners?.toFixed(1)}</strong> · Away: <strong>{prediction.corners.exp_away_corners?.toFixed(1)}</strong></span>
                </div>
                <ProbBar label="Over 9.5" pct={prediction.corners.prob_corners_over_9_5} type="corner" />
                <ProbBar label="Over 10.5" pct={prediction.corners.prob_corners_over_10_5} type="corner" />
                <ProbBar label="Over 11.5" pct={prediction.corners.prob_corners_over_11_5} type="corner" />
              </>
            )}

            {activeTab === 'fouls' && prediction.fouls && (
              <>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12, fontSize: 13 }}>
                  <span className="text-secondary">Exp. Fouls: <strong className="text-amber">{prediction.fouls.exp_total_fouls?.toFixed(1)}</strong></span>
                  <span className="text-secondary">Home: <strong>{prediction.fouls.exp_home_fouls?.toFixed(1)}</strong> · Away: <strong>{prediction.fouls.exp_away_fouls?.toFixed(1)}</strong></span>
                </div>
                <ProbBar label="Over 20" pct={prediction.fouls.prob_fouls_over_20} type="foul" />
                <ProbBar label="Over 25" pct={prediction.fouls.prob_fouls_over_25} type="foul" />
                <ProbBar label="Over 30" pct={prediction.fouls.prob_fouls_over_30} type="foul" />
              </>
            )}
          </div>

          <button id="log-bet-btn" className="btn btn-secondary btn-full" style={{ marginTop: 16 }} onClick={() => setShowBetModal(true)}>
            💰 Log a Bet on This Match
          </button>
        </>
      )}

      {showBetModal && <QuickBetModal fixture={fixture} onClose={() => setShowBetModal(false)} />}
    </div>
  )
}

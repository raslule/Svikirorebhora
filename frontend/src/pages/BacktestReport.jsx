import { useState, useEffect } from 'react'
import { admin } from '../api'
import toast from 'react-hot-toast'

export default function BacktestReport() {
  const [running, setRunning] = useState(false)
  const [metrics, setMetrics] = useState(null)
  const [modelInfo, setModelInfo] = useState([])

  const fetchModelInfo = async () => {
    try {
      const { data } = await admin.modelsInfo()
      if (data?.models) {
        setModelInfo(data.models)
      }
    } catch {
      // Fallback silent
    }
  }

  useEffect(() => {
    fetchModelInfo()
  }, [])

  const runBacktest = async () => {
    setRunning(true)
    try {
      const { data } = await admin.retrain()
      setMetrics(data.metrics)
      toast.success('Backtest complete!')
      await fetchModelInfo()
    } catch {
      toast.error('Backtest failed — ensure all data is seeded')
    } finally {
      setRunning(false)
    }
  }

  const runUpdate = async () => {
    toast.loading('Fetching latest data from football-data.co.uk...')
    try {
      const { data } = await admin.updateData()
      toast.dismiss()
      toast.success(`Data updated! ${JSON.stringify(data.summary)}`)
    } catch {
      toast.dismiss()
      toast.error('Update failed')
    }
  }
  const outcomeModelInfo = modelInfo.find(m => m.id === 'outcome')
  const brierTargetStr = outcomeModelInfo?.target || 'Brier Score < 0.22'
  const brierTargetMatch = brierTargetStr.match(/< ([\d\.]+)/)
  const brierTargetVal = brierTargetMatch ? parseFloat(brierTargetMatch[1]) : 0.22

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Model Backtest Report</h1>
        <p className="page-subtitle">Walk-forward validation — Train ≤ 2022, Val 2023-24, Test 2025+</p>
      </div>

      <div className="page-body">
        {/* Admin Controls */}
        <div className="card mb-6">
          <div className="card-title" style={{ marginBottom: 16 }}>⚙️ Admin Controls</div>
          <div className="flex gap-3" style={{ gap: 12, flexWrap: 'wrap' }}>
            <button id="run-backtest-btn" className="btn btn-primary" onClick={runBacktest} disabled={running}>
              {running ? <><span className="spinner" style={{ width: 14, height: 14 }} /> Running...</> : '🚀 Run Full Backtest & Retrain'}
            </button>
            <button id="update-data-btn" className="btn btn-secondary" onClick={runUpdate}>
              🔄 Fetch Latest Data
            </button>
          </div>
          <div style={{ marginTop: 12, fontSize: 12, color: 'var(--text-muted)' }}>
            💡 Retraining triggers a full walk-forward backtest on 45k+ matches. Dixon-Coles optimization typically takes 1–3 minutes.
          </div>
        </div>

        {/* Model Target Card */}
        <div className="stat-grid mb-6">
          <div className="stat-card">
            <div className="stat-label">Brier Target</div>
            <div className="stat-value text-teal">&lt; {brierTargetVal}</div>
            <div className="stat-sub">1X2 Outcome Model</div>
          </div>
          {metrics?.outcome && (
            <div className={`stat-card ${metrics.outcome.ensemble_brier < brierTargetVal ? 'green' : 'red'}`}>
              <div className="stat-label">Ensemble Brier</div>
              <div className="stat-value" style={{ color: metrics.outcome.ensemble_brier < brierTargetVal ? 'var(--green)' : 'var(--red)', fontSize: 24 }}>
                {metrics.outcome.ensemble_brier?.toFixed(4)}
              </div>
              <div className="stat-sub">{metrics.outcome.ensemble_brier < brierTargetVal ? '✓ Target Met' : '✗ Above Target'}</div>
            </div>
          )}
          {metrics?.corners?.home && (
            <div className="stat-card amber">
              <div className="stat-label">Corners MAE</div>
              <div className="stat-value" style={{ fontSize: 24 }}>{metrics.corners.home?.mae?.toFixed(3)}</div>
              <div className="stat-sub">Home corners</div>
            </div>
          )}
          {metrics?.fouls?.home && (
            <div className="stat-card green">
              <div className="stat-label">Fouls MAE</div>
              <div className="stat-value" style={{ fontSize: 24 }}>{metrics.fouls.home?.mae?.toFixed(3)}</div>
              <div className="stat-sub">Home fouls MAE</div>
            </div>
          )}
        </div>

        {/* Model Architecture Overview (Dynamically rendered from backend GET /api/models/info) */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 20 }}>🧠 Model Architecture Overview</div>
          {(modelInfo.length > 0 ? modelInfo : [
            { id: 'outcome', name: '1X2 Outcome', architecture: 'XGBoost + Dixon-Coles (70/30 Fusion)', target: 'Brier Score < 0.22', badge: 'badge-teal' },
            { id: 'goals', name: 'xG & BTTS', architecture: 'Dixon-Coles Bivariate Poisson (MLE, L-BFGS-B)', target: 'BTTS Log-Loss', badge: 'badge-purple' },
            { id: 'corners', name: 'Corners', architecture: 'Negative Binomial GLM', target: 'MAE < 2.5 corners', badge: 'badge-amber' },
            { id: 'fouls', name: 'Fouls', architecture: 'Poisson Regression + Referee Regime', target: 'MAE < 3.0 fouls', badge: 'badge-green' },
            { id: 'cards', name: 'Cards', architecture: 'Poisson GLM + Referee Strictness Scaling', target: 'MAE < 1.5 cards', badge: 'badge-rose' },
            { id: 'shots', name: 'Total Shots & SOT', architecture: 'Negative Binomial GLM + Dixon-Coles xG', target: 'MAE < 4.0 shots', badge: 'badge-cyan' },
          ]).map(m => {
            let metricText = 'Run backtest'
            let pass = null
            if (m.id === 'outcome' && metrics?.outcome) {
              metricText = `${metrics.outcome.ensemble_brier?.toFixed(4)} Brier`
              pass = metrics.outcome.pass
            } else if (m.id === 'goals' && metrics?.goals) {
              metricText = `${metrics.goals.btts_log_loss} LL`
            } else if (m.id === 'corners' && metrics?.corners?.home) {
              metricText = `${metrics.corners.home.mae?.toFixed(3)} MAE`
            } else if (m.id === 'fouls' && metrics?.fouls?.home) {
              metricText = `${metrics.fouls.home.mae?.toFixed(3)} MAE`
            } else if (m.id === 'cards' && metrics?.cards) {
              metricText = `${metrics.cards.mae_total_cards?.toFixed(3)} MAE`
            } else if (m.id === 'shots' && metrics?.shots) {
              metricText = `${metrics.shots.mae_total_shots?.toFixed(3)} MAE`
            }

            return (
              <div key={m.id || m.name} style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '16px 0', borderBottom: '1px solid var(--border)' }}>
                <div style={{ flex: '0 0 140px' }}>
                  <div style={{ fontWeight: 700, fontSize: 14 }}>{m.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{m.target}</div>
                </div>
                <div style={{ flex: 1, fontSize: 13, color: 'var(--text-secondary)' }}>
                  <div>{m.architecture}</div>
                  {m.artifact?.last_modified && (
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                      Artifact updated: {new Date(m.artifact.last_modified).toLocaleString()}
                      {m.artifact.home_adv !== undefined && ` · home_adv=${m.artifact.home_adv}, rho=${m.artifact.rho}, teams=${m.artifact.teams_count}`}
                    </div>
                  )}
                </div>
                <div>
                  <span className={`card-badge ${m.badge}`}>{metricText}</span>
                  {pass === true && <span style={{ marginLeft: 6 }}>✅</span>}
                  {pass === false && <span style={{ marginLeft: 6 }}>❌</span>}
                </div>
              </div>
            )
          })}

          <div style={{ marginTop: 20, padding: '16px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)', fontSize: 12, color: 'var(--text-secondary)' }}>
            <strong>Outcome / Corners / Fouls data split:</strong> Train (2000–2022) · Validation (2023–2024) · Test (2025+) &nbsp;|&nbsp;
            <strong>Dixon-Coles window:</strong> Full train split (≤2022), time-weighted by half-life=365 days — older matches receive exponentially lower weight &nbsp;|&nbsp;
            <strong>Data source:</strong> football-data.co.uk (free, no subscription) &nbsp;|&nbsp;
            <strong>Features:</strong> ELO, rolling form (5-match), rest days, referee strictness regime, ghost-game flag
          </div>
        </div>
      </div>
    </div>
  )
}

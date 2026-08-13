import { useState } from 'react'
import { admin } from '../api'
import toast from 'react-hot-toast'

export default function BacktestReport() {
  const [running, setRunning] = useState(false)
  const [metrics, setMetrics] = useState(null)

  const runBacktest = async () => {
    setRunning(true)
    try {
      const { data } = await admin.retrain()
      setMetrics(data.metrics)
      toast.success('Backtest complete!')
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

  const TARGET = 0.19

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Model Backtest Report</h1>
        <p className="page-subtitle">Walk-forward validation — Train ≤2022, Val 2023-24, Test 2025+</p>
      </div>

      <div className="page-body">
        {/* Admin Controls */}
        <div className="card mb-6">
          <div className="card-title" style={{ marginBottom: 16 }}>⚙️ Admin Controls</div>
          <div className="flex gap-3" style={{ gap: 12, flexWrap: 'wrap' }}>
            <button id="run-backtest-btn" className="btn btn-primary" onClick={runBacktest} disabled={running}>
              {running ? <><span className="spinner" style={{ width: 14, height: 14 }} /> Running...</> : '🔬 Run Full Backtest & Retrain'}
            </button>
            <button id="update-data-btn" className="btn btn-secondary" onClick={runUpdate}>
              🔄 Fetch Latest Data
            </button>
          </div>
          <div style={{ marginTop: 12, fontSize: 12, color: 'var(--text-muted)' }}>
            ⚠️ Retraining on 45k+ matches may take 5-15 minutes. Data auto-updates every Monday 06:00 SAST.
          </div>
        </div>

        {/* Model Target Card */}
        <div className="stat-grid mb-6">
          <div className="stat-card">
            <div className="stat-label">Brier Target</div>
            <div className="stat-value text-teal">&lt; {TARGET}</div>
            <div className="stat-sub">1X2 Outcome Model</div>
          </div>
          {metrics?.outcome && (
            <div className={`stat-card ${metrics.outcome.ensemble_brier < TARGET ? 'green' : 'red'}`}>
              <div className="stat-label">Ensemble Brier</div>
              <div className="stat-value" style={{ color: metrics.outcome.ensemble_brier < TARGET ? 'var(--green)' : 'var(--red)', fontSize: 24 }}>
                {metrics.outcome.ensemble_brier?.toFixed(4)}
              </div>
              <div className="stat-sub">{metrics.outcome.pass ? '✅ Target Met' : '❌ Below Target'}</div>
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
            <div className="stat-card">
              <div className="stat-label">Fouls R²</div>
              <div className="stat-value" style={{ fontSize: 24 }}>{metrics.fouls.home?.r2?.toFixed(3)}</div>
              <div className="stat-sub">Home fouls</div>
            </div>
          )}
        </div>

        {/* Model Architecture */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 20 }}>🧠 Model Architecture Overview</div>
          {[
            { name: '1X2 Outcome', model: 'XGBoost + Logistic Regression (60/40 Ensemble)', target: 'Brier Score < 0.19', metric: metrics?.outcome ? `${metrics.outcome.ensemble_brier?.toFixed(4)} Brier` : 'Run backtest', badge: 'badge-teal', pass: metrics?.outcome?.pass },
            { name: 'xG & BTTS', model: 'Dixon-Coles Bivariate Poisson (MLE, L-BFGS-B)', target: 'BTTS Log-Loss', metric: metrics?.goals ? `${metrics.goals.btts_log_loss} LL` : 'Run backtest', badge: 'badge-purple', pass: null },
            { name: 'Corners', model: 'Negative Binomial Regression + Ridge', target: 'MAE < 2.5 corners', metric: metrics?.corners?.home ? `${metrics.corners.home.mae?.toFixed(3)} MAE` : 'Run backtest', badge: 'badge-amber', pass: null },
            { name: 'Fouls', model: 'Ridge Linear Regression + Referee Regime', target: 'R² > 0.4', metric: metrics?.fouls?.home ? `R²=${metrics.fouls.home.r2?.toFixed(3)}` : 'Run backtest', badge: 'badge-green', pass: null },
          ].map(m => (
            <div key={m.name} style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '16px 0', borderBottom: '1px solid var(--border)' }}>
              <div style={{ flex: '0 0 140px' }}>
                <div style={{ fontWeight: 700, fontSize: 14 }}>{m.name}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>{m.target}</div>
              </div>
              <div style={{ flex: 1, fontSize: 13, color: 'var(--text-secondary)' }}>{m.model}</div>
              <div>
                <span className={`card-badge ${m.badge}`}>{m.metric}</span>
                {m.pass === true && <span style={{ marginLeft: 6 }}>✅</span>}
                {m.pass === false && <span style={{ marginLeft: 6 }}>❌</span>}
              </div>
            </div>
          ))}

          <div style={{ marginTop: 20, padding: '16px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)', fontSize: 12, color: 'var(--text-secondary)' }}>
            <strong>Data split:</strong> Train (2000–2022) · Validation (2023–2024) · Test (2025+) &nbsp;|&nbsp;
            <strong>Data source:</strong> football-data.co.uk (free, no subscription) &nbsp;|&nbsp;
            <strong>Features:</strong> ELO, rolling form (5-match), rest days, referee strictness regime, ghost-game flag
          </div>
        </div>
      </div>
    </div>
  )
}

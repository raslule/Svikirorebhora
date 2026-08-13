export default function TeamAnalytics() {
  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Team Analytics</h1>
        <p className="page-subtitle">Deep-dive team statistics — ELO trend, rolling form, attack/defense profile</p>
      </div>
      <div className="page-body">
        <div className="card" style={{ textAlign: 'center', padding: '80px 24px' }}>
          <div style={{ fontSize: 64, marginBottom: 20 }}>📊</div>
          <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 10 }}>Team Analytics</div>
          <div className="text-secondary" style={{ maxWidth: 400, margin: '0 auto', fontSize: 14 }}>
            Select a team from any league to view their ELO rating history, 5-match rolling form,
            attack/defense strength, referee profile, and head-to-head record.
          </div>
          <div style={{ marginTop: 32, padding: '20px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', display: 'inline-block' }}>
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>Available after database is seeded</div>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
              {['ELO Trend', 'Rolling xG', 'Attack/Def Radar', 'H2H Stats', 'Referee Profile'].map(f => (
                <span key={f} className="card-badge badge-teal">{f}</span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

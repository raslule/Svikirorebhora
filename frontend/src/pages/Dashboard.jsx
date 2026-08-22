import { useState, useEffect } from 'react'
import toast from 'react-hot-toast'
import { matches as matchesApi, predictions as predApi } from '../api'
import PredictionPanel from '../components/PredictionPanel'

const LEAGUES = [
  { id: 'premier-league', label: '🏴󠁧󠁢󠁥󠁮󠁧󠁿 EPL' },
  { id: 'la-liga',        label: '🇪🇸 La Liga' },
  { id: 'serie-a',        label: '🇮🇹 Serie A' },
  { id: 'ligue-1',        label: '🇫🇷 Ligue 1' },
  { id: 'bundesliga',     label: '🇩🇪 Bundesliga' },
]

export default function Dashboard() {
  const [league, setLeague] = useState('premier-league')
  const [fixtures, setFixtures]   = useState([])
  const [loadingF, setLoadingF]   = useState(false)
  const [selected, setSelected]   = useState(null)
  const [prediction, setPrediction] = useState(null)
  const [loadingP, setLoadingP]   = useState(false)

  useEffect(() => {
    fetchFixtures()
  }, [league])

  const fetchFixtures = async () => {
    setLoadingF(true)
    setSelected(null)
    setPrediction(null)
    try {
      const { data } = await matchesApi.upcoming({ league })
      setFixtures(data.slice(0, 20))
    } catch {
      // Fallback: show placeholder fixtures
      setFixtures(PLACEHOLDER_FIXTURES[league] || [])
    } finally {
      setLoadingF(false)
    }
  }

  const handleFixtureClick = async (fx) => {
    setSelected(fx)
    setPrediction(null)
    setLoadingP(true)
    try {
      const { data } = await predApi.predict({
        home_team: fx.home_team,
        away_team: fx.away_team,
        league: fx.league,
        match_date: fx.date || null,
      })
      setPrediction(data)
    } catch (e) {
      toast.error('Prediction failed — check API is running')
    } finally {
      setLoadingP(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Match Dashboard</h1>
        <p className="page-subtitle">Select a fixture to see AI-powered predictions across all markets</p>
        <div className="league-tabs">
          {LEAGUES.map(l => (
            <button
              key={l.id}
              id={`league-tab-${l.id}`}
              className={`league-tab${league === l.id ? ' active' : ''}`}
              data-league={l.id}
              onClick={() => setLeague(l.id)}
            >{l.label}</button>
          ))}
        </div>
      </div>

      <div className="page-body">
        <div className="grid-2" style={{ gap: 24, alignItems: 'start' }}>
          {/* Fixtures Panel */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 style={{ fontSize: 15, fontWeight: 700 }}>Upcoming Fixtures</h2>
              <button className="btn btn-secondary btn-sm" onClick={fetchFixtures} disabled={loadingF}>
                {loadingF ? <span className="spinner" style={{ width: 14, height: 14 }} /> : '↻ Refresh'}
              </button>
            </div>

            {loadingF ? (
              <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}>
                <div className="spinner" style={{ width: 32, height: 32, borderWidth: 3 }} />
              </div>
            ) : fixtures.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">📅</div>
                <div className="empty-state-title">No fixtures available</div>
                <div className="empty-state-text">Check back after the next match round</div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {fixtures.map((fx, i) => (
                  <FixtureRow
                    key={i}
                    fixture={fx}
                    isSelected={selected?.home_team === fx.home_team && selected?.away_team === fx.away_team}
                    onClick={() => handleFixtureClick(fx)}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Prediction Panel */}
          <div>
            {!selected ? (
              <div className="card" style={{ textAlign: 'center', padding: '60px 24px' }}>
                <div style={{ fontSize: 48, marginBottom: 16 }}>🎯</div>
                <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 8 }}>Select a fixture</div>
                <div className="text-secondary text-sm">Click any match on the left to see full AI predictions</div>
              </div>
            ) : (
              <PredictionPanel
                fixture={selected}
                prediction={prediction}
                loading={loadingP}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

function FixtureRow({ fixture, isSelected, onClick }) {
  return (
    <div
      id={`fixture-${fixture.home_team?.replace(/\s/g,'')}-vs-${fixture.away_team?.replace(/\s/g,'')}`}
      className="fixture-card"
      style={{ borderColor: isSelected ? 'rgba(0,212,255,0.4)' : undefined, background: isSelected ? 'var(--bg-card)' : undefined }}
      onClick={onClick}
    >
      <div className="team-side">
        <div className="team-name">{fixture.home_team}</div>
        <div className="team-form" style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>Home</div>
      </div>

      <div className="fixture-vs">
        <div className="vs-label">VS</div>
        {fixture.time && fixture.time !== 'nan' && (
          <div className="vs-time">{fixture.time?.slice(0,5)}</div>
        )}
        {fixture.date && (
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
            {(() => {
              const d = new Date(fixture.kickoff_utc || fixture.date);
              if (!isNaN(d.getTime())) {
                return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' });
              }
              return fixture.date ? fixture.date.replace(' SAST', '') : '';
            })()}
          </div>
        )}
      </div>

      <div className="team-side" style={{ alignItems: 'flex-end' }}>
        <div className="team-name">{fixture.away_team}</div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>Away</div>
      </div>
    </div>
  )
}

// Fallback placeholder fixtures when API has no data
const PLACEHOLDER_FIXTURES = {
  'premier-league': [
    { league: 'premier-league', home_team: 'Arsenal', away_team: 'Chelsea', date: '2026-08-16', time: '15:00' },
    { league: 'premier-league', home_team: 'Liverpool', away_team: 'Man City', date: '2026-08-16', time: '17:30' },
    { league: 'premier-league', home_team: 'Man Utd', away_team: 'Tottenham', date: '2026-08-17', time: '14:00' },
    { league: 'premier-league', home_team: 'Aston Villa', away_team: 'Newcastle', date: '2026-08-17', time: '16:30' },
  ],
  'la-liga': [
    { league: 'la-liga', home_team: 'Real Madrid', away_team: 'Barcelona', date: '2026-08-16', time: '21:00' },
    { league: 'la-liga', home_team: 'Atletico Madrid', away_team: 'Sevilla', date: '2026-08-17', time: '19:00' },
  ],
  'serie-a': [
    { league: 'serie-a', home_team: 'Inter Milan', away_team: 'AC Milan', date: '2026-08-16', time: '20:45' },
    { league: 'serie-a', home_team: 'Juventus', away_team: 'Napoli', date: '2026-08-17', time: '18:00' },
  ],
  'ligue-1': [
    { league: 'ligue-1', home_team: 'Paris SG', away_team: 'Marseille', date: '2026-08-16', time: '21:00' },
    { league: 'ligue-1', home_team: 'Monaco', away_team: 'Lyon', date: '2026-08-17', time: '19:00' },
  ],
  'bundesliga': [
    { league: 'bundesliga', home_team: 'Bayern Munich', away_team: 'Borussia Dortmund', date: '2026-08-16', time: '18:30' },
    { league: 'bundesliga', home_team: 'Leverkusen', away_team: 'Leipzig', date: '2026-08-17', time: '15:30' },
  ],
}

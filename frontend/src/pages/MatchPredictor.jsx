import { useState } from 'react'
import { predictions as predApi } from '../api'
import toast from 'react-hot-toast'
import PredictionPanel from '../components/PredictionPanel'

const LEAGUES = [
  { id: 'premier-league', label: '🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League', teams: ['Arsenal','Chelsea','Liverpool','Man City','Man Utd','Tottenham','Aston Villa','Newcastle','West Ham','Brighton','Everton','Fulham','Brentford','Crystal Palace','Wolves','Bournemouth','Ipswich','Leicester','Southampton','Nottm Forest'] },
  { id: 'la-liga',        label: '🇪🇸 La Liga',        teams: ['Real Madrid','Barcelona','Atletico Madrid','Sevilla','Valencia','Villarreal','Athletic Bilbao','Real Sociedad','Betis','Osasuna','Girona','Las Palmas','Celta Vigo','Getafe','Leganes','Mallorca','Alaves','Valladolid','Espanyol','Rayo Vallecano'] },
  { id: 'serie-a',        label: '🇮🇹 Serie A',        teams: ['Inter Milan','AC Milan','Juventus','Napoli','Roma','Lazio','Atalanta','Fiorentina','Torino','Bologna','Udinese','Genoa','Lecce','Monza','Cagliari','Empoli','Venezia','Parma','Como','Hellas Verona'] },
  { id: 'ligue-1',        label: '🇫🇷 Ligue 1',        teams: ['Paris SG','Marseille','Monaco','Lyon','Lille','Lens','Nice','Rennes','Toulouse','Reims','Strasbourg','Nantes','Brest','Metz','Clermont','Le Havre','Lorient','Montpellier','Auxerre','Angers'] },
  { id: 'bundesliga',     label: '🇩🇪 Bundesliga',     teams: ['Bayern Munich','Borussia Dortmund','Leverkusen','Leipzig','Eintracht Frankfurt','Wolfsburg','Hoffenheim','Freiburg','Union Berlin','Werder Bremen','Augsburg','Stuttgart','Mainz','Heidenheim','Kiel','St. Pauli'] },
]

export default function MatchPredictor() {
  const [league, setLeague] = useState('premier-league')
  const [homeTeam, setHomeTeam] = useState('')
  const [awayTeam, setAwayTeam] = useState('')
  const [matchDate, setMatchDate] = useState('')
  const [prediction, setPrediction] = useState(null)
  const [loading, setLoading] = useState(false)

  const currentLeague = LEAGUES.find(l => l.id === league)

  const handlePredict = async () => {
    if (!homeTeam || !awayTeam) return toast.error('Select both teams')
    if (homeTeam === awayTeam) return toast.error('Teams must be different')
    setLoading(true)
    setPrediction(null)
    try {
      const { data } = await predApi.predict({
        home_team: homeTeam, away_team: awayTeam,
        league, match_date: matchDate || null,
      })
      setPrediction(data)
    } catch (e) {
      toast.error('Prediction failed — ensure the backend is running')
    } finally {
      setLoading(false)
    }
  }

  const fixture = { home_team: homeTeam, away_team: awayTeam, league, date: matchDate }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Match Predictor</h1>
        <p className="page-subtitle">Select any home & away team to get full AI predictions across all 5 markets</p>
      </div>

      <div className="page-body">
        <div className="grid-2" style={{ gap: 24, alignItems: 'start' }}>
          {/* Controls */}
          <div>
            <div className="card">
              <div className="card-header">
                <div className="card-title">⚙️ Configure Match</div>
                <span className="card-badge badge-teal">Manual Mode</span>
              </div>

              <div className="input-group">
                <label className="input-label">Competition</label>
                <select id="predictor-league" className="input-field" value={league} onChange={e => { setLeague(e.target.value); setHomeTeam(''); setAwayTeam('') }}>
                  {LEAGUES.map(l => <option key={l.id} value={l.id}>{l.label}</option>)}
                </select>
              </div>

              <div className="grid-2" style={{ gap: 12 }}>
                <div className="input-group">
                  <label className="input-label">Home Team</label>
                  <select id="predictor-home" className="input-field" value={homeTeam} onChange={e => setHomeTeam(e.target.value)}>
                    <option value="">Select team</option>
                    {currentLeague?.teams.filter(t => t !== awayTeam).map(t => <option key={t}>{t}</option>)}
                  </select>
                </div>
                <div className="input-group">
                  <label className="input-label">Away Team</label>
                  <select id="predictor-away" className="input-field" value={awayTeam} onChange={e => setAwayTeam(e.target.value)}>
                    <option value="">Select team</option>
                    {currentLeague?.teams.filter(t => t !== homeTeam).map(t => <option key={t}>{t}</option>)}
                  </select>
                </div>
              </div>

              <div className="input-group">
                <label className="input-label">Match Date (optional)</label>
                <input id="predictor-date" type="date" className="input-field" value={matchDate} onChange={e => setMatchDate(e.target.value)} />
              </div>

              <button id="run-prediction-btn" className="btn btn-primary btn-full btn-lg" onClick={handlePredict} disabled={loading || !homeTeam || !awayTeam}>
                {loading ? <><span className="spinner" style={{ width: 16, height: 16 }} /> Predicting...</> : '🎯 Run Prediction'}
              </button>
            </div>

            {/* Model guide */}
            <div className="card" style={{ marginTop: 16 }}>
              <div className="card-title" style={{ marginBottom: 14 }}>🧠 Models Used</div>
              {[
                { label: '1X2 Outcome', model: 'XGBoost + Dixon-Coles 70/30 Fusion', badge: 'badge-teal' },
                { label: 'xG & BTTS', model: 'Dixon-Coles Bivariate Poisson', badge: 'badge-purple' },
                { label: 'Corners', model: 'Negative Binomial GLM', badge: 'badge-amber' },
                { label: 'Fouls', model: 'Poisson Regression + Referee Regime', badge: 'badge-green' },
                { label: 'Cards', model: 'Poisson GLM + Referee Strictness', badge: 'badge-rose' },
                { label: 'Total Shots & SOT', model: 'Negative Binomial GLM', badge: 'badge-cyan' },
              ].map(m => (
                <div key={m.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{m.label}</span>
                  <span className={`card-badge ${m.badge}`}>{m.model}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Results */}
          <div>
            {(!homeTeam || !awayTeam) && !prediction ? (
              <div className="card" style={{ textAlign: 'center', padding: '60px 24px' }}>
                <div style={{ fontSize: 64, marginBottom: 16 }}>🎯</div>
                <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Ready to Predict</div>
                <div className="text-secondary text-sm">Select league, home & away team<br />then click Run Prediction</div>
              </div>
            ) : (
              <PredictionPanel
                fixture={fixture}
                prediction={prediction}
                loading={loading}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

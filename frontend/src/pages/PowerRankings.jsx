import React, { useState, useEffect } from 'react';
import api from '../api';
import './PowerRankings.css'; 

const PowerRankings = () => {
  const [league, setLeague] = useState('premier-league');
  const [globalRankings, setGlobalRankings] = useState({});
  const [loading, setLoading] = useState(true);

  const LEAGUES = [
    { id: 'premier-league', name: 'Premier League', teams: ['Arsenal','Chelsea','Liverpool','Man City','Man United','Tottenham','Aston Villa','Newcastle','West Ham','Brighton','Everton','Fulham','Brentford','Crystal Palace','Wolves','Bournemouth','Ipswich','Coventry','Hull',"Nott'm Forest"] },
    { id: 'la-liga',        name: 'La Liga',        teams: ['Real Madrid','Barcelona','Ath Madrid','Sevilla','Valencia','Villarreal','Ath Bilbao','Sociedad','Betis','Osasuna','Girona','Las Palmas','Celta','Getafe','Leganes','Mallorca','Alaves','Valladolid','Espanol','Vallecano'] },
    { id: 'serie-a',        name: 'Serie A',        teams: ['Inter','Milan','Juventus','Napoli','Roma','Lazio','Atalanta','Fiorentina','Torino','Bologna','Udinese','Genoa','Lecce','Monza','Cagliari','Empoli','Venezia','Parma','Como','Verona'] },
    { id: 'ligue-1',        name: 'Ligue 1',        teams: ['Paris SG','Marseille','Monaco','Lyon','Lille','Lens','Nice','Rennes','Toulouse','Reims','Strasbourg','Nantes','Brest','Metz','Clermont','Le Havre','Lorient','Montpellier','Auxerre','Angers'] },
    { id: 'bundesliga',     name: 'Bundesliga',     teams: ['Bayern Munich','Dortmund','Leverkusen','RB Leipzig','Ein Frankfurt','Wolfsburg','Hoffenheim','Freiburg','Union Berlin','Werder Bremen','Augsburg','Stuttgart','Mainz','Heidenheim','Holstein Kiel','St Pauli'] },
  ];

  useEffect(() => {
    const fetchRankings = async () => {
      try {
        const response = await api.get('/rankings');
        setGlobalRankings(response.data.rankings || {});
      } catch (err) {
        console.error("Failed to fetch rankings", err);
      } finally {
        setLoading(false);
      }
    };
    fetchRankings();
  }, []);

  const getLeagueRankings = () => {
    const activeLeague = LEAGUES.find(l => l.id === league);
    const teams = activeLeague ? activeLeague.teams : [];
    const rankings = teams.map(team => {
      const data = globalRankings[team] || { attack: 0, defense: 0, power: 0 };
      
      // Enforce precision rounding so Power = Att - Def exactly matches on screen
      const attack = Number((data.attack || 0).toFixed(3));
      const defense = Number((data.defense || 0).toFixed(3));
      const power = attack - defense;

      return { team, attack, defense, power };
    });
    return rankings.sort((a, b) => b.power - a.power);
  };

  const formatStat = (val) => {
    if (val === 0) return '0.000';
    return (val > 0 ? '+' : '') + val.toFixed(3);
  };

  const currentRankings = getLeagueRankings();

  const maxAttack = Math.max(...currentRankings.map(r => Math.abs(r.attack)), 0.1);
  const maxDefense = Math.max(...currentRankings.map(r => Math.abs(r.defense)), 0.1);
  const maxPowerAbs = Math.max(...currentRankings.map(r => Math.abs(r.power)), 0.1);

  const minPowerRaw = Math.min(...currentRankings.map(r => r.power));
  const maxPowerRaw = Math.max(...currentRankings.map(r => r.power));

  const getBarWidth = (val, max) => {
    return Math.min((Math.abs(val) / max) * 100, 100) + '%';
  };

  return (
    <div className="rankings-container">
      <div className="rankings-header">
        <h1>🏆 Power Rankings</h1>
        <p>Mathematically extracted from the Dixon-Coles Goal Optimizer.</p>
      </div>

      <div className="rankings-controls">
        <select 
          className="league-selector"
          value={league} 
          onChange={(e) => setLeague(e.target.value)}
        >
          {LEAGUES.map(l => (
            <option key={l.id} value={l.id}>{l.name}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="loading" style={{textAlign: 'center', marginTop: 50}}>Loading High-Performance Models...</div>
      ) : (
        <div className="rankings-glass-card">
          <table className="rankings-table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Team</th>
                <th>Attack Param</th>
                <th>Defence Param</th>
                <th>Overall Edge</th>
                <th>0-100 Score</th>
              </tr>
            </thead>
            <tbody>
              {currentRankings.map((r, idx) => {
                const score = maxPowerRaw === minPowerRaw ? 50 : ((r.power - minPowerRaw) / (maxPowerRaw - minPowerRaw)) * 100;
                return (
                <tr key={r.team}>
                  <td>
                    <span className="rank-badge">{idx + 1}</span>
                  </td>
                  <td>
                    <div className="team-name-cell">{r.team}</div>
                  </td>
                  <td>
                    <div className="stat-wrapper">
                      <span className={`stat-value ${r.attack > 0 ? 'stat-positive' : 'stat-neutral'}`}>
                        {formatStat(r.attack)}
                      </span>
                      <div className="stat-bar-bg">
                        <div 
                          className="stat-bar-fill bg-teal" 
                          style={{ width: getBarWidth(r.attack, maxAttack) }}
                        />
                      </div>
                    </div>
                  </td>
                  <td>
                    <div className="stat-wrapper">
                      <span className={`stat-value ${r.defense < 0 ? 'stat-positive' : (r.defense > 0 ? 'stat-negative' : 'stat-neutral')}`}>
                        {formatStat(r.defense)}
                      </span>
                      <div className="stat-bar-bg">
                        <div 
                          className={`stat-bar-fill ${r.defense > 0 ? 'bg-red' : 'bg-teal'}`} 
                          style={{ width: getBarWidth(r.defense, maxDefense) }}
                        />
                      </div>
                    </div>
                  </td>
                  <td>
                    <div className="stat-wrapper">
                      <span className={`stat-value ${r.power > 0 ? 'stat-positive' : 'stat-neutral'}`}>
                        {formatStat(r.power)}
                      </span>
                      <div className="stat-bar-bg">
                        <div 
                          className="stat-bar-fill bg-gradient" 
                          style={{ width: getBarWidth(r.power, maxPowerAbs) }}
                        />
                      </div>
                    </div>
                  </td>
                  <td>
                    <div className="stat-wrapper">
                      <span className="stat-value" style={{ fontWeight: 'bold', color: '#fff' }}>
                        {score.toFixed(1)}
                      </span>
                      <div className="stat-bar-bg">
                        <div 
                          className="stat-bar-fill" 
                          style={{ width: `${score}%`, backgroundColor: `hsl(${score * 1.2}, 80%, 50%)` }}
                        />
                      </div>
                    </div>
                  </td>
                </tr>
              );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default PowerRankings;

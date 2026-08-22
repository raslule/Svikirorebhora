import { useState, useEffect } from 'react';
import { getTeamsByLeague, getTeamAnalytics } from '../api';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer,
  BarChart, Bar, Cell
} from 'recharts';

export default function TeamAnalytics() {
  const [league, setLeague] = useState('premier-league');
  const [teams, setTeams] = useState([]);
  const [selectedTeam, setSelectedTeam] = useState('');
  
  const [loadingTeams, setLoadingTeams] = useState(false);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);
  const [analytics, setAnalytics] = useState(null);

  useEffect(() => {
    async function fetchTeams() {
      setLoadingTeams(true);
      try {
        const data = await getTeamsByLeague(league);
        setTeams(data);
        if (data.length > 0) {
          setSelectedTeam(data[0]);
        }
      } catch (err) {
        console.error("Failed to load teams", err);
      } finally {
        setLoadingTeams(false);
      }
    }
    fetchTeams();
  }, [league]);

  useEffect(() => {
    async function fetchAnalytics() {
      if (!selectedTeam) return;
      setLoadingAnalytics(true);
      try {
        const data = await getTeamAnalytics(selectedTeam);
        setAnalytics(data);
      } catch (err) {
        console.error("Failed to load analytics", err);
      } finally {
        setLoadingAnalytics(false);
      }
    }
    fetchAnalytics();
  }, [selectedTeam]);

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Team Analytics</h1>
        <p className="page-subtitle">Deep-dive team statistics &mdash; ELO trend, rolling form, attack/defense profile</p>
      </div>
      
      <div className="page-body">
        <div style={{ display: 'flex', gap: 16, marginBottom: 24, alignItems: 'center' }}>
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 14, color: 'var(--text-secondary)' }}>League</label>
            <select 
              value={league} 
              onChange={(e) => setLeague(e.target.value)}
              style={{ padding: '8px 12px', borderRadius: '4px', border: '1px solid var(--border)', background: 'var(--bg-elevated)', color: 'var(--text-primary)' }}
            >
              <option value="premier-league">Premier League</option>
              <option value="la-liga">La Liga</option>
              <option value="serie-a">Serie A</option>
              <option value="ligue-1">Ligue 1</option>
              <option value="bundesliga">Bundesliga</option>
            </select>
          </div>
          
          <div>
            <label style={{ display: 'block', marginBottom: 4, fontSize: 14, color: 'var(--text-secondary)' }}>Team</label>
            <select 
              value={selectedTeam} 
              onChange={(e) => setSelectedTeam(e.target.value)}
              disabled={loadingTeams}
              style={{ padding: '8px 12px', borderRadius: '4px', border: '1px solid var(--border)', background: 'var(--bg-elevated)', color: 'var(--text-primary)', minWidth: 200 }}
            >
              {teams.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>

        {loadingAnalytics && <div style={{ padding: 40, textAlign: 'center' }}>Loading analytics...</div>}
        
        {!loadingAnalytics && analytics && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            
            {/* Top row: Form & Profile */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
              <div className="card">
                <div className="card-header">5-Match Rolling Form</div>
                <div className="card-body" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: 150 }}>
                  <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
                    {analytics.form.results.map((r, i) => (
                      <div key={i} style={{
                        width: 32, height: 32, borderRadius: '4px', 
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontWeight: 800, fontSize: 14,
                        background: r === 'W' ? '#10b981' : r === 'L' ? '#ef4444' : '#f59e0b',
                        color: '#000'
                      }}>
                        {r}
                      </div>
                    ))}
                  </div>
                  <div style={{ display: 'flex', gap: 24 }}>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 24, fontWeight: 800 }}>{analytics.form.gf}</div>
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Goals For</div>
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ fontSize: 24, fontWeight: 800 }}>{analytics.form.ga}</div>
                      <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Goals Against</div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="card">
                <div className="card-header">Attack / Defense Profile (Dixon-Coles)</div>
                <div className="card-body">
                  <div style={{ marginBottom: 16 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 14 }}>
                      <span>Attacking Strength</span>
                      <span style={{ fontWeight: 800 }}>{analytics.profile.attack_raw}</span>
                    </div>
                    <div style={{ height: 8, background: 'var(--bg-active)', borderRadius: 4, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${analytics.profile.attack_score}%`, background: 'var(--chart-blue)' }}></div>
                    </div>
                  </div>
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 14 }}>
                      <span>Defensive Solidity</span>
                      <span style={{ fontWeight: 800 }}>{analytics.profile.defense_raw}</span>
                    </div>
                    <div style={{ height: 8, background: 'var(--bg-active)', borderRadius: 4, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${analytics.profile.defense_score}%`, background: 'var(--chart-teal)' }}></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Middle row: ELO Trend */}
            <div className="card">
              <div className="card-header">15-Match ELO Trend</div>
              <div className="card-body" style={{ height: 300 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={analytics.elo_trend} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                    <XAxis 
                      dataKey="date" 
                      stroke="#94a3b8" 
                      tick={{ fill: '#94a3b8', fontSize: 11 }}
                      tickFormatter={(val) => val ? val.slice(5) : ''}
                      angle={-35}
                      textAnchor="end"
                      height={50}
                    />
                    <YAxis domain={['auto', 'auto']} stroke="var(--text-secondary)" tick={{fill: 'var(--text-secondary)'}} />
                    <RechartsTooltip 
                      contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}
                      labelStyle={{ color: 'var(--text-secondary)', marginBottom: 8 }}
                    />
                    <Line 
                      type="monotone" 
                      dataKey="elo" 
                      stroke="#60a5fa" 
                      strokeWidth={2.5} 
                      dot={{ r: 4, fill: '#1e293b', stroke: '#60a5fa', strokeWidth: 2 }} 
                      activeDot={{ r: 6, fill: '#60a5fa' }} 
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            
            {/* Bottom row: Referee Regime */}
            <div className="card">
              <div className="card-header">Points Per Game by Referee Strictness</div>
              <div className="card-body" style={{ height: 250 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={analytics.referee_impact} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
                    <XAxis dataKey="regime" stroke="var(--text-secondary)" tick={{fill: 'var(--text-secondary)'}} />
                    <YAxis domain={[0, 3]} stroke="var(--text-secondary)" tick={{fill: 'var(--text-secondary)'}} />
                    <RechartsTooltip 
                      contentStyle={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)' }}
                      cursor={{ fill: 'var(--bg-active)' }}
                    />
                    <Bar dataKey="ppg" radius={[4, 4, 0, 0]}>
                      {analytics.referee_impact.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={
                          entry.regime === 'STRICT' ? '#ef4444' : 
                          entry.regime === 'LENIENT' ? '#10b981' : 
                          '#3b82f6'
                        } />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

          </div>
        )}
      </div>
    </div>
  );
}

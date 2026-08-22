import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// Attach JWT token to every request
api.interceptors.request.use(cfg => {
  const token = localStorage.getItem('so_token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

// Auto-logout on 401
api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      localStorage.removeItem('so_token')
      localStorage.removeItem('so_user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export const auth = {
  login:    (u, p)   => api.post('/auth/token', new URLSearchParams({ username: u, password: p }), { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }),
  register: (u, p)   => api.post('/auth/register', { username: u, password: p }),
  me:       ()       => api.get('/auth/me'),
}

export const predictions = {
  predict: (body)    => api.post('/predict', body),
}

export const matches = {
  results:   (p)     => api.get('/matches/results', { params: p }),
  upcoming:  (p)     => api.get('/matches/upcoming', { params: p }),
  standings: (league, season = 'current') => api.get('/matches/standings', { params: { league, season } }),
  seasons:   (league) => api.get('/matches/seasons', { params: { league } }),
}

export const bets = {
  list:     (p)      => api.get('/bets', { params: p }),
  create:   (body)   => api.post('/bets', body),
  update:   (id, b)  => api.put(`/bets/${id}`, b),
  remove:   (id)     => api.delete(`/bets/${id}`),
  analytics:()       => api.get('/bets/analytics/summary'),
}

export const admin = {
  retrain:    ()     => api.post('/admin/retrain'),
  updateData: ()     => api.post('/admin/update-data'),
  modelsInfo: ()     => api.get('/models/info'),
}

export const getTeamsByLeague = async (league) => {
    try {
        const response = await api.get(`/teams/${league}`);
        return response.data;
    } catch (error) {
        console.error("Error fetching teams by league", error);
        throw error;
    }
};

export const getTeamAnalytics = async (teamName) => {
    try {
        const response = await api.get(`/teams/${teamName}/analytics`);
        return response.data;
    } catch (error) {
        console.error("Error fetching team analytics", error);
        throw error;
    }
};

export default api

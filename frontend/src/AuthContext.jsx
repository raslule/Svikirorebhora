import { createContext, useContext, useState, useEffect } from 'react'
import { auth as authApi } from './api'

const AuthCtx = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('so_user')) } catch { return null }
  })
  const [loading, setLoading] = useState(false)

  const login = async (username, password) => {
    setLoading(true)
    try {
      const { data } = await authApi.login(username, password)
      localStorage.setItem('so_token', data.access_token)
      localStorage.setItem('so_user', JSON.stringify({ username: data.username }))
      setUser({ username: data.username })
      return { ok: true }
    } catch (e) {
      return { ok: false, error: e.response?.data?.detail || 'Login failed' }
    } finally {
      setLoading(false)
    }
  }

  const register = async (username, password) => {
    setLoading(true)
    try {
      const { data } = await authApi.register(username, password)
      localStorage.setItem('so_token', data.access_token)
      localStorage.setItem('so_user', JSON.stringify({ username: data.username }))
      setUser({ username: data.username })
      return { ok: true }
    } catch (e) {
      return { ok: false, error: e.response?.data?.detail || 'Registration failed' }
    } finally {
      setLoading(false)
    }
  }

  const logout = () => {
    localStorage.removeItem('so_token')
    localStorage.removeItem('so_user')
    setUser(null)
  }

  return (
    <AuthCtx.Provider value={{ user, login, register, logout, loading }}>
      {children}
    </AuthCtx.Provider>
  )
}

export const useAuth = () => useContext(AuthCtx)

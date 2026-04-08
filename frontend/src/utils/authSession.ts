export interface AuthSessionSnapshot {
  token: string
  username: string
  role: string
  isAdmin: boolean
  loginTime: string
}

export interface AuthSessionPayload {
  token: string
  username: string
  role?: string
  isAdmin?: boolean
  loginTime?: string
}

const STORAGE_KEYS = {
  token: 'token',
  username: 'username',
  role: 'role',
  loginTime: 'loginTime'
} as const

const canUseStorage = () => typeof window !== 'undefined' && typeof window.sessionStorage !== 'undefined'

const emitSessionChange = () => {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event('auth-session-changed'))
  }
}

const normalizeRole = (role?: string, isAdmin?: boolean) => {
  const normalized = String(role || '').trim().toUpperCase()
  if (normalized) return normalized
  return isAdmin ? 'ADMIN' : 'USER'
}

export const readAuthSession = (): AuthSessionSnapshot => {
  if (!canUseStorage()) {
    return {
      token: '',
      username: '',
      role: '',
      isAdmin: false,
      loginTime: ''
    }
  }

  const role = sessionStorage.getItem(STORAGE_KEYS.role) || ''
  return {
    token: sessionStorage.getItem(STORAGE_KEYS.token) || '',
    username: sessionStorage.getItem(STORAGE_KEYS.username) || '',
    role,
    isAdmin: role === 'ADMIN',
    loginTime: sessionStorage.getItem(STORAGE_KEYS.loginTime) || ''
  }
}

export const getAuthToken = () => readAuthSession().token

export const saveAuthSession = (payload: AuthSessionPayload) => {
  const role = normalizeRole(payload.role, payload.isAdmin)
  const snapshot: AuthSessionSnapshot = {
    token: payload.token,
    username: payload.username,
    role,
    isAdmin: role === 'ADMIN',
    loginTime: payload.loginTime || new Date().toLocaleString('zh-CN')
  }

  if (canUseStorage()) {
    sessionStorage.setItem(STORAGE_KEYS.token, snapshot.token)
    sessionStorage.setItem(STORAGE_KEYS.username, snapshot.username)
    sessionStorage.setItem(STORAGE_KEYS.role, snapshot.role)
    sessionStorage.setItem(STORAGE_KEYS.loginTime, snapshot.loginTime)
    emitSessionChange()
  }

  return snapshot
}

export const clearAuthSession = () => {
  if (canUseStorage()) {
    Object.values(STORAGE_KEYS).forEach((key) => sessionStorage.removeItem(key))
    emitSessionChange()
  }
}

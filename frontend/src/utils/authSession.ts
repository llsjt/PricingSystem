export interface AuthSessionSnapshot {
  token: string
  username: string
  isAdmin: boolean
  loginTime: string
}

export interface AuthSessionPayload {
  token: string
  username: string
  isAdmin: boolean
  loginTime?: string
}

const STORAGE_KEYS = {
  token: 'token',
  username: 'username',
  isAdmin: 'isAdmin',
  loginTime: 'loginTime'
} as const

const canUseStorage = () => typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'

const emitSessionChange = () => {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event('auth-session-changed'))
  }
}

export const readAuthSession = (): AuthSessionSnapshot => {
  if (!canUseStorage()) {
    return {
      token: '',
      username: '',
      isAdmin: false,
      loginTime: ''
    }
  }

  return {
    token: localStorage.getItem(STORAGE_KEYS.token) || '',
    username: localStorage.getItem(STORAGE_KEYS.username) || '',
    isAdmin: localStorage.getItem(STORAGE_KEYS.isAdmin) === 'true',
    loginTime: localStorage.getItem(STORAGE_KEYS.loginTime) || ''
  }
}

export const getAuthToken = () => readAuthSession().token

export const saveAuthSession = (payload: AuthSessionPayload) => {
  if (!canUseStorage()) {
    return {
      ...payload,
      loginTime: payload.loginTime || ''
    }
  }

  const snapshot: AuthSessionSnapshot = {
    token: payload.token,
    username: payload.username,
    isAdmin: Boolean(payload.isAdmin),
    loginTime: payload.loginTime || new Date().toLocaleString('zh-CN')
  }

  localStorage.setItem(STORAGE_KEYS.token, snapshot.token)
  localStorage.setItem(STORAGE_KEYS.username, snapshot.username)
  localStorage.setItem(STORAGE_KEYS.isAdmin, String(snapshot.isAdmin))
  localStorage.setItem(STORAGE_KEYS.loginTime, snapshot.loginTime)
  emitSessionChange()
  return snapshot
}

export const clearAuthSession = () => {
  if (canUseStorage()) {
    Object.values(STORAGE_KEYS).forEach((key) => localStorage.removeItem(key))
    emitSessionChange()
  }
}

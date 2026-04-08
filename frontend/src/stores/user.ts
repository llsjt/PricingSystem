import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { clearAuthSession, readAuthSession, saveAuthSession, type AuthSessionPayload } from '../utils/authSession'

export const useUserStore = defineStore('user', () => {
  const token = ref('')
  const username = ref('Guest')
  const role = ref('USER')
  const loginTime = ref('')

  const isAdmin = computed(() => role.value === 'ADMIN')
  const isAuthenticated = computed(() => Boolean(token.value))

  const syncFromSession = () => {
    const snapshot = readAuthSession()
    token.value = snapshot.token
    username.value = snapshot.username || 'Guest'
    role.value = snapshot.role || 'USER'
    loginTime.value = snapshot.loginTime
    return snapshot
  }

  const applySession = (payload: AuthSessionPayload) => {
    const snapshot = saveAuthSession(payload)
    syncFromSession()
    return snapshot
  }

  const clearSession = () => {
    clearAuthSession()
    token.value = ''
    username.value = 'Guest'
    role.value = 'USER'
    loginTime.value = ''
  }

  syncFromSession()

  return {
    token,
    username,
    role,
    isAdmin,
    loginTime,
    isAuthenticated,
    syncFromSession,
    applySession,
    clearSession
  }
})

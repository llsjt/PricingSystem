import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { clearAuthSession, readAuthSession, saveAuthSession, type AuthSessionPayload } from '../utils/authSession'

export const useUserStore = defineStore('user', () => {
  const token = ref('')
  const username = ref('Guest')
  const isAdmin = ref(false)
  const loginTime = ref('')

  const isAuthenticated = computed(() => Boolean(token.value))

  const syncFromSession = () => {
    const snapshot = readAuthSession()
    token.value = snapshot.token
    username.value = snapshot.username || 'Guest'
    isAdmin.value = snapshot.isAdmin
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
    isAdmin.value = false
    loginTime.value = ''
  }

  syncFromSession()

  return {
    token,
    username,
    isAdmin,
    loginTime,
    isAuthenticated,
    syncFromSession,
    applySession,
    clearSession
  }
})

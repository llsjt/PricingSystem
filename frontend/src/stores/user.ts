import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUserStore = defineStore('user', () => {
  const username = ref('Guest')
  const token = ref('')

  function setToken(newToken: string) {
    token.value = newToken
  }

  return { username, token, setToken }
})

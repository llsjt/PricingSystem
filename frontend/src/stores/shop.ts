/**
 * 店铺状态仓库，统一缓存当前用户可见的店铺列表。
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getShopList, type Shop } from '../api/shop'
import { resolveRequestErrorMessage } from '../utils/error'

export const useShopStore = defineStore('shop', () => {
  const shops = ref<Shop[]>([])
  const loaded = ref(false)
  const loading = ref(false)
  const loadSucceeded = ref(false)
  const loadError = ref('')
  let fetchPromise: Promise<boolean> | null = null

  const resetState = () => {
    shops.value = []
    loaded.value = false
    loading.value = false
    loadSucceeded.value = false
    loadError.value = ''
    fetchPromise = null
  }

  async function fetchShops(force = false) {
    if (loading.value && fetchPromise) {
      return fetchPromise
    }
    if (!force && loadSucceeded.value) {
      return true
    }

    fetchPromise = (async () => {
      loading.value = true
      loadError.value = ''

      try {
        const res: any = await getShopList()
        if (res.code === 200) {
          shops.value = res.data || []
          loadSucceeded.value = true
          return true
        }

        shops.value = []
        loadSucceeded.value = false
        loadError.value = res.message || '\u5e97\u94fa\u5217\u8868\u52a0\u8f7d\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5'
        return false
      } catch (error) {
        shops.value = []
        loadSucceeded.value = false
        loadError.value = await resolveRequestErrorMessage(error, '\u5e97\u94fa\u5217\u8868\u52a0\u8f7d\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5')
        return false
      } finally {
        loaded.value = true
        loading.value = false
        fetchPromise = null
      }
    })()

    return fetchPromise
  }

  return { shops, loaded, loading, loadSucceeded, loadError, resetState, fetchShops }
})

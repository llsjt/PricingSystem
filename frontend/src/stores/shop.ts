import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getShopList, type Shop } from '../api/shop'

export const useShopStore = defineStore('shop', () => {
  const shops = ref<Shop[]>([])
  const loaded = ref(false)

  async function fetchShops() {
    try {
      const res: any = await getShopList()
      if (res.code === 200) {
        shops.value = res.data || []
      }
    } catch {
      shops.value = []
    }
    loaded.value = true
  }

  return { shops, loaded, fetchShops }
})

import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import {
  getProductDailyMetrics,
  getProductSkus,
  getTrafficPromoDaily,
  type ProductDailyMetricPageVO,
  type ProductDailyMetricVO,
  type ProductListVO,
  type ProductSkuVO,
  type TrafficPromoDailyVO
} from '../../api/product'
import { resolveRequestErrorMessage } from '../../utils/error'

const average = (sum: number, count: number) => (count > 0 ? sum / count : 0)

export const calcGrossProfit = (salePrice?: number | null, costPrice?: number | null) =>
  Number(salePrice || 0) - Number(costPrice || 0)

export function useProductDetailDrawer() {
  const detailVisible = ref(false)
  const detailLoading = ref(false)
  const detailTab = ref('base')
  const currentProduct = ref<ProductListVO | null>(null)
  const dailyMetrics = ref<ProductDailyMetricVO[]>([])
  const dailyMetricSummary = ref<ProductDailyMetricPageVO['summary']>({
    days: 0,
    totalVisitors: 0,
    totalTurnover: 0,
    avgConversionRate: 0
  })
  const skus = ref<ProductSkuVO[]>([])
  const trafficPromos = ref<TrafficPromoDailyVO[]>([])

  const dailyMetricPagination = reactive({
    page: 1,
    size: 10,
    total: 0
  })

  const dailySummary = computed(() => dailyMetricSummary.value)

  const skuSummary = computed(() => {
    const rows = skus.value
    const totalStock = rows.reduce((sum, row) => sum + Number(row.stock || 0), 0)
    const avgStock = Math.round(average(totalStock, rows.length))
    const avgSalePrice = average(
      rows.reduce((sum, row) => sum + Number(row.salePrice || 0), 0),
      rows.length
    )
    return {
      count: rows.length,
      totalStock,
      avgStock,
      avgSalePrice
    }
  })

  const trafficSummary = computed(() => {
    const rows = trafficPromos.value
    const sourceCount = new Set(rows.map((row) => row.trafficSource).filter(Boolean)).size
    const totalCost = rows.reduce((sum, row) => sum + Number(row.costAmount || 0), 0)
    const totalPay = rows.reduce((sum, row) => sum + Number(row.payAmount || 0), 0)
    const avgRoi = average(
      rows.reduce((sum, row) => sum + Number(row.roi || 0), 0),
      rows.length
    )
    return {
      sourceCount,
      totalCost,
      totalPay,
      avgRoi
    }
  })

  const resetDailyMetricState = () => {
    dailyMetrics.value = []
    dailyMetricPagination.page = 1
    dailyMetricPagination.size = 10
    dailyMetricPagination.total = 0
    dailyMetricSummary.value = {
      days: 0,
      totalVisitors: 0,
      totalTurnover: 0,
      avgConversionRate: 0
    }
  }

  const loadDailyMetricsPage = async (productId: number) => {
    const dailyRes: any = await getProductDailyMetrics(productId, {
      page: dailyMetricPagination.page,
      size: dailyMetricPagination.size
    })

    if (dailyRes?.code !== 200) {
      throw new Error(dailyRes?.message || '加载商品日指标失败')
    }

    const pageData = dailyRes.data || {}
    dailyMetrics.value = pageData.records || []
    dailyMetricPagination.page = Number(pageData.page || dailyMetricPagination.page)
    dailyMetricPagination.size = Number(pageData.size || dailyMetricPagination.size)
    dailyMetricPagination.total = Number(pageData.total || 0)
    dailyMetricSummary.value = pageData.summary || {
      days: 0,
      totalVisitors: 0,
      totalTurnover: 0,
      avgConversionRate: 0
    }
  }

  const loadDetailData = async (productId: number) => {
    detailLoading.value = true
    try {
      const [, skuRes, trafficRes] = await Promise.all([
        loadDailyMetricsPage(productId),
        getProductSkus(productId),
        getTrafficPromoDaily(productId, { limit: 90 })
      ])

      skus.value = skuRes?.code === 200 ? skuRes.data || [] : []
      trafficPromos.value = trafficRes?.code === 200 ? trafficRes.data || [] : []
    } catch (error) {
      ElMessage.error(await resolveRequestErrorMessage(error, '加载商品明细数据失败'))
      resetDailyMetricState()
      skus.value = []
      trafficPromos.value = []
    } finally {
      detailLoading.value = false
    }
  }

  const handleDailyMetricPageChange = async (page: number) => {
    if (!currentProduct.value) return
    dailyMetricPagination.page = page
    try {
      detailLoading.value = true
      await loadDailyMetricsPage(currentProduct.value.id)
    } catch (error) {
      ElMessage.error(await resolveRequestErrorMessage(error, '加载商品日指标失败'))
    } finally {
      detailLoading.value = false
    }
  }

  const handleDailyMetricSizeChange = async (size: number) => {
    dailyMetricPagination.page = 1
    dailyMetricPagination.size = size
    await handleDailyMetricPageChange(1)
  }

  const openDetailDrawer = async (row: ProductListVO) => {
    currentProduct.value = row
    detailTab.value = 'base'
    detailVisible.value = true
    resetDailyMetricState()
    await loadDetailData(row.id)
  }

  return {
    currentProduct,
    dailyMetricPagination,
    dailyMetrics,
    dailySummary,
    detailLoading,
    detailTab,
    detailVisible,
    handleDailyMetricPageChange,
    handleDailyMetricSizeChange,
    openDetailDrawer,
    skuSummary,
    skus,
    trafficPromos,
    trafficSummary
  }
}

import axios from 'axios'
import request from './request'
import { getAuthToken } from '../utils/authSession'

export type ImportDataType = 'AUTO' | 'PRODUCT_BASE' | 'PRODUCT_SKU' | 'PRODUCT_DAILY_METRIC' | 'TRAFFIC_PROMO_DAILY'

export interface ProductListVO {
  id: number
  platform?: string
  externalProductId: string
  productName: string
  categoryName?: string
  costPrice: number | null
  salePrice: number | null
  stock?: number
  status: string
  monthlySales?: number
  conversionRate?: number
  updatedAt: string
}

export interface ProductDailyMetricVO {
  id: number
  statDate: string
  visitorCount?: number
  addCartCount?: number
  payBuyerCount?: number
  salesCount?: number
  turnover?: number
  refundAmount?: number
  conversionRate?: number
  createdAt?: string
}

export interface ProductDailyMetricSummaryVO {
  days: number
  totalVisitors: number
  totalTurnover: number
  avgConversionRate: number
}

export interface ProductDailyMetricPageVO {
  page: number
  size: number
  total: number
  records: ProductDailyMetricVO[]
  summary: ProductDailyMetricSummaryVO
}

export interface ProductSkuVO {
  id: number
  externalSkuId?: string
  skuName?: string
  skuAttr?: string
  salePrice?: number
  costPrice?: number
  stock?: number
  updatedAt?: string
}

export interface TrafficPromoDailyVO {
  id: number
  statDate: string
  trafficSource?: string
  impressionCount?: number
  clickCount?: number
  visitorCount?: number
  costAmount?: number
  payAmount?: number
  roi?: number
  createdAt?: string
}

export interface ProductManualDTO {
  externalProductId?: string
  productName: string
  categoryName?: string
  costPrice: number
  salePrice: number
  stock?: number
  monthlySales?: number
  conversionRate?: number
  status?: string
}

export interface ImportResultVO {
  dataType: string
  dataTypeLabel: string
  targetTable: string
  fileName: string
  rowCount: number
  successCount: number
  failCount: number
  uploadStatus: string
  startDate?: string
  endDate?: string
  autoDetected?: boolean
  summary: string
  errors?: string[]
}

export interface MockExcelExportDTO {
  productCount: number
  dailyCount: number
  skuCount: number
  trafficCount: number
  startProductId?: number
  startDate?: string
  seed?: number
}

export const getProductList = (params: { page: number; size: number; keyword?: string; platform?: string; status?: string; shopId?: number }) => {
  return request.get('/products/list', { params })
}

export const getProductDailyMetrics = (id: number, params?: { page?: number; size?: number }) => {
  return request.get(`/products/${id}/daily-metrics`, { params })
}

export const getProductSkus = (id: number) => {
  return request.get(`/products/${id}/skus`)
}

export const getTrafficPromoDaily = (id: number, params?: { limit?: number }) => {
  return request.get(`/products/${id}/traffic-promo`, { params })
}

export const addProductManual = (data: ProductManualDTO) => {
  return request.post('/products/add', data)
}

export const batchDeleteProducts = (ids: number[]) => {
  return request.delete('/products/batch-delete', { params: { ids: ids.join(',') } })
}

export const downloadTemplate = (dataType: Exclude<ImportDataType, 'AUTO'>) => {
  return request.get('/products/template', {
    params: { dataType },
    responseType: 'blob'
  })
}

export const downloadMockExcelBundle = (data: MockExcelExportDTO) => {
  const token = getAuthToken()
  return axios.post('/api/products/mock-export', data, {
    responseType: 'blob',
    timeout: 60000,
    headers: token
      ? {
          Authorization: `Bearer ${token}`
        }
      : undefined
  })
}

export const importDataUrl = '/products/import' // For el-upload action

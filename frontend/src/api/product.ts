import request from './request'

export type ImportDataType = 'AUTO' | 'PRODUCT_BASE' | 'PRODUCT_DAILY_METRIC' | 'TRAFFIC_PROMO_DAILY'

export interface ProductListVO {
  id: number
  itemId: number
  title: string
  category?: string
  costPrice: number
  currentPrice: number
  stock?: number
  status: string
  monthlySales?: number
  conversionRate?: number
  updatedAt: string
}

export interface ProductManualDTO {
  itemId?: number
  title: string
  category?: string
  costPrice: number
  currentPrice: number
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

export const getProductList = (params: { page: number; size: number; keyword?: string }) => {
  return request.get('/products/list', { params })
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

export const importDataUrl = '/products/import' // For el-upload action

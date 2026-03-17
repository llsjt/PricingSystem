import request from './request'

export interface ProductListVO {
  id: number
  title: string
  category?: string
  costPrice: number
  marketPrice?: number
  currentPrice: number
  stock?: number
  source: string
  monthlySales?: number
  clickRate?: number
  conversionRate?: number
  updatedAt: string
}

export interface ProductManualDTO {
  title: string
  category?: string
  costPrice: number
  marketPrice?: number
  currentPrice: number
  stock?: number
  monthlySales?: number
  clickRate?: number
  conversionRate?: number
  source: string
}

export const getProductList = (params: { page: number; size: number; keyword?: string; dataSource?: string }) => {
  return request.get('/products/list', { params })
}

export const addProductManual = (data: ProductManualDTO) => {
  return request.post('/products/add', data)
}

export const batchDeleteProducts = (ids: number[]) => {
  return request.delete('/products/batch-delete', { params: { ids: ids.join(',') } })
}

export const downloadTemplate = () => {
  return request.get('/products/template', { responseType: 'blob' })
}

export const importDataUrl = '/products/import' // For el-upload action

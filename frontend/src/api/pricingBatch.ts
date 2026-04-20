import request from './request'

export interface PricingBatchCreateRequest {
  productIds: number[]
  strategyGoal: string
  constraints: string
}

export interface PricingBatchCreateResponse {
  batchId: number
  batchCode: string
  totalCount: number
  linkedTaskIds: number[]
  createFailedCount: number
}

export interface PricingBatchDetail {
  batchId: number
  batchCode: string
  batchStatus: string
  strategyGoal: string
  constraintText?: string
  totalCount: number
  runningCount: number
  completedCount: number
  manualReviewCount: number
  failedCount: number
  cancelledCount: number
  finalizedAt?: string | null
  createdAt: string
  updatedAt: string
}

export interface PricingBatchItem {
  id: number
  batchId: number
  itemOrder: number
  productId: number
  taskId?: number | null
  resultId?: number | null
  productTitle: string
  currentPrice?: number | null
  finalPrice?: number | null
  expectedSales?: number | null
  expectedProfit?: number | null
  profitGrowth?: number | null
  creationStatus: string
  taskStatus?: string | null
  displayStatus: string
  executeStrategy?: string | null
  reviewRequired?: boolean
  appliedStatus?: string | null
  errorMessage?: string | null
  createdAt: string
  batchItemUpdatedAt?: string | null
  taskUpdatedAt?: string | null
  updatedAt: string
}

export interface PricingBatchItemsPage {
  records: PricingBatchItem[]
  total: number
  current: number
  size: number
}

export interface PricingBatchListPage {
  records: PricingBatchDetail[]
  total: number
  current: number
  size: number
}

export interface PricingBatchCancelResponse {
  cancelledCount: number
  skippedCount: number
}

export const createPricingBatch = (data: PricingBatchCreateRequest) => {
  return request.post('/pricing/batches', data)
}

export const getRecentPricingBatches = (params: { page?: number; size?: number; status?: string } = {}) => {
  return request.get('/pricing/batches', { params })
}

export const getPricingBatchDetail = (batchId: number) => {
  return request.get(`/pricing/batches/${batchId}`)
}

export const getPricingBatchItems = (batchId: number, params: { page?: number; size?: number; status?: string }) => {
  return request.get(`/pricing/batches/${batchId}/items`, { params })
}

export const cancelPricingBatch = (batchId: number) => {
  return request.post(`/pricing/batches/${batchId}/cancel`)
}

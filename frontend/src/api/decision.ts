import request from './request'

export interface DecisionTaskRequest {
  productIds: number[]
  strategyGoal: string
  constraints: string
}

export interface DecisionTaskQuery {
  page?: number
  size?: number
  status?: string
  startTime?: string
  endTime?: string
  sortOrder?: 'asc' | 'desc'
}

export interface DecisionTaskStats {
  total: number
  completed: number
  running: number
  failed: number
}

export interface DecisionComparisonItem {
  resultId: number
  productId: number
  productTitle: string
  originalPrice: number
  suggestedPrice: number
  profitChange: number
  expectedSales: number
  expectedProfit: number
  passStatus: string
  executeStrategy: string
  resultSummary: string
  appliedStatus: string
}

export interface DecisionTaskItem {
  id: number
  taskCode: string
  productId: number
  productTitle: string
  currentPrice: number
  suggestedMinPrice?: number
  suggestedMaxPrice?: number
  finalPrice?: number
  taskStatus: string
  executeStrategy?: string
  createdAt: string
}

export interface DecisionLogItem {
  id: number
  agentCode: string
  agentName: string
  runOrder: number
  runStatus: string
  outputSummary: string
  suggestedPrice?: number
  predictedProfit?: number
  confidenceScore?: number
  riskLevel?: string
  needManualReview?: boolean
  createdAt: string
}

export const startDecisionTask = (data: DecisionTaskRequest) => {
  return request.post('/decision/start', data)
}

export const getTaskResult = (taskId: number) => {
  return request.get(`/decision/result/${taskId}`)
}

export const getTaskComparison = (taskId: number) => {
  return request.get(`/decision/comparison/${taskId}`)
}

export const getTaskLogs = (taskId: number) => {
  return request.get(`/decision/logs/${taskId}`)
}

export const getTaskList = (params: DecisionTaskQuery) => {
  return request.get('/decision/tasks', { params })
}

export const getTaskStats = (params?: Pick<DecisionTaskQuery, 'startTime' | 'endTime'>) => {
  return request.get('/decision/tasks/stats', { params })
}

export const applyDecision = (resultId: number) => {
  return request.post(`/decision/apply/${resultId}`)
}

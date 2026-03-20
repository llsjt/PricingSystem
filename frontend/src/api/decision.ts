import request from './request'

export interface DecisionTaskRequest {
  productIds: number[]
  strategyGoal: string
  constraints: string
}

export interface DecResult {
  id: number
  taskId: number
  productId: number
  suggestedPrice: number
  profitChange: number
  isAccepted: boolean
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

export const applyDecision = (resultId: number) => {
  return request.post(`/decision/apply/${resultId}`)
}

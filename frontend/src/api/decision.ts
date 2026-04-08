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
  roleName?: string
  speakOrder?: number
  thoughtContent?: string
  agentCode?: string
  agentName?: string
  runOrder?: number
  displayOrder?: number
  stage?: string
  runStatus?: string
  outputSummary?: string
  suggestedPrice?: number
  predictedProfit?: number
  confidenceScore?: number
  riskLevel?: string
  needManualReview?: boolean
  thinking?: string
  evidence?: Array<Record<string, unknown>>
  suggestion?: Record<string, unknown>
  reasonWhy?: string
  createdAt: string
}

export type PricingTaskStatus =
  | 'IDLE'
  | 'PENDING'
  | 'QUEUED'
  | 'RUNNING'
  | 'RETRYING'
  | 'MANUAL_REVIEW'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED'

export type PricingAgentCode = 'DATA_ANALYSIS' | 'MARKET_INTEL' | 'RISK_CONTROL' | 'MANAGER_COORDINATOR'

export interface AgentCardContent {
  thinking: string
  evidence: Array<Record<string, unknown>>
  suggestion: Record<string, unknown>
  reasonWhy?: string | null
}

export interface PricingTaskDetail {
  taskId: number
  productId: number
  productTitle: string
  taskStatus: PricingTaskStatus
  currentPrice: number
  suggestedMinPrice?: number
  suggestedMaxPrice?: number
  finalPrice?: number
  expectedSales?: number
  expectedProfit?: number
  strategy?: string
  finalSummary?: string
  createdAt: string
  updatedAt: string
}

export interface PricingTaskCreateRequest {
  productId: number
  constraints: string
  strategyGoal?: string
}

export interface PricingTaskResultPayload {
  finalPrice: number
  expectedSales: number
  expectedProfit: number
  strategy?: string
  summary?: string
}

export interface PricingTaskStartedMessage {
  schemaVersion: string
  channel: string
  type: 'task_started'
  taskId: number
  timestamp: string
  status?: PricingTaskStatus
}

export interface PricingAgentCardMessage {
  schemaVersion: string
  channel: string
  type: 'agent_card'
  taskId: number
  timestamp: string
  agentCode: PricingAgentCode
  agentName: string
  displayOrder: number
  stage: string
  card: AgentCardContent
}

export interface PricingTaskCompletedMessage {
  schemaVersion: string
  channel: string
  type: 'task_completed'
  taskId: number
  timestamp: string
  status?: PricingTaskStatus
  result?: PricingTaskResultPayload
}

export interface PricingTaskFailedMessage {
  schemaVersion: string
  channel: string
  type: 'task_failed'
  taskId: number
  timestamp: string
  status?: PricingTaskStatus
  message?: string
}

export type PricingTaskStreamMessage =
  | PricingTaskStartedMessage
  | PricingAgentCardMessage
  | PricingTaskCompletedMessage
  | PricingTaskFailedMessage

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

export const createPricingTask = (data: PricingTaskCreateRequest) => {
  return request.post('/pricing/tasks', data)
}

export const getPricingTaskDetail = (taskId: number) => {
  return request.get(`/pricing/tasks/${taskId}`)
}

export const getPricingTaskLogs = (taskId: number) => {
  return request.get(`/pricing/tasks/${taskId}/logs`)
}

export const getPricingTaskStreamUrl = (taskId: number) => `/api/pricing/tasks/${taskId}/events`

export const cancelPricingTask = (taskId: number) => {
  return request.post(`/pricing/tasks/${taskId}/cancel`)
}

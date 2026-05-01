/**
 * 定价任务接口封装，统一维护任务创建、结果查询、日志查询与 SSE 消息类型。
 */

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

export interface ReplaySourceMeta {
  logId?: number | null
  executionId?: string | null
  runAttempt?: number | null
}

export interface DecisionLogItem {
  id: number
  roleName?: string
  speakOrder?: number
  thoughtContent?: string
  agentCode?: string
  agentName?: string
  runAttempt?: number
  runOrder?: number
  displayOrder?: number
  stage?: 'running' | 'completed' | 'failed' | string
  runStatus?: 'running' | 'success' | 'failed' | string
  outputSummary?: string
  suggestedPrice?: number
  predictedProfit?: number
  confidenceScore?: number
  riskLevel?: string
  needManualReview?: boolean
  thinking?: string
  evidence?: Array<Record<string, unknown>>
  suggestion?: AgentSuggestion
  agentOpinion?: AgentOpinion | null
  reasonWhy?: string
  consensusScore?: number | null
  disagreementSummary?: string | null
  disagreementPoints?: ManagerArbitrationItem[] | null
  conflicts?: ManagerArbitrationItem[] | null
  disagreements?: ManagerArbitrationItem[] | null
  conflictPoints?: ManagerArbitrationItem[] | null
  acceptedOpinions?: ManagerArbitrationItem[] | null
  rejectedOpinions?: ManagerArbitrationItem[] | null
  arbitrationDecision?: string | null
  arbitrationSummary?: string | null
  arbitrationReason?: string | null
  decisionSummary?: string | null
  decisionReason?: string | null
  selectedAgent?: string | null
  selectedOption?: string | null
  selectedPrice?: number | null
  selectedStrategy?: string | null
  replayed?: boolean
  source?: ReplaySourceMeta | null
  sourceLogId?: number | null
  sourceExecutionId?: string | null
  sourceRunAttempt?: number | null
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

export type ManagerArbitrationItem = string | Record<string, unknown>

export interface AgentOpinionEvidence {
  key: string
  label: string
  value: unknown
  source?: string | null
}

export interface AgentOpinionPricing {
  recommendedPrice?: number | string | null
  minPrice?: number | string | null
  maxPrice?: number | string | null
  safeFloorPrice?: number | string | null
}

export interface AgentOpinionImpact {
  expectedSales?: number | null
  expectedProfit?: number | string | null
  profitGrowth?: number | string | null
}

export interface AgentOpinionMarket {
  marketFloor?: number | string | null
  marketCeiling?: number | string | null
  marketMedian?: number | string | null
  marketAverage?: number | string | null
  validCompetitorCount?: number | null
  dataQuality?: string | null
  sourceStatus?: string | null
}

export interface AgentOpinionRisk {
  isPass?: boolean | null
  riskLevel?: string | null
  needManualReview?: boolean | null
}

export interface AgentOpinionRationale {
  thinking?: string | null
  assumptions?: string[] | null
  notes?: string[] | null
}

export interface AgentOpinionRelations {
  dependsOnOpinionIds?: string[] | null
  acceptedOpinionIds?: string[] | null
  rejectedOpinionIds?: string[] | null
  conflictOpinionIds?: string[] | null
  selectedOpinionIds?: string[] | null
}

export interface AgentOpinionDecision {
  decisionType?: string | null
  consensusScore?: number | null
  arbitrationDecision?: string | null
  arbitrationReason?: string | null
}

export interface AgentOpinion {
  version?: string
  opinionId?: string
  taskId?: number
  runAttempt?: number
  agentCode?: PricingAgentCode | string
  agentName?: string
  kind?: string
  status?: string
  summary?: string
  confidence?: number | null
  pricing?: AgentOpinionPricing | null
  impact?: AgentOpinionImpact | null
  market?: AgentOpinionMarket | null
  risk?: AgentOpinionRisk | null
  evidence?: AgentOpinionEvidence[] | null
  rationale?: AgentOpinionRationale | null
  relations?: AgentOpinionRelations | null
  decision?: AgentOpinionDecision | null
}

export interface ManagerArbitrationFields {
  consensusScore?: number | null
  disagreementSummary?: string | null
  disagreementPoints?: ManagerArbitrationItem[] | null
  conflicts?: ManagerArbitrationItem[] | null
  disagreements?: ManagerArbitrationItem[] | null
  conflictPoints?: ManagerArbitrationItem[] | null
  acceptedOpinions?: ManagerArbitrationItem[] | null
  rejectedOpinions?: ManagerArbitrationItem[] | null
  arbitrationDecision?: string | null
  arbitrationSummary?: string | null
  arbitrationReason?: string | null
  decisionSummary?: string | null
  decisionReason?: string | null
  selectedAgent?: string | null
  selectedOption?: string | null
  selectedPrice?: number | null
  selectedStrategy?: string | null
}

export type AgentSuggestion = Record<string, unknown> & ManagerArbitrationFields

export interface AgentCardContent extends ManagerArbitrationFields {
  thinking: string
  evidence: Array<Record<string, unknown>>
  suggestion: AgentSuggestion
  agentOpinion?: AgentOpinion | null
  reasonWhy?: string | null
  replayed?: boolean
  sourceLogId?: number | null
  sourceExecutionId?: string | null
  sourceRunAttempt?: number | null
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

export interface PricingTaskSnapshot {
  detail: PricingTaskDetail
  logs: DecisionLogItem[]
  comparison: DecisionComparisonItem[]
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
  runAttempt?: number
  replayed?: boolean
  sourceLogId?: number | null
  sourceExecutionId?: string | null
  sourceRunAttempt?: number | null
  stage: 'running' | 'completed' | 'failed' | string
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

export const deleteDecisionTask = (taskId: number) => {
  return request.delete(`/decision/tasks/${taskId}`)
}

export const batchDeleteDecisionTasks = (ids: number[]) => {
  return request.delete('/decision/tasks/batch-delete', { params: { ids: ids.join(',') } })
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

export const getPricingTaskSnapshot = (taskId: number) => {
  return request.get(`/pricing/tasks/${taskId}/snapshot`)
}

export const getPricingTaskStreamUrl = (taskId: number) => `/api/pricing/tasks/${taskId}/events`

export const cancelPricingTask = (taskId: number) => {
  return request.post(`/pricing/tasks/${taskId}/cancel`)
}

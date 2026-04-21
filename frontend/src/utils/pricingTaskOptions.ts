/**
 * 定价任务选项常量，集中定义策略目标等前端可选项。
 */

export const PRICING_GOAL_OPTIONS = [
  { label: 'MAX_PROFIT', name: '利润优先' },
  { label: 'CLEARANCE', name: '清仓促销' },
  { label: 'MARKET_SHARE', name: '市场份额优先' }
] as const

export type PricingGoal = (typeof PRICING_GOAL_OPTIONS)[number]['label']

export const PRICING_GOAL_LABELS: Record<string, string> = Object.fromEntries(
  PRICING_GOAL_OPTIONS.map((item) => [item.label, item.name])
)

export const PRICING_STATUS_LABELS: Record<string, string> = {
  PENDING: '待执行',
  QUEUED: '待执行',
  RUNNING: '执行中',
  RETRYING: '重试中',
  MANUAL_REVIEW: '人工审核',
  COMPLETED: '已完成',
  FAILED: '失败',
  CANCELLED: '已取消',
  CREATE_FAILED: '创建失败',
  PARTIAL_FAILED: '部分失败'
}

export const PRICING_STATUS_TAG_TYPES: Record<string, 'info' | 'warning' | 'success' | 'danger'> = {
  PENDING: 'info',
  QUEUED: 'info',
  RUNNING: 'warning',
  RETRYING: 'warning',
  MANUAL_REVIEW: 'warning',
  COMPLETED: 'success',
  FAILED: 'danger',
  CANCELLED: 'info',
  CREATE_FAILED: 'danger',
  PARTIAL_FAILED: 'warning'
}

export const PRICING_BATCH_STATUS_OPTIONS = [
  { label: '待执行', value: 'PENDING' },
  { label: '执行中', value: 'RUNNING' },
  { label: '重试中', value: 'RETRYING' },
  { label: '人工审核', value: 'MANUAL_REVIEW' },
  { label: '已完成', value: 'COMPLETED' },
  { label: '失败', value: 'FAILED' },
  { label: '已取消', value: 'CANCELLED' },
  { label: '创建失败', value: 'CREATE_FAILED' }
]

export const isRunningPricingStatus = (status?: string | null) =>
  ['PENDING', 'QUEUED', 'RUNNING', 'RETRYING'].includes(String(status || '').trim().toUpperCase())

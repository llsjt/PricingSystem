/**
 * 动画刷新策略工具，用于在快照刷新和流式更新之间决定是否保留动画状态。
 */

export const RUNNING_PRICING_TASK_STATUSES = new Set(['PENDING', 'QUEUED', 'RUNNING', 'RETRYING'])

export const shouldKeepRevealEnabledAfterRefresh = (
  status: string | null | undefined,
  wasRevealEnabled: boolean
) => Boolean(wasRevealEnabled && RUNNING_PRICING_TASK_STATUSES.has(String(status || '').toUpperCase()))

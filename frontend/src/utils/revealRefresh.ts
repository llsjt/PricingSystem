export const RUNNING_PRICING_TASK_STATUSES = new Set(['PENDING', 'QUEUED', 'RUNNING', 'RETRYING'])

export const shouldKeepRevealEnabledAfterRefresh = (
  status: string | null | undefined,
  wasRevealEnabled: boolean
) => Boolean(wasRevealEnabled && RUNNING_PRICING_TASK_STATUSES.has(String(status || '').toUpperCase()))

export interface AgentTimelineItem<TCode extends string = string> {
  code: TCode
  name: string
  order: number
}

export type AgentTimelineCardState = {
  __stage?: string
} | null | undefined

export const buildVisibleAgentTimeline = <TAgent extends AgentTimelineItem>(
  agents: readonly TAgent[],
  cards: Partial<Record<TAgent['code'], AgentTimelineCardState>>
) => agents.filter((agent) => Boolean(cards[agent.code]))

export type AgentRunRoundLog = {
  agentCode?: string | null
  displayOrder?: number | string | null
  runOrder?: number | string | null
  runAttempt?: number | string | null
  stage?: string | null
}

const toRunAttempt = (value: unknown): number | null => {
  if (value === null || value === undefined || value === '') return null
  const attempt = Number(value)
  return Number.isFinite(attempt) && attempt >= 0 ? attempt : null
}

export const filterLatestAgentRunRound = <TLog extends AgentRunRoundLog>(logs: readonly TLog[]): TLog[] => {
  let latestAttempt: number | null = null
  const attempts = new Set<number>()
  for (const log of logs) {
    const attempt = toRunAttempt(log.runAttempt)
    if (attempt === null) continue
    attempts.add(attempt)
    latestAttempt = latestAttempt === null ? attempt : Math.max(latestAttempt, attempt)
  }
  if (latestAttempt === null) return filterLatestInferredRunRound(logs)
  if (attempts.size <= 1) return filterLatestInferredRunRound(logs)
  return logs.filter((log) => toRunAttempt(log.runAttempt) === latestAttempt)
}

export const resolveLatestAgentRunAttempt = (logs: readonly AgentRunRoundLog[]): number | null => {
  let latestAttempt: number | null = null
  for (const log of logs) {
    const attempt = toRunAttempt(log.runAttempt)
    if (attempt === null) continue
    latestAttempt = latestAttempt === null ? attempt : Math.max(latestAttempt, attempt)
  }
  return latestAttempt
}

const isFirstAgentRunningLog = (log: AgentRunRoundLog) => {
  const code = String(log.agentCode || '').trim()
  const order = Number(log.displayOrder ?? log.runOrder ?? 0)
  const stage = String(log.stage || '').trim().toLowerCase()
  return stage === 'running' && (code === 'DATA_ANALYSIS' || order === 1)
}

const filterLatestInferredRunRound = <TLog extends AgentRunRoundLog>(logs: readonly TLog[]): TLog[] => {
  let latestStart = -1
  let startCount = 0
  logs.forEach((log, index) => {
    if (!isFirstAgentRunningLog(log)) return
    latestStart = index
    startCount += 1
  })
  if (startCount <= 1 || latestStart < 0) return [...logs]
  return logs.slice(latestStart)
}

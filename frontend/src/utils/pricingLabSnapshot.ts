import type { AgentCardContent, DecisionLogItem, PricingAgentCode } from '../api/decision'
import { extractManagerArbitrationFields } from './agentOpinion'
import { filterLatestAgentRunRound, resolveLatestAgentRunAttempt } from './agentTimeline'
import { AGENT_ORDER_BY_CODE, getLogAgentCode } from './decisionDisplay'

export type SnapshotAgentStage = 'running' | 'completed' | 'failed'

export interface SnapshotAgentCard {
  code: PricingAgentCode
  stage: SnapshotAgentStage
  card: AgentCardContent | null
  sortOrder: number
  logId: number
}

export interface SnapshotAgentCards {
  runAttempt: number | null
  cards: SnapshotAgentCard[]
}

const normalizeSnapshotStage = (stage: unknown): SnapshotAgentStage => {
  const normalized = String(stage || '').trim().toLowerCase()
  if (normalized === 'running') return 'running'
  if (normalized === 'failed') return 'failed'
  return 'completed'
}

const toNumericSortValue = (value: unknown, fallback: number) => {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : fallback
}

const resolveSnapshotAgentCode = (log: DecisionLogItem): PricingAgentCode | null =>
  getLogAgentCode(log)
  || (String(log.agentName || log.roleName || '').includes('经理') ? 'MANAGER_COORDINATOR' : null)

const buildSnapshotCardPayload = (log: DecisionLogItem): AgentCardContent => ({
  thinking: String(log.thinking || log.outputSummary || ''),
  evidence: Array.isArray(log.evidence) ? log.evidence : [],
  suggestion: log.suggestion && typeof log.suggestion === 'object' ? log.suggestion : {},
  agentOpinion: log.agentOpinion || null,
  reasonWhy: log.reasonWhy || null,
  ...extractManagerArbitrationFields(log)
})

export const buildSnapshotAgentCards = (logs: readonly DecisionLogItem[]): SnapshotAgentCards => {
  const latestLogs = filterLatestAgentRunRound(logs)
  const cards = latestLogs
    .map((log): SnapshotAgentCard | null => {
      const code = resolveSnapshotAgentCode(log)
      if (!code) return null
      const stage = normalizeSnapshotStage(log.stage)
      return {
        code,
        stage,
        card: stage === 'running' ? null : buildSnapshotCardPayload(log),
        sortOrder: toNumericSortValue(log.displayOrder ?? log.runOrder, AGENT_ORDER_BY_CODE[code]),
        logId: toNumericSortValue(log.id, 0)
      }
    })
    .filter((card): card is SnapshotAgentCard => Boolean(card))
    .sort((a, b) => a.sortOrder - b.sortOrder || a.logId - b.logId)

  return {
    runAttempt: resolveLatestAgentRunAttempt(latestLogs),
    cards
  }
}

import type { AgentCardContent, DecisionLogItem, PricingAgentCode } from '../api/decision'
import { extractManagerArbitrationFields } from './agentOpinion'
import { filterLatestAgentRunRound, hasExplicitAgentRunAttempt, resolveLatestAgentRunAttempt } from './agentTimeline'
import { AGENT_ORDER_BY_CODE, getLogAgentCode } from './decisionDisplay'

export type SnapshotAgentStage = 'running' | 'completed' | 'failed'
export type SnapshotExistingCard = (AgentCardContent & { __stage?: SnapshotAgentStage }) | null
export type SnapshotExistingCardMap = Partial<Record<PricingAgentCode, SnapshotExistingCard>>

export interface SnapshotAgentCard {
  code: PricingAgentCode
  stage: SnapshotAgentStage
  card: AgentCardContent | null
  sortOrder: number
  logId: number
}

export interface SnapshotAgentCards {
  runAttempt: number | null
  resolvedRunAttempt: number | null
  hasExplicitRunAttempt: boolean
  missingAgentCodes: PricingAgentCode[]
  cards: SnapshotAgentCard[]
}

const SNAPSHOT_AGENT_ORDER: PricingAgentCode[] = [
  'DATA_ANALYSIS',
  'MARKET_INTEL',
  'RISK_CONTROL',
  'MANAGER_COORDINATOR'
]

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

const toOptionalNumber = (value: unknown): number | null | undefined => {
  if (value === undefined) return undefined
  if (value === null || value === '') return null
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

const toOptionalString = (value: unknown): string | null | undefined => {
  if (value === undefined) return undefined
  if (value === null || value === '') return null
  return String(value)
}

const resolveSnapshotAgentCode = (log: DecisionLogItem): PricingAgentCode | null =>
  getLogAgentCode(log)
  || (String(log.agentName || log.roleName || '').includes('经理') ? 'MANAGER_COORDINATOR' : null)

const buildReplayMeta = (log: DecisionLogItem) => ({
  replayed: log.replayed === true ? true : undefined,
  sourceLogId: toOptionalNumber(log.sourceLogId ?? log.source?.logId),
  sourceExecutionId: toOptionalString(log.sourceExecutionId ?? log.source?.executionId),
  sourceRunAttempt: toOptionalNumber(log.sourceRunAttempt ?? log.source?.runAttempt)
})

const buildSnapshotCardPayload = (log: DecisionLogItem): AgentCardContent => ({
  thinking: String(log.thinking || log.outputSummary || ''),
  evidence: Array.isArray(log.evidence) ? log.evidence : [],
  suggestion: log.suggestion && typeof log.suggestion === 'object' ? log.suggestion : {},
  agentOpinion: log.agentOpinion || null,
  reasonWhy: log.reasonWhy || null,
  ...buildReplayMeta(log),
  ...extractManagerArbitrationFields(log)
})

export const buildSnapshotAgentCards = (logs: readonly DecisionLogItem[]): SnapshotAgentCards => {
  const latestLogs = filterLatestAgentRunRound(logs)
  const resolvedRunAttempt = resolveLatestAgentRunAttempt(latestLogs)
  const hasExplicitRunAttempt = hasExplicitAgentRunAttempt(logs)
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

  const visibleCodes = new Set(cards.map((card) => card.code))

  return {
    runAttempt: resolvedRunAttempt,
    resolvedRunAttempt,
    hasExplicitRunAttempt,
    missingAgentCodes: SNAPSHOT_AGENT_ORDER.filter((code) => !visibleCodes.has(code)),
    cards
  }
}

export const applySnapshotCardsPreservingTerminalState = (
  existingCards: SnapshotExistingCardMap,
  snapshot: SnapshotAgentCards
): SnapshotExistingCardMap => {
  const nextCards: SnapshotExistingCardMap = {
    ...existingCards
  }

  snapshot.cards.forEach(({ code, stage, card }) => {
    const existingCard = existingCards[code]
    if (stage === 'running') {
      if (!existingCard || existingCard.__stage === 'running') nextCards[code] = null
      return
    }
    if (!card) {
      nextCards[code] = null
      return
    }
    nextCards[code] = {
      ...card,
      __stage: stage
    }
  })

  return nextCards
}

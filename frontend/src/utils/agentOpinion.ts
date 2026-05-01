import type {
  AgentCardContent,
  AgentOpinion,
  DecisionLogItem,
  ManagerArbitrationFields,
  ManagerArbitrationItem,
  PricingAgentCode
} from '../api/decision'
import { formatCurrency } from './formatters'

const AGENT_NAME_BY_CODE: Record<PricingAgentCode, string> = {
  DATA_ANALYSIS: '经营收益测算',
  MARKET_INTEL: '竞品市场判断',
  RISK_CONTROL: '利润底线校验',
  MANAGER_COORDINATOR: '定价决策经理'
}

type AgentOpinionSource =
  | (Partial<DecisionLogItem> & Partial<AgentCardContent> & { card?: unknown })
  | null
  | undefined

export interface NormalizedManagerArbitration {
  consensusScore: number | null
  consensusScoreText: string | null
  consensusScorePercent: number | null
  disagreementSummary: string | null
  disagreementPoints: string[]
  acceptedOpinions: string[]
  rejectedOpinions: string[]
  decisionSummary: string | null
  decisionReason: string | null
  selectedAgentCode: PricingAgentCode | null
  selectedAgentLabel: string | null
  selectedPrice: number | null
  selectedPriceText: string | null
  selectedStrategy: string | null
}

export interface NormalizedAgentOpinion {
  opinionId: string | null
  agentCode: PricingAgentCode | null
  agentName: string | null
  kind: string | null
  status: string | null
  summary: string | null
  confidence: number | null
  recommendedPrice: number | null
  minPrice: number | null
  maxPrice: number | null
  safeFloorPrice: number | null
  expectedSales: number | null
  expectedProfit: number | null
  riskLevel: string | null
  evidenceLines: string[]
  arbitration: NormalizedManagerArbitration | null
  raw: Record<string, unknown>
}

const coerceRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}

const toNumber = (value: unknown) => {
  if (value === null || value === undefined || value === '') return null
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

const toText = (value: unknown) => {
  const text = String(value ?? '').trim()
  return text || null
}

const normalizeAgentCode = (value: unknown): PricingAgentCode | null => {
  const code = String(value ?? '').trim() as PricingAgentCode
  return code in AGENT_NAME_BY_CODE ? code : null
}

const parseAgentCodeFromOpinionId = (value: unknown): PricingAgentCode | null => {
  const match = String(value ?? '').match(/:agent:([A-Z_]+):/)
  return normalizeAgentCode(match?.[1] || '')
}

const readLegacyField = (source: AgentOpinionSource, keys: string[]) => {
  const root = coerceRecord(source)
  const suggestion = coerceRecord(root.suggestion)
  for (const key of keys) {
    if (root[key] !== undefined && root[key] !== null && root[key] !== '') return root[key]
    if (suggestion[key] !== undefined && suggestion[key] !== null && suggestion[key] !== '') return suggestion[key]
  }
  return null
}

const formatArbitrationItem = (value: ManagerArbitrationItem | unknown): string => {
  if (typeof value === 'string') return value
  const record = coerceRecord(value)
  if (record.opinionId || record.summary) {
    return String(record.summary || record.opinionId)
  }
  if (record.field || record.reason) {
    const field = String(record.field || '字段')
    const reason = String(record.reason || '')
    return reason ? `${field}：${reason}` : field
  }
  const parts = Object.entries(record)
    .filter(([, currentValue]) => currentValue !== null && currentValue !== undefined && currentValue !== '')
    .map(([key, currentValue]) => `${key}：${String(currentValue)}`)
  return parts.join('，') || String(value ?? '')
}

const asItemList = (value: unknown): string[] =>
  Array.isArray(value)
    ? value.filter((item) => item !== null && item !== undefined).map((item) => formatArbitrationItem(item))
    : []

const asOpinionIdList = (value: unknown): string[] =>
  Array.isArray(value)
    ? value.map((item) => String(item ?? '').trim()).filter(Boolean)
    : []

const formatEvidenceLines = (value: unknown): string[] => {
  if (!Array.isArray(value) || value.length === 0) return []
  return value
    .map((item) => {
      const record = coerceRecord(item)
      const label = String(record.label || '依据')
      const rawValue = record.value
      if (rawValue === null || rawValue === undefined || rawValue === '') return null
      return `${label}：${typeof rawValue === 'object' ? formatArbitrationItem(rawValue) : String(rawValue)}`
    })
    .filter((item): item is string => Boolean(item))
}

const buildArbitration = (
  opinion: Record<string, unknown>,
  source: AgentOpinionSource
): NormalizedManagerArbitration | null => {
  const decision = coerceRecord(opinion.decision)
  const relations = coerceRecord(opinion.relations)
  const pricing = coerceRecord(opinion.pricing)
  const consensusScore = toNumber(decision.consensusScore ?? readLegacyField(source, ['consensusScore']))
  const disagreementPoints = asOpinionIdList(relations.conflictOpinionIds)
  const acceptedOpinionIds = asOpinionIdList(relations.acceptedOpinionIds)
  const rejectedOpinionIds = asOpinionIdList(relations.rejectedOpinionIds)
  const selectedOpinionIds = asOpinionIdList(relations.selectedOpinionIds)
  const legacyDisagreementPoints = asItemList(readLegacyField(source, ['disagreementPoints', 'conflicts', 'disagreements', 'conflictPoints']))
  const legacyAccepted = asItemList(readLegacyField(source, ['acceptedOpinions']))
  const legacyRejected = asItemList(readLegacyField(source, ['rejectedOpinions']))

  const selectedAgentCode = normalizeAgentCode(readLegacyField(source, ['selectedAgent', 'selectedOption']))
    || parseAgentCodeFromOpinionId(selectedOpinionIds[0] || acceptedOpinionIds[0])
  const selectedPrice = toNumber(readLegacyField(source, ['selectedPrice'])) ?? toNumber(pricing.recommendedPrice)
  const selectedStrategy = toText(readLegacyField(source, ['selectedStrategy'])) || toText(coerceRecord(coerceRecord(source).suggestion).strategy)

  const resolvedDisagreementPoints = legacyDisagreementPoints.length ? legacyDisagreementPoints : disagreementPoints
  const resolvedAccepted = legacyAccepted.length ? legacyAccepted : acceptedOpinionIds
  const resolvedRejected = legacyRejected.length ? legacyRejected : rejectedOpinionIds
  const decisionSummary = toText(decision.arbitrationDecision ?? readLegacyField(source, ['arbitrationDecision', 'arbitrationSummary', 'decisionSummary']))
  const decisionReason = toText(decision.arbitrationReason ?? readLegacyField(source, ['arbitrationReason', 'decisionReason']))
  const disagreementSummary = toText(readLegacyField(source, ['disagreementSummary']))

  if (
    consensusScore === null
    && !resolvedDisagreementPoints.length
    && !resolvedAccepted.length
    && !resolvedRejected.length
    && !decisionSummary
    && !decisionReason
    && !selectedAgentCode
    && selectedPrice === null
    && !selectedStrategy
  ) {
    return null
  }

  const consensusPercent = consensusScore === null ? null : Math.max(0, Math.min(100, consensusScore > 1 ? consensusScore : consensusScore * 100))
  return {
    consensusScore,
    consensusScoreText: consensusPercent === null ? null : `${consensusPercent.toFixed(2)}%`,
    consensusScorePercent: consensusPercent,
    disagreementSummary,
    disagreementPoints: resolvedDisagreementPoints,
    acceptedOpinions: resolvedAccepted,
    rejectedOpinions: resolvedRejected,
    decisionSummary,
    decisionReason,
    selectedAgentCode,
    selectedAgentLabel: selectedAgentCode ? AGENT_NAME_BY_CODE[selectedAgentCode] : null,
    selectedPrice,
    selectedPriceText: selectedPrice === null ? null : formatCurrency(selectedPrice),
    selectedStrategy,
  }
}

export const normalizeAgentOpinion = (source: AgentOpinionSource): NormalizedAgentOpinion | null => {
  const root = coerceRecord(source)
  const card = coerceRecord(root.card)
  const sourceOpinion = coerceRecord(root.agentOpinion)
  const cardOpinion = coerceRecord(card.agentOpinion)
  const opinion = Object.keys(sourceOpinion).length ? sourceOpinion : cardOpinion
  const suggestion = coerceRecord(root.suggestion)
  const pricing = coerceRecord(opinion.pricing)
  const impact = coerceRecord(opinion.impact)
  const risk = coerceRecord(opinion.risk)

  const recommendedPrice = toNumber(pricing.recommendedPrice ?? suggestion.recommendedPrice ?? suggestion.finalPrice ?? root.suggestedPrice)
  const summary = toText(opinion.summary ?? readLegacyField(source, ['summary', 'resultSummary']))
  const evidenceLines = formatEvidenceLines(opinion.evidence ?? root.evidence)
  const arbitration = buildArbitration(opinion, source)

  if (!Object.keys(opinion).length && !summary && recommendedPrice === null && evidenceLines.length === 0 && !arbitration) {
    return null
  }

  return {
    opinionId: toText(opinion.opinionId),
    agentCode: normalizeAgentCode(opinion.agentCode ?? root.agentCode),
    agentName: toText(opinion.agentName ?? root.agentName ?? root.roleName),
    kind: toText(opinion.kind),
    status: toText(opinion.status),
    summary,
    confidence: toNumber(opinion.confidence ?? root.confidenceScore),
    recommendedPrice,
    minPrice: toNumber(pricing.minPrice),
    maxPrice: toNumber(pricing.maxPrice),
    safeFloorPrice: toNumber(pricing.safeFloorPrice),
    expectedSales: toNumber(impact.expectedSales),
    expectedProfit: toNumber(impact.expectedProfit),
    riskLevel: toText(risk.riskLevel ?? root.riskLevel),
    evidenceLines,
    arbitration,
    raw: opinion
  }
}

export const extractManagerArbitrationFields = (
  source?: AgentOpinionSource
): ManagerArbitrationFields => {
  const normalized = normalizeAgentOpinion(source)
  if (normalized?.arbitration) {
    const arbitration = normalized.arbitration
    const disagreementPoints = arbitration.disagreementPoints.length ? arbitration.disagreementPoints : null
    return {
      consensusScore: arbitration.consensusScore,
      disagreementSummary: arbitration.disagreementSummary,
      disagreementPoints,
      disagreements: null,
      conflictPoints: null,
      conflicts: disagreementPoints,
      acceptedOpinions: arbitration.acceptedOpinions.length ? arbitration.acceptedOpinions : null,
      rejectedOpinions: arbitration.rejectedOpinions.length ? arbitration.rejectedOpinions : null,
      arbitrationDecision: arbitration.decisionSummary,
      arbitrationSummary: arbitration.decisionSummary,
      arbitrationReason: arbitration.decisionReason,
      decisionSummary: arbitration.decisionSummary,
      decisionReason: arbitration.decisionReason,
      selectedAgent: arbitration.selectedAgentCode,
      selectedOption: arbitration.selectedAgentCode,
      selectedPrice: arbitration.selectedPrice,
      selectedStrategy: arbitration.selectedStrategy
    }
  }

  return {
    consensusScore: toNumber(readLegacyField(source, ['consensusScore'])),
    disagreementSummary: toText(readLegacyField(source, ['disagreementSummary'])),
    disagreementPoints: Array.isArray(readLegacyField(source, ['disagreementPoints', 'conflicts', 'disagreements', 'conflictPoints']))
      ? readLegacyField(source, ['disagreementPoints', 'conflicts', 'disagreements', 'conflictPoints']) as ManagerArbitrationItem[]
      : null,
    disagreements: Array.isArray(readLegacyField(source, ['disagreements']))
      ? readLegacyField(source, ['disagreements']) as ManagerArbitrationItem[]
      : null,
    conflictPoints: Array.isArray(readLegacyField(source, ['conflictPoints']))
      ? readLegacyField(source, ['conflictPoints']) as ManagerArbitrationItem[]
      : null,
    conflicts: Array.isArray(readLegacyField(source, ['conflicts']))
      ? readLegacyField(source, ['conflicts']) as ManagerArbitrationItem[]
      : null,
    acceptedOpinions: Array.isArray(readLegacyField(source, ['acceptedOpinions']))
      ? readLegacyField(source, ['acceptedOpinions']) as ManagerArbitrationItem[]
      : null,
    rejectedOpinions: Array.isArray(readLegacyField(source, ['rejectedOpinions']))
      ? readLegacyField(source, ['rejectedOpinions']) as ManagerArbitrationItem[]
      : null,
    arbitrationDecision: toText(readLegacyField(source, ['arbitrationDecision'])),
    arbitrationSummary: toText(readLegacyField(source, ['arbitrationSummary'])),
    arbitrationReason: toText(readLegacyField(source, ['arbitrationReason'])),
    decisionSummary: toText(readLegacyField(source, ['decisionSummary'])),
    decisionReason: toText(readLegacyField(source, ['decisionReason'])),
    selectedAgent: toText(readLegacyField(source, ['selectedAgent'])),
    selectedOption: toText(readLegacyField(source, ['selectedOption'])),
    selectedPrice: toNumber(readLegacyField(source, ['selectedPrice'])),
    selectedStrategy: toText(readLegacyField(source, ['selectedStrategy']))
  }
}

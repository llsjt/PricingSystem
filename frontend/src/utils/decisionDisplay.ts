import type { DecisionLogItem, PricingAgentCode } from '../api/decision'
import { formatCurrency, formatPercent } from './formatters.ts'

export type DecisionDisplayLine = string

export const AGENT_ORDER_BY_CODE: Record<PricingAgentCode, number> = {
  DATA_ANALYSIS: 1,
  MARKET_INTEL: 2,
  RISK_CONTROL: 3,
  MANAGER_COORDINATOR: 4
}

export const AGENT_NAME_BY_CODE: Record<PricingAgentCode, string> = {
  DATA_ANALYSIS: '数据分析Agent',
  MARKET_INTEL: '市场情报Agent',
  RISK_CONTROL: '风险控制Agent',
  MANAGER_COORDINATOR: '经理协调Agent'
}

const TEXT_VALUE_MAP: Record<string, string> = {
  MAX_PROFIT: '利润优先',
  CLEARANCE: '清仓促销',
  MARKET_SHARE: '市场份额优先',
  AUTO_EXECUTE: '自动执行',
  MANUAL_REVIEW: '人工审核',
  LOW: '低',
  MEDIUM: '中',
  HIGH: '高',
  QUEUED: '待执行',
  RETRYING: '重试中',
  SUCCESS: '成功',
  RUNNING: '执行中',
  COMPLETED: '已完成',
  CANCELLED: '已取消',
  FAILED: '失败',
  PENDING: '待执行',
  TMALL_CSV: '天猫真实样本',
  TMALL_CSV_FALLBACK: '天猫样本缺失·模拟补全'
}

const DATA_QUALITY_MAP: Record<string, string> = {
  HIGH: '高',
  MEDIUM: '中',
  LOW: '低'
}

export const normalizeAgentCode = (code?: string | null): PricingAgentCode | null => {
  const normalized = String(code || '') as PricingAgentCode
  return normalized in AGENT_ORDER_BY_CODE ? normalized : null
}

export const toNaturalChinese = (value: unknown): string => {
  const text = String(value ?? '').trim()
  if (!text) return '-'
  const upper = text.toUpperCase()
  return TEXT_VALUE_MAP[upper] || text
}

export const isSuccessStatus = (status?: string | null) => {
  const normalized = String(status || '').trim().toUpperCase()
  return normalized === 'SUCCESS' || normalized === '成功'
}

export const isFailedStatus = (status?: string | null) => {
  const normalized = String(status || '').trim().toUpperCase()
  return normalized === 'FAILED' || normalized === '失败'
}

export const getRunStatusType = (status?: string | null): 'success' | 'warning' | 'danger' => {
  if (isSuccessStatus(status)) return 'success'
  if (isFailedStatus(status)) return 'danger'
  return 'warning'
}

export const getRunStatusText = (status?: string | null) => (status ? toNaturalChinese(status) : '-')

const formatDataQualityText = (value: unknown) => {
  const text = String(value ?? '').trim().toUpperCase()
  return DATA_QUALITY_MAP[text] || String(value ?? '-')
}

const toNumber = (value: unknown) => {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

const formatBoolean = (value: boolean) => (value ? '是' : '否')

const formatPrimitive = (key: string, value: unknown): string => {
  if (value == null) return '-'
  if (typeof value === 'boolean') return formatBoolean(value)

  const numeric = toNumber(value)
  if (numeric != null) {
    const lowered = key.toLowerCase()
    if (lowered.includes('price') || lowered.includes('profit') || lowered.includes('amount')) {
      return formatCurrency(numeric)
    }
    if (lowered.includes('rate')) {
      return formatPercent(numeric)
    }
    return String(numeric)
  }

  return toNaturalChinese(value)
}

const formatObjectLine = (value: Record<string, unknown>) => {
  if ('competitorName' in value) {
    const name = String(value.competitorName || '竞品')
    const platform = String(value.sourcePlatform || '')
    const shopType = String(value.shopType || '')
    const title = platform ? `${name}（${platform}${shopType ? `/${shopType}` : ''}）` : name

    const parts: string[] = [title]
    if (value.price != null) parts.push(`价格${formatPrimitive('price', value.price)}`)
    if (value.originalPrice != null) parts.push(`原价${formatPrimitive('originalPrice', value.originalPrice)}`)
    if (value.salesVolumeHint != null) parts.push(`销量提示：${toNaturalChinese(value.salesVolumeHint)}`)
    if (value.promotionTag != null) parts.push(`促销：${toNaturalChinese(value.promotionTag)}`)
    return parts.join('，')
  }

  if ('brand' in value && 'averagePrice' in value) {
    const brand = String(value.brand || '未知品牌')
    const sample = toNumber(value.sampleCount)
    const avg = toNumber(value.averagePrice)
    const min = toNumber(value.minPrice)
    const max = toNumber(value.maxPrice)
    const parts: string[] = [brand]
    if (sample != null) parts.push(`样本${sample}件`)
    if (avg != null) parts.push(`均价${formatCurrency(avg)}`)
    if (min != null && max != null) parts.push(`区间${formatCurrency(min)}~${formatCurrency(max)}`)
    return parts.join('，')
  }

  if ('shopType' in value && 'share' in value) {
    const shopType = String(value.shopType || '其他')
    const share = toNumber(value.share)
    const sample = toNumber(value.sampleCount)
    const avg = toNumber(value.averagePrice)
    const parts: string[] = [shopType]
    if (share != null) parts.push(`占比${(share * 100).toFixed(1)}%`)
    if (sample != null) parts.push(`样本${sample}件`)
    if (avg != null) parts.push(`均价${formatCurrency(avg)}`)
    return parts.join('，')
  }

  if ('promotionRate' in value || 'averageDiscount' in value || 'promotedSampleCount' in value) {
    const rate = toNumber(value.promotionRate)
    const promoted = toNumber(value.promotedSampleCount)
    const discount = toNumber(value.averageDiscount)
    const parts: string[] = []
    if (rate != null) parts.push(`促销占比${(rate * 100).toFixed(1)}%`)
    if (promoted != null) parts.push(`在促样本${promoted}件`)
    if (discount != null) parts.push(`平均折扣率${discount.toFixed(2)}`)
    return parts.length ? parts.join('，') : '暂无促销数据'
  }

  const keyMap: Record<string, string> = {
    competitorName: '竞品',
    sourcePlatform: '平台',
    shopType: '店铺类型',
    promotionTag: '促销信息',
    salesVolumeHint: '销量提示',
    marketScore: '市场评分',
    riskLevel: '风险等级'
  }

  return Object.entries(value)
    .filter(([, currentValue]) => currentValue !== null && currentValue !== undefined)
    .map(([key, currentValue]) => `${keyMap[key] || key}：${formatPrimitive(key, currentValue)}`)
    .join('，')
}

export const formatEvidenceValue = (label: unknown, value: unknown): string => {
  if (value == null) return '-'

  if (String(label || '').includes('数据质量')) {
    return formatDataQualityText(value)
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return '暂无数据'
    const lines = value.map((item) => {
      if (item && typeof item === 'object') {
        return formatObjectLine(item as Record<string, unknown>)
      }
      return toNaturalChinese(item)
    })
    const joined = lines.join('；')
    if (String(label || '').includes('竞品摘要')) {
      return `共 ${value.length} 条：${joined}`
    }
    return joined
  }

  if (value && typeof value === 'object') {
    return formatObjectLine(value as Record<string, unknown>)
  }

  return toNaturalChinese(value)
}

export const getSuggestionLines = (
  code: PricingAgentCode | null,
  suggestion?: Record<string, unknown>
): DecisionDisplayLine[] => {
  if (!suggestion || Object.keys(suggestion).length === 0) {
    return ['暂无建议内容']
  }

  const lines: string[] = []
  const priceRange = suggestion.priceRange
  if (priceRange && typeof priceRange === 'object') {
    const range = priceRange as Record<string, unknown>
    const min = toNumber(range.min)
    const max = toNumber(range.max)
    if (min != null && max != null) {
      lines.push(`建议价格区间：${formatCurrency(min)} ~ ${formatCurrency(max)}`)
    }
  }

  if (code === 'DATA_ANALYSIS') {
    const recommendedPrice = toNumber(suggestion.recommendedPrice)
    if (recommendedPrice != null) lines.push(`建议定价：${formatCurrency(recommendedPrice)}`)
    const expectedSales = toNumber(suggestion.expectedSales)
    if (expectedSales != null) lines.push(`预期销量：${expectedSales}`)
    const expectedProfit = toNumber(suggestion.expectedProfit)
    if (expectedProfit != null) lines.push(`预期利润：${formatCurrency(expectedProfit)}`)
    const expectedProfitRate = toNumber(suggestion.expectedProfitRate)
    if (expectedProfitRate != null) lines.push(`预期利润率：${formatPercent(expectedProfitRate)}`)
  }

  if (code === 'MARKET_INTEL') {
    const recommendedPrice = toNumber(suggestion.recommendedPrice)
    if (recommendedPrice != null) lines.push(`建议定价：${formatCurrency(recommendedPrice)}`)
    const marketScore = toNumber(suggestion.marketScore)
    if (marketScore != null) lines.push(`市场接受度评分：${marketScore.toFixed(1)}`)
    if (suggestion.dataQuality != null) lines.push(`数据质量：${formatDataQualityText(suggestion.dataQuality)}`)
    if (suggestion.pricingPosition != null) lines.push(`当前价格位置：${toNaturalChinese(suggestion.pricingPosition)}`)
    const usedCompetitorCount = toNumber(suggestion.usedCompetitorCount)
    if (usedCompetitorCount != null) lines.push(`纳入分析竞品：${usedCompetitorCount}`)
    if (suggestion.source != null) lines.push(`竞品来源：${toNaturalChinese(suggestion.source)}`)
    if (suggestion.sourceStatus != null) lines.push(`竞品状态：${toNaturalChinese(suggestion.sourceStatus)}`)
    if (suggestion.evidenceSummary != null) lines.push(`证据摘要：${toNaturalChinese(suggestion.evidenceSummary)}`)
    if (suggestion.riskNotes != null) lines.push(`风险提示：${toNaturalChinese(suggestion.riskNotes)}`)

    const sourceStatus = String(suggestion.sourceStatus || '').toUpperCase()
    const dataQuality = String(suggestion.dataQuality || '').toUpperCase()
    if (sourceStatus && sourceStatus !== 'OK') {
      lines.push('未获取到可靠竞品，市场建议已降级')
    } else if (dataQuality === 'LOW') {
      lines.push('本次竞品数据不足，仅供参考')
    }
  }

  if (code === 'RISK_CONTROL') {
    const recommendedPrice = toNumber(suggestion.recommendedPrice)
    if (recommendedPrice != null) lines.push(`风控建议价：${formatCurrency(recommendedPrice)}`)
    if (typeof suggestion.pass === 'boolean') lines.push(`是否自动通过：${formatBoolean(suggestion.pass)}`)
    if (suggestion.riskLevel != null) lines.push(`风险等级：${toNaturalChinese(suggestion.riskLevel)}`)
    if (suggestion.action != null) lines.push(`建议动作：${toNaturalChinese(suggestion.action)}`)
  }

  if (code === 'MANAGER_COORDINATOR') {
    const finalPrice = toNumber(suggestion.finalPrice)
    if (finalPrice != null) lines.push(`最终建议价：${formatCurrency(finalPrice)}`)
    const expectedSales = toNumber(suggestion.expectedSales)
    if (expectedSales != null) lines.push(`预期销量：${expectedSales}`)
    const expectedProfit = toNumber(suggestion.expectedProfit)
    if (expectedProfit != null) lines.push(`预期利润：${formatCurrency(expectedProfit)}`)
    if (suggestion.strategy != null) lines.push(`执行策略：${toNaturalChinese(suggestion.strategy)}`)
  }

  if (suggestion.summary != null) {
    lines.push(`建议说明：${toNaturalChinese(suggestion.summary)}`)
  }

  if (lines.length > 0) {
    return lines
  }

  const keyMap: Record<string, string> = {
    summary: '建议说明',
    recommendedPrice: '建议定价',
    expectedSales: '预期销量',
    expectedProfit: '预期利润',
    expectedProfitRate: '预期利润率',
    marketScore: '市场接受度评分',
    pass: '是否自动通过',
    riskLevel: '风险等级',
    action: '建议动作',
    finalPrice: '最终建议价',
    strategy: '执行策略',
    error: '是否异常',
    message: '异常信息'
  }

  return Object.entries(suggestion)
    .filter(([, value]) => value !== null && value !== undefined)
    .map(([key, value]) => `${keyMap[key] || key}：${formatPrimitive(key, value)}`)
}

export const getLogAgentName = (log: Pick<DecisionLogItem, 'agentName' | 'agentCode' | 'roleName'>) => {
  if (log.agentName) return log.agentName
  const code = normalizeAgentCode(log.agentCode)
  if (code) return AGENT_NAME_BY_CODE[code]
  return log.agentCode || log.roleName || 'Agent'
}

export const getLogThinking = (log: DecisionLogItem) => String(log.thinking || log.outputSummary || log.thoughtContent || '-')

export const getLogEvidenceLines = (log: DecisionLogItem): DecisionDisplayLine[] => {
  const evidence = Array.isArray(log.evidence) ? log.evidence : []
  if (evidence.length === 0) return ['暂无依据内容']
  return evidence.map((item, index) => {
    const label = item?.label ?? `依据${index + 1}`
    return `${String(label)}：${formatEvidenceValue(label, item?.value)}`
  })
}

export const getLogSuggestionLines = (log: DecisionLogItem): DecisionDisplayLine[] => {
  const suggestion = log.suggestion && typeof log.suggestion === 'object' ? log.suggestion : {}
  return getSuggestionLines(normalizeAgentCode(log.agentCode), suggestion)
}

export const getLogReason = (log: DecisionLogItem) => String(log.reasonWhy || '').trim()

export const formatPriceRange = (min?: number | null, max?: number | null) =>
  `${formatCurrency(min)} - ${formatCurrency(max)}`

export const createApplyDecisionConfirmMessage = (productTitle: unknown, suggestedPrice: unknown) =>
  `确认将商品“${String(productTitle || '-')}”的售价更新为 ${formatCurrency(suggestedPrice)} 吗？`

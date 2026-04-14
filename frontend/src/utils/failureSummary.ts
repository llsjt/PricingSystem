export interface FailureSummarySource {
  thinking?: unknown
  outputSummary?: unknown
  thoughtContent?: unknown
  suggestion?: unknown
}

const normalizeText = (value: unknown) => String(value ?? '').trim()

const detectFailureSummary = (text: string) => {
  const normalized = text.toLowerCase()
  if (
    normalized.includes('timeout')
    || normalized.includes('timed out')
    || normalized.includes('time out')
    || normalized.includes('readtimeout')
    || normalized.includes('connecttimeout')
  ) {
    return 'LLM 调用超时'
  }

  if (
    normalized.includes('json')
    || normalized.includes('parse')
    || normalized.includes('decode')
    || normalized.includes('expecting value')
    || normalized.includes('invalid control character')
  ) {
    return '输出解析失败'
  }

  return text
}

const looksLikePromptLeak = (text: string) => (
  text.includes('你正在为商品')
  || text.includes('制定定价策略')
  || text.includes('请基于以上数据分析')
  || text.includes('Task `')
)

export const getFailureSummary = (
  source?: FailureSummarySource | null,
  fallback = '任务执行失败'
) => {
  const suggestion = source?.suggestion
  if (suggestion && typeof suggestion === 'object') {
    const message = normalizeText((suggestion as Record<string, unknown>).message)
    if (message) return detectFailureSummary(message)
  }

  const rawText = normalizeText(source?.thinking)
    || normalizeText(source?.outputSummary)
    || normalizeText(source?.thoughtContent)

  if (!rawText) return fallback
  if (looksLikePromptLeak(rawText)) return fallback
  return detectFailureSummary(rawText)
}

export interface FailureSummarySource {
  thinking?: unknown
  outputSummary?: unknown
  thoughtContent?: unknown
  suggestion?: unknown
}

const normalizeText = (value: unknown) => String(value ?? '').trim()
const containsChinese = (value: string) => /[\u3400-\u9fff]/u.test(value)

const GENERIC_ENGLISH_FAILURE_PATTERNS = [
  /\bagent execution failed\b/i,
  /\btask failed\b/i,
  /\brequest failed\b/i,
  /\binternal server error\b/i,
  /\bbad request\b/i,
  /\bunauthorized\b/i,
  /\bforbidden\b/i,
  /\bnot found\b/i,
  /\bprovider returned invalid competitor result\b/i,
  /\bcrewai\b.*\bfailed\b/i
] as const

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
    if (message) {
      const detected = detectFailureSummary(message)
      if (detected !== message) return detected
      if (!containsChinese(message) && GENERIC_ENGLISH_FAILURE_PATTERNS.some((pattern) => pattern.test(message))) {
        return fallback
      }
      return message
    }
  }

  const rawText = normalizeText(source?.thinking)
    || normalizeText(source?.outputSummary)
    || normalizeText(source?.thoughtContent)

  if (!rawText) return fallback
  if (looksLikePromptLeak(rawText)) return fallback
  const detected = detectFailureSummary(rawText)
  if (detected !== rawText) return detected
  if (!containsChinese(rawText) && GENERIC_ENGLISH_FAILURE_PATTERNS.some((pattern) => pattern.test(rawText))) {
    return fallback
  }
  return rawText
}

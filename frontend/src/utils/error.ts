/**
 * 错误信息清洗工具，把接口和运行时异常整理成适合界面提示的文本。
 */

const TECHNICAL_MESSAGE_PATTERNS = [
  /\b(invalid username or password|network error|failed to fetch|stream failed|request failed|internal server error|unauthorized|forbidden|bad request|not found)\b/i,
  /\b(timeout of \d+ms exceeded|read timed out|timed out|connection refused|socket hang up|econnreset|econnrefused|enotfound|etimedout)\b/i,
  /\b(typeerror|referenceerror|syntaxerror|rangeerror|axioserror|fetcherror|nullpointerexception|illegalargumentexception|sqlsyntaxerrorexception|exception)\b/i,
  /\b(traceback|stack trace|sqlstate)\b/i,
  /(^|\n)\s*at\s+\S+/,
  /\b(?:java|org|com)\.[\w$.]+(?::|\b)/i
] as const

const normalizeMessage = (value: unknown) => {
  if (typeof value !== 'string') {
    return ''
  }

  const normalized = value.replace(/\s+/g, ' ').trim()
  if (!normalized || ['null', 'undefined'].includes(normalized.toLowerCase())) {
    return ''
  }

  return normalized
}

const containsChinese = (value: string) => /[\u3400-\u9fff]/u.test(value)

const looksLikeStructuredPayload = (value: string) => {
  const trimmed = value.trim()
  return /^(?:\{|\[)/.test(trimmed) || /^<!doctype html/i.test(trimmed) || /^<html/i.test(trimmed)
}

const looksLikeTechnicalMessage = (value: string) =>
  value.includes('�') ||
  looksLikeStructuredPayload(value) ||
  TECHNICAL_MESSAGE_PATTERNS.some((pattern) => pattern.test(value))

export const toUserFacingErrorMessage = (value: unknown, fallback: string) => {
  const normalized = normalizeMessage(value)
  if (!normalized) {
    return fallback
  }

  if (looksLikeTechnicalMessage(normalized)) {
    return fallback
  }

  if (!containsChinese(normalized)) {
    return fallback
  }

  return normalized
}

export const sanitizeErrorMessage = (value: unknown, fallback: string) =>
  toUserFacingErrorMessage(value, fallback)

const parseBlobErrorMessage = async (raw: Blob, fallback: string) => {
  try {
    const text = await raw.text()
    const parsed = JSON.parse(text)
    return toUserFacingErrorMessage(parsed?.message, toUserFacingErrorMessage(parsed?.error, fallback))
  } catch {
    return fallback
  }
}

const resolveTransportFallbackMessage = (error: any, fallback: string) => {
  const message = normalizeMessage(error?.message)
  const code = String(error?.code || '').toUpperCase()

  if (code === 'ECONNABORTED' || /\btimeout\b|timed out/i.test(message)) {
    return '请求超时，请稍后重试'
  }

  if (!error?.response) {
    return '网络连接失败，请检查网络后重试'
  }

  return fallback
}

export const resolveRequestErrorMessage = async (error: unknown, fallback = '请求失败，请稍后重试') => {
  const responseData = (error as any)?.response?.data
  if (responseData instanceof Blob) {
    return parseBlobErrorMessage(responseData, fallback)
  }

  const responseMessage = toUserFacingErrorMessage(
    responseData?.message,
    toUserFacingErrorMessage(responseData?.error, '')
  )
  if (responseMessage) {
    return responseMessage
  }

  const directMessage = toUserFacingErrorMessage((error as any)?.message, '')
  if (directMessage) {
    return directMessage
  }

  return resolveTransportFallbackMessage(error, fallback)
}

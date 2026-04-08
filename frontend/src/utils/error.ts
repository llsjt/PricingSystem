export const sanitizeErrorMessage = (value: unknown, fallback: string) => {
  if (typeof value !== 'string') {
    return fallback
  }

  const normalized = value.trim()
  if (!normalized || ['null', 'undefined'].includes(normalized.toLowerCase())) {
    return fallback
  }

  return normalized
}

const parseBlobErrorMessage = async (raw: Blob, fallback: string) => {
  try {
    const text = await raw.text()
    const parsed = JSON.parse(text)
    return sanitizeErrorMessage(parsed?.message, sanitizeErrorMessage(parsed?.error, fallback))
  } catch {
    return fallback
  }
}

export const resolveRequestErrorMessage = async (error: unknown, fallback = '网络异常') => {
  const responseData = (error as any)?.response?.data
  if (responseData instanceof Blob) {
    return parseBlobErrorMessage(responseData, fallback)
  }

  return sanitizeErrorMessage(responseData?.message, sanitizeErrorMessage((error as any)?.message, fallback))
}

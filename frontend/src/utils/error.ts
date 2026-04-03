const parseBlobErrorMessage = async (raw: Blob, fallback: string) => {
  try {
    const text = await raw.text()
    const parsed = JSON.parse(text)
    return parsed?.message || parsed?.error || fallback
  } catch {
    return fallback
  }
}

export const resolveRequestErrorMessage = async (error: unknown, fallback = '网络异常') => {
  const responseData = (error as any)?.response?.data
  if (responseData instanceof Blob) {
    return parseBlobErrorMessage(responseData, fallback)
  }

  return responseData?.message || (error as any)?.message || fallback
}

import type { LlmConfigResponse, LlmConfigVO } from '../api/llmConfig'

export const extractLlmConfig = (response?: LlmConfigResponse | null): LlmConfigVO | null => {
  if (!response) {
    return null
  }

  return response.data || null
}

export const hasConfiguredLlmApiKey = (response?: LlmConfigResponse | null) =>
  Boolean(extractLlmConfig(response)?.hasApiKey)

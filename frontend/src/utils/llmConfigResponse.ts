/**
 * 大模型配置响应处理工具，负责从接口数据中判断用户是否已完成配置。
 */

import type { LlmConfigResponse, LlmConfigVO } from '../api/llmConfig'

export const extractLlmConfig = (response?: LlmConfigResponse | null): LlmConfigVO | null => {
  if (!response) {
    return null
  }

  return response.data || null
}

export const hasConfiguredLlmApiKey = (response?: LlmConfigResponse | null) =>
  Boolean(extractLlmConfig(response)?.hasApiKey)

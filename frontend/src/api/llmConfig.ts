import request, { type ApiResponse } from './request'

export interface LlmConfigPayload {
  apiKey: string
  baseUrl: string
  model: string
}

export interface LlmConfigVO {
  baseUrl: string
  model: string
  hasApiKey: boolean
  apiKeyPreview: string
}

export type LlmConfigResponse = ApiResponse<LlmConfigVO | null>

export const getLlmConfig = () => request.get<LlmConfigResponse>('/user/llm-config')

export const saveLlmConfig = (data: LlmConfigPayload) => request.put<ApiResponse<null>>('/user/llm-config', data)

export const deleteLlmConfig = () => request.delete<ApiResponse<null>>('/user/llm-config')

export const verifyLlmConfig = (data: LlmConfigPayload) => request.post<ApiResponse<string>>('/user/llm-config/verify', data)

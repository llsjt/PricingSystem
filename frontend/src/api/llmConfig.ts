import request from './request'

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

export const getLlmConfig = () => request.get<LlmConfigVO>('/user/llm-config')

export const saveLlmConfig = (data: LlmConfigPayload) => request.put('/user/llm-config', data)

export const deleteLlmConfig = () => request.delete('/user/llm-config')

export const verifyLlmConfig = (data: LlmConfigPayload) => request.post('/user/llm-config/verify', data)

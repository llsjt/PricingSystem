import test from 'node:test'
import assert from 'node:assert/strict'

import { extractLlmConfig, hasConfiguredLlmApiKey } from '../src/utils/llmConfigResponse.ts'

test('extractLlmConfig returns config payload when response contains data', () => {
  const response = {
    code: 200,
    data: {
      baseUrl: 'https://example.test/v1',
      model: 'qwen-plus',
      hasApiKey: true,
      apiKeyPreview: 'sk-****1234'
    }
  }

  assert.deepEqual(extractLlmConfig(response), response.data)
})

test('extractLlmConfig returns null when response data is null', () => {
  assert.equal(extractLlmConfig({ code: 200, data: null }), null)
})

test('hasConfiguredLlmApiKey returns false when api key is not configured', () => {
  const response = {
    code: 200,
    data: {
      baseUrl: 'https://example.test/v1',
      model: 'qwen-plus',
      hasApiKey: false,
      apiKeyPreview: ''
    }
  }

  assert.equal(hasConfiguredLlmApiKey(response), false)
})

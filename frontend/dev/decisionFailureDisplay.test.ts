import test from 'node:test'
import assert from 'node:assert/strict'

import { getFailureSummary } from '../src/utils/failureSummary.ts'

test('getFailureSummary prefers the concise backend message for failed cards', () => {
  const summary = getFailureSummary({
    thinking: 'Agent 执行失败: Task `你正在为商品...` failed',
    suggestion: { error: true, message: 'LLM 调用超时' }
  })

  assert.equal(summary, 'LLM 调用超时')
})

test('getFailureSummary falls back to a generic failure message when details are missing', () => {
  const summary = getFailureSummary({
    thinking: '',
    suggestion: {}
  })

  assert.equal(summary, '任务执行失败')
})

test('getFailureSummary hides prompt-like raw task text from historical failed cards', () => {
  const summary = getFailureSummary({
    thinking: 'Agent 执行失败: Task `你正在为商品 [凉感阔腿裤] 制定定价策略` failed'
  })

  assert.equal(summary, '任务执行失败')
})

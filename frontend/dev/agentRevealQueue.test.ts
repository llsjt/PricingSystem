import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createRevealQueueState,
  enqueueReveal,
  finishReveal,
  isActiveReveal,
  queueRevealCardRequest
} from '../src/utils/agentRevealQueue.ts'

const agentOrder = ['DATA_ANALYSIS', 'MARKET_INTEL', 'RISK_CONTROL', 'MANAGER_COORDINATOR'] as const

test('reveals one agent at a time and starts the next only after the active agent finishes', () => {
  const state = createRevealQueueState<string>()

  assert.equal(enqueueReveal(state, 'MARKET_INTEL', agentOrder), 'MARKET_INTEL')
  assert.equal(isActiveReveal(state, 'MARKET_INTEL'), true)

  assert.equal(enqueueReveal(state, 'RISK_CONTROL', agentOrder), 'MARKET_INTEL')
  assert.deepEqual(state.queue, ['RISK_CONTROL'])

  assert.equal(finishReveal(state, 'MARKET_INTEL'), 'RISK_CONTROL')
  assert.equal(isActiveReveal(state, 'RISK_CONTROL'), true)

  assert.equal(finishReveal(state, 'RISK_CONTROL'), null)
  assert.equal(state.active, null)
})

test('keeps queued agent cards in configured display order even if events arrive close together', () => {
  const state = createRevealQueueState<string>()

  enqueueReveal(state, 'MARKET_INTEL', agentOrder)
  enqueueReveal(state, 'MANAGER_COORDINATOR', agentOrder)
  enqueueReveal(state, 'RISK_CONTROL', agentOrder)

  assert.deepEqual(state.queue, ['RISK_CONTROL', 'MANAGER_COORDINATOR'])
  assert.equal(finishReveal(state, 'MARKET_INTEL'), 'RISK_CONTROL')
  assert.equal(finishReveal(state, 'RISK_CONTROL'), 'MANAGER_COORDINATOR')
})

test('ignores duplicate reveal requests for the active or queued agent', () => {
  const state = createRevealQueueState<string>()

  enqueueReveal(state, 'DATA_ANALYSIS', agentOrder)
  enqueueReveal(state, 'DATA_ANALYSIS', agentOrder)
  enqueueReveal(state, 'MARKET_INTEL', agentOrder)
  enqueueReveal(state, 'MARKET_INTEL', agentOrder)

  assert.equal(state.active, 'DATA_ANALYSIS')
  assert.deepEqual(state.queue, ['MARKET_INTEL'])
})

test('replaces the active agent payload instead of dropping the later update', () => {
  const state = createRevealQueueState<string>()
  const pending: Partial<Record<string, { card: string; stage: string }>> = {}

  assert.equal(
    queueRevealCardRequest(state, pending, 'MARKET_INTEL', { card: 'old', stage: 'completed' }, agentOrder),
    'activate'
  )
  assert.equal(
    queueRevealCardRequest(state, pending, 'MARKET_INTEL', { card: 'new', stage: 'failed' }, agentOrder),
    'replace-active'
  )

  assert.equal(state.active, 'MARKET_INTEL')
  assert.deepEqual(state.queue, [])
  assert.deepEqual(pending.MARKET_INTEL, { card: 'new', stage: 'failed' })
})

test('replaces the queued agent payload without duplicating queue order', () => {
  const state = createRevealQueueState<string>()
  const pending: Partial<Record<string, { card: string; stage: string }>> = {}

  assert.equal(
    queueRevealCardRequest(state, pending, 'DATA_ANALYSIS', { card: 'data', stage: 'completed' }, agentOrder),
    'activate'
  )
  assert.equal(
    queueRevealCardRequest(state, pending, 'MARKET_INTEL', { card: 'old', stage: 'completed' }, agentOrder),
    'queued'
  )
  assert.equal(
    queueRevealCardRequest(state, pending, 'MARKET_INTEL', { card: 'new', stage: 'completed' }, agentOrder),
    'replace-queued'
  )

  assert.equal(state.active, 'DATA_ANALYSIS')
  assert.deepEqual(state.queue, ['MARKET_INTEL'])
  assert.deepEqual(pending.MARKET_INTEL, { card: 'new', stage: 'completed' })
})

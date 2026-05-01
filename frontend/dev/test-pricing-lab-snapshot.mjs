import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { build } from 'esbuild'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const outdir = join(root, 'node_modules', '.cache', 'pricing-lab-snapshot-test')
const outfile = join(outdir, 'pricingLabSnapshot.mjs')

await mkdir(outdir, { recursive: true })
await build({
  entryPoints: [join(root, 'src', 'utils', 'pricingLabSnapshot.ts')],
  outfile,
  bundle: true,
  format: 'esm',
  platform: 'node',
  logLevel: 'silent'
})

const {
  buildSnapshotAgentCards,
  applySnapshotCardsPreservingTerminalState
} = await import(`${pathToFileURL(outfile).href}?${Date.now()}`)

const singleCompleted = buildSnapshotAgentCards([
  {
    id: 10,
    agentCode: 'MARKET_INTEL',
    agentName: '市场情报智能体',
    displayOrder: 2,
    stage: 'completed',
    thinking: '市场价带已完成',
    evidence: [{ label: '竞品', value: '8 个有效样本' }],
    suggestion: { recommendedPrice: 88.6 },
    createdAt: '2026-05-01T00:00:00Z'
  }
])

assert.equal(singleCompleted.runAttempt, null)
assert.equal(singleCompleted.resolvedRunAttempt, null)
assert.equal(singleCompleted.hasExplicitRunAttempt, false)
assert.deepEqual(singleCompleted.missingAgentCodes, [
  'DATA_ANALYSIS',
  'RISK_CONTROL',
  'MANAGER_COORDINATOR'
])
assert.deepEqual(singleCompleted.cards.map((card) => card.code), ['MARKET_INTEL'])
assert.equal(singleCompleted.cards[0].stage, 'completed')
assert.equal(singleCompleted.cards[0].card?.thinking, '市场价带已完成')
assert.equal(singleCompleted.cards[0].card?.suggestion.recommendedPrice, 88.6)

const runningOnly = buildSnapshotAgentCards([
  {
    id: 11,
    agentCode: 'DATA_ANALYSIS',
    agentName: '数据分析智能体',
    displayOrder: 1,
    stage: 'running',
    createdAt: '2026-05-01T00:00:02Z'
  }
])

assert.deepEqual(runningOnly.cards.map((card) => [card.code, card.stage, card.card]), [
  ['DATA_ANALYSIS', 'running', null]
])

const latestAttempt = buildSnapshotAgentCards([
  {
    id: 1,
    agentCode: 'DATA_ANALYSIS',
    displayOrder: 1,
    stage: 'completed',
    runAttempt: 0,
    thinking: '旧轮次',
    suggestion: {},
    createdAt: '2026-05-01T00:00:00Z'
  },
  {
    id: 2,
    agentCode: 'DATA_ANALYSIS',
    displayOrder: 1,
    stage: 'running',
    runAttempt: 1,
    createdAt: '2026-05-01T00:01:00Z'
  }
])

assert.equal(latestAttempt.runAttempt, 1)
assert.equal(latestAttempt.resolvedRunAttempt, 1)
assert.equal(latestAttempt.hasExplicitRunAttempt, true)
assert.deepEqual(latestAttempt.cards.map((card) => [card.code, card.stage]), [
  ['DATA_ANALYSIS', 'running']
])

const replayedLog = buildSnapshotAgentCards([
  {
    id: 21,
    agentCode: 'MANAGER_COORDINATOR',
    displayOrder: 4,
    stage: 'completed',
    replayed: true,
    source: {
      logId: 8,
      executionId: 'exec-42',
      runAttempt: 3
    },
    thinking: '回放后的经理结论',
    suggestion: {
      finalPrice: 66.8
    },
    createdAt: '2026-05-01T00:02:00Z'
  }
])

assert.equal(replayedLog.cards[0].card?.replayed, true)
assert.equal(replayedLog.cards[0].card?.sourceLogId, 8)
assert.equal(replayedLog.cards[0].card?.sourceExecutionId, 'exec-42')
assert.equal(replayedLog.cards[0].card?.sourceRunAttempt, 3)

const projectedMixedTimeline = buildSnapshotAgentCards([
  {
    id: 31,
    agentCode: 'DATA_ANALYSIS',
    displayOrder: 1,
    stage: 'completed',
    runAttempt: 2,
    replayed: true,
    sourceRunAttempt: 1,
    thinking: '历史数据分析',
    suggestion: {},
    createdAt: '2026-05-01T00:03:00Z'
  },
  {
    id: 32,
    agentCode: 'MARKET_INTEL',
    displayOrder: 2,
    stage: 'completed',
    runAttempt: 2,
    replayed: true,
    sourceRunAttempt: 1,
    thinking: '历史市场分析',
    suggestion: {},
    createdAt: '2026-05-01T00:03:01Z'
  },
  {
    id: 33,
    agentCode: 'RISK_CONTROL',
    displayOrder: 3,
    stage: 'completed',
    runAttempt: 2,
    replayed: true,
    sourceRunAttempt: 1,
    thinking: '历史风控分析',
    suggestion: {},
    createdAt: '2026-05-01T00:03:02Z'
  },
  {
    id: 34,
    agentCode: 'MANAGER_COORDINATOR',
    displayOrder: 4,
    stage: 'completed',
    runAttempt: 2,
    thinking: '本轮经理仲裁',
    suggestion: {},
    createdAt: '2026-05-01T00:03:03Z'
  }
])

assert.deepEqual(
  projectedMixedTimeline.cards.map((card) => [card.code, card.card?.replayed === true, card.card?.sourceRunAttempt ?? null]),
  [
    ['DATA_ANALYSIS', true, 1],
    ['MARKET_INTEL', true, 1],
    ['RISK_CONTROL', true, 1],
    ['MANAGER_COORDINATOR', false, null]
  ],
  'keeps Java projected replay/fresh cards together when they share the page-effective runAttempt'
)

const preservedTerminalState = applySnapshotCardsPreservingTerminalState(
  {
    DATA_ANALYSIS: {
      thinking: 'stream failed',
      evidence: [],
      suggestion: { error: true, message: '[DATA_ANALYSIS] 输出结构校验失败' },
      agentOpinion: null,
      reasonWhy: null,
      __stage: 'failed'
    },
    MARKET_INTEL: {
      thinking: 'stream success',
      evidence: [{ label: '竞品', value: 8 }],
      suggestion: { recommendedPrice: 290 },
      agentOpinion: null,
      reasonWhy: null,
      __stage: 'completed'
    },
    RISK_CONTROL: null,
    MANAGER_COORDINATOR: null
  },
  buildSnapshotAgentCards([
    {
      id: 41,
      agentCode: 'DATA_ANALYSIS',
      displayOrder: 1,
      stage: 'failed',
      thinking: '[DATA_ANALYSIS] 输出结构校验失败',
      suggestion: { error: true, message: '[DATA_ANALYSIS] 输出结构校验失败' },
      createdAt: '2026-05-01T00:05:00Z'
    },
    {
      id: 42,
      agentCode: 'MARKET_INTEL',
      displayOrder: 2,
      stage: 'running',
      createdAt: '2026-05-01T00:05:01Z'
    }
  ])
)

assert.equal(preservedTerminalState.DATA_ANALYSIS?.__stage, 'failed')
assert.equal(preservedTerminalState.MARKET_INTEL?.__stage, 'completed')
assert.equal(preservedTerminalState.MARKET_INTEL?.suggestion.recommendedPrice, 290)
assert.equal(preservedTerminalState.RISK_CONTROL, null)
assert.equal(preservedTerminalState.MANAGER_COORDINATOR, null)

console.log('pricing lab snapshot tests passed')

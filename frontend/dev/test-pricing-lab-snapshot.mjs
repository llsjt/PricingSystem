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

const { buildSnapshotAgentCards } = await import(`${pathToFileURL(outfile).href}?${Date.now()}`)

const singleCompleted = buildSnapshotAgentCards([
  {
    id: 10,
    agentCode: 'MARKET_INTEL',
    agentName: '市场情报智能体',
    displayOrder: 2,
    stage: 'completed',
    thinking: '市场价带已完成',
    evidence: [{ label: '竞品', value: '8个有效样本' }],
    suggestion: { recommendedPrice: 88.6 },
    createdAt: '2026-05-01T00:00:00Z'
  }
])

assert.equal(singleCompleted.runAttempt, null)
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
assert.deepEqual(latestAttempt.cards.map((card) => [card.code, card.stage]), [
  ['DATA_ANALYSIS', 'running']
])

console.log('pricing lab snapshot tests passed')

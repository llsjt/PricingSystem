import assert from 'node:assert/strict'
import { mkdir, readFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { build } from 'esbuild'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const outdir = join(root, 'node_modules', '.cache', 'agent-timeline-test')
const outfile = join(outdir, 'agentTimeline.mjs')
const refreshOutfile = join(outdir, 'revealRefresh.mjs')

await mkdir(outdir, { recursive: true })
await build({
  entryPoints: [join(root, 'src', 'utils', 'agentTimeline.ts')],
  outfile,
  bundle: true,
  format: 'esm',
  platform: 'node',
  logLevel: 'silent'
})
await build({
  entryPoints: [join(root, 'src', 'utils', 'revealRefresh.ts')],
  outfile: refreshOutfile,
  bundle: true,
  format: 'esm',
  platform: 'node',
  logLevel: 'silent'
})

const { buildVisibleAgentTimeline, filterLatestAgentRunRound } = await import(`${pathToFileURL(outfile).href}?${Date.now()}`)
const { shouldKeepRevealEnabledAfterRefresh } = await import(`${pathToFileURL(refreshOutfile).href}?${Date.now()}`)

const agents = [
  { code: 'DATA_ANALYSIS', name: '数据分析Agent', order: 1 },
  { code: 'MARKET_INTEL', name: '市场情报Agent', order: 2 },
  { code: 'RISK_CONTROL', name: '风险控制Agent', order: 3 },
  { code: 'MANAGER_COORDINATOR', name: '经理协调Agent', order: 4 }
]

assert.deepEqual(
  buildVisibleAgentTimeline(agents, {
    DATA_ANALYSIS: null,
    MARKET_INTEL: null,
    RISK_CONTROL: null,
    MANAGER_COORDINATOR: null
  }).map((agent) => agent.code),
  [],
  'hides all agents before any stream or snapshot card exists'
)

assert.deepEqual(
  buildVisibleAgentTimeline(agents, {
    DATA_ANALYSIS: { __stage: 'completed' },
    MARKET_INTEL: { __stage: 'running' },
    RISK_CONTROL: null,
    MANAGER_COORDINATOR: undefined
  }).map((agent) => agent.code),
  ['DATA_ANALYSIS', 'MARKET_INTEL'],
  'shows only agents that have appeared and preserves configured order'
)

assert.deepEqual(
  buildVisibleAgentTimeline(agents, {
    MARKET_INTEL: { __stage: 'completed' },
    UNKNOWN_AGENT: { __stage: 'running' }
  }).map((agent) => agent.code),
  ['MARKET_INTEL'],
  'ignores unknown cards and does not create duplicate display items'
)

assert.deepEqual(
  filterLatestAgentRunRound([
    { id: 1, agentCode: 'DATA_ANALYSIS', displayOrder: 1, stage: 'completed', runAttempt: 0 },
    { id: 2, agentCode: 'MARKET_INTEL', displayOrder: 2, stage: 'failed', runAttempt: 0 },
    { id: 3, agentCode: 'DATA_ANALYSIS', displayOrder: 1, stage: 'running', runAttempt: 1 },
    { id: 4, agentCode: 'DATA_ANALYSIS', displayOrder: 1, stage: 'failed', runAttempt: 1 }
  ]).map((log) => log.id),
  [3, 4],
  'keeps only logs from the latest retry attempt'
)

assert.deepEqual(
  filterLatestAgentRunRound([
    { id: 1, agentCode: 'DATA_ANALYSIS', displayOrder: 1, stage: 'completed' },
    { id: 2, agentCode: 'MARKET_INTEL', displayOrder: 2, stage: 'running' }
  ]).map((log) => log.id),
  [1, 2],
  'keeps legacy logs when runAttempt is absent'
)

assert.deepEqual(
  filterLatestAgentRunRound([
    { id: 1, agentCode: 'DATA_ANALYSIS', displayOrder: 1, stage: 'running', runAttempt: 0 },
    { id: 2, agentCode: 'DATA_ANALYSIS', displayOrder: 1, stage: 'completed', runAttempt: 0 },
    { id: 3, agentCode: 'MARKET_INTEL', displayOrder: 2, stage: 'running', runAttempt: 0 },
    { id: 4, agentCode: 'MARKET_INTEL', displayOrder: 2, stage: 'failed', runAttempt: 0 },
    { id: 5, agentCode: 'DATA_ANALYSIS', displayOrder: 1, stage: 'running', runAttempt: 0 },
    { id: 6, agentCode: 'DATA_ANALYSIS', displayOrder: 1, stage: 'failed', runAttempt: 0 }
  ]).map((log) => log.id),
  [5, 6],
  'infers latest retry round from repeated first-agent running logs when runAttempt was not incremented'
)

assert.equal(shouldKeepRevealEnabledAfterRefresh('RUNNING', true), true, 'keeps reveal mode while task is running')
assert.equal(shouldKeepRevealEnabledAfterRefresh('QUEUED', true), true, 'keeps reveal mode while task is queued')
assert.equal(shouldKeepRevealEnabledAfterRefresh('COMPLETED', true), false, 'turns reveal mode off when task is completed')
assert.equal(shouldKeepRevealEnabledAfterRefresh('RUNNING', false), false, 'does not re-enable reveal mode after user skipped animation')

const pricingLabSource = await readFile(join(root, 'src', 'views', 'PricingLab.vue'), 'utf8')
assert.match(pricingLabSource, /decision-chat-panel/, 'decision stage uses AI chat panel wrapper')
assert.doesNotMatch(pricingLabSource, /is-manager|price-highlight-manager/, 'manager agent uses the same visual treatment as other agents')
assert.doesNotMatch(pricingLabSource, /agent-box\[data-agent=/, 'agent cards do not use per-agent large color overrides')

console.log('agent timeline tests passed')

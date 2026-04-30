import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { build } from 'esbuild'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const outdir = join(root, 'node_modules', '.cache', 'pricing-decision-view-test')
const outfile = join(outdir, 'pricingDecisionView.mjs')

await mkdir(outdir, { recursive: true })
await build({
  entryPoints: [join(root, 'src', 'utils', 'pricingDecisionView.ts')],
  outfile,
  bundle: true,
  format: 'esm',
  platform: 'node',
  logLevel: 'silent'
})

const {
  ANALYSIS_AGENT_CODES,
  MANAGER_AGENT_CODE,
  buildDecisionStatusOverview
} = await import(`${pathToFileURL(outfile).href}?${Date.now()}`)

const emptyCards = () => ({
  DATA_ANALYSIS: null,
  MARKET_INTEL: null,
  RISK_CONTROL: null,
  MANAGER_COORDINATOR: null
})

assert.deepEqual(
  ANALYSIS_AGENT_CODES,
  ['DATA_ANALYSIS', 'MARKET_INTEL', 'RISK_CONTROL'],
  'keeps the three analysis agents in a fixed left-to-right order'
)

assert.equal(
  MANAGER_AGENT_CODE,
  'MANAGER_COORDINATOR',
  'exposes the manager lane code for the full-width arbitration card'
)

const runningCards = emptyCards()
runningCards.DATA_ANALYSIS = { __stage: 'running' }
runningCards.MARKET_INTEL = { __stage: 'running' }
runningCards.RISK_CONTROL = { __stage: 'running' }
assert.deepEqual(
  buildDecisionStatusOverview(runningCards, null),
  {
    analysisCompletedCount: 0,
    analysisRunningCount: 3,
    analysisStatusText: '0/3 已完成',
    managerStatusText: '等待经理仲裁',
    primaryStatusText: '三个分析并行中',
    finalPrice: null,
    finalPriceLabel: '最终建议价'
  },
  'summarizes the top status area when the three analysis cards are running in parallel'
)

const waitingManagerCards = emptyCards()
waitingManagerCards.DATA_ANALYSIS = { __stage: 'completed' }
waitingManagerCards.MARKET_INTEL = { __stage: 'completed' }
waitingManagerCards.RISK_CONTROL = { __stage: 'completed' }
assert.deepEqual(
  buildDecisionStatusOverview(waitingManagerCards, null),
  {
    analysisCompletedCount: 3,
    analysisRunningCount: 0,
    analysisStatusText: '3/3 已完成',
    managerStatusText: '等待经理仲裁',
    primaryStatusText: '3/3 完成，等待经理仲裁',
    finalPrice: null,
    finalPriceLabel: '最终建议价'
  },
  'shows the handoff state after all three analysis agents finish and before the manager completes'
)

const managerDoneCards = emptyCards()
managerDoneCards.DATA_ANALYSIS = { __stage: 'completed' }
managerDoneCards.MARKET_INTEL = { __stage: 'completed' }
managerDoneCards.RISK_CONTROL = { __stage: 'completed' }
managerDoneCards.MANAGER_COORDINATOR = { __stage: 'completed' }
assert.deepEqual(
  buildDecisionStatusOverview(managerDoneCards, 29.9),
  {
    analysisCompletedCount: 3,
    analysisRunningCount: 0,
    analysisStatusText: '3/3 已完成',
    managerStatusText: 'Manager 已完成',
    primaryStatusText: 'Manager 已完成',
    finalPrice: 29.9,
    finalPriceLabel: '最终建议价'
  },
  'surfaces the manager completion state and final suggested price once arbitration is done'
)

console.log('pricing decision view tests passed')

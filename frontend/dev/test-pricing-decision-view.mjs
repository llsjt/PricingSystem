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
    isTimelineInconsistent: false,
    canShowManagerCompleted: false,
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
    isTimelineInconsistent: false,
    canShowManagerCompleted: false,
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
    isTimelineInconsistent: false,
    canShowManagerCompleted: true,
    analysisStatusText: '3/3 已完成',
    managerStatusText: '经理已完成',
    primaryStatusText: '经理已完成',
    finalPrice: 29.9,
    finalPriceLabel: '最终建议价'
  },
  'surfaces the manager completion state and final suggested price once arbitration is done'
)

const runningManagerCards = emptyCards()
runningManagerCards.DATA_ANALYSIS = { __stage: 'completed' }
runningManagerCards.MARKET_INTEL = { __stage: 'completed' }
runningManagerCards.RISK_CONTROL = { __stage: 'completed' }
runningManagerCards.MANAGER_COORDINATOR = { __stage: 'running' }
const runningManagerOverview = buildDecisionStatusOverview(runningManagerCards, null)
assert.equal(runningManagerOverview.managerStatusText, '经理仲裁中', 'uses Chinese copy while manager arbitration is running')
assert.equal(runningManagerOverview.primaryStatusText, '经理仲裁中', 'uses Chinese primary copy while manager arbitration is running')
assert.doesNotMatch(
  `${runningManagerOverview.managerStatusText}${runningManagerOverview.primaryStatusText}`,
  /Manager/,
  'does not expose English manager wording in running state'
)

const managerDoneOverview = buildDecisionStatusOverview(managerDoneCards, 29.9)
assert.doesNotMatch(
  `${managerDoneOverview.managerStatusText}${managerDoneOverview.primaryStatusText}`,
  /Manager/,
  'does not expose English manager wording in completed state'
)

const managerAheadCards = emptyCards()
managerAheadCards.DATA_ANALYSIS = { __stage: 'completed' }
managerAheadCards.MANAGER_COORDINATOR = { __stage: 'completed' }
assert.deepEqual(
  buildDecisionStatusOverview(managerAheadCards, 31.2),
  {
    analysisCompletedCount: 1,
    analysisRunningCount: 0,
    isTimelineInconsistent: true,
    canShowManagerCompleted: false,
    analysisStatusText: '1/3 已完成',
    managerStatusText: '等待快照对齐',
    primaryStatusText: '结果同步中',
    finalPrice: 31.2,
    finalPriceLabel: '最终建议价'
  },
  'holds manager completion copy until the snapshot catches all three analysis lanes up'
)

console.log('pricing decision view tests passed')

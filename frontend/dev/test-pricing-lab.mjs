import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { build } from 'esbuild'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const pricingLabSource = await readFile(join(root, 'src', 'views', 'PricingLab.vue'), 'utf8')

assert.match(pricingLabSource, /decision-overview-grid/, 'renders a dedicated top overview grid for decision progress')
assert.match(pricingLabSource, /parallel-analysis-panel/, 'splits the analysis agents into a dedicated parallel analysis area')
assert.match(pricingLabSource, /manager-arbitration-panel/, 'renders a separate full-width manager arbitration area')
assert.match(pricingLabSource, /数据、市场、风控三个分析智能体会按固定顺序纵向展示/, 'describes the parallel analysis area as a vertical sequence')
assert.match(pricingLabSource, /\.parallel-analysis-grid\{grid-template-columns:1fr\}/, 'stacks parallel analysis cards vertically')
assert.doesNotMatch(pricingLabSource, /@media \(max-width:1100px\)\{[^}]*\.parallel-analysis-grid[^}]*grid-template-columns:repeat\(2/, 'does not restore a two-column layout for parallel analysis on tablet widths')
assert.match(pricingLabSource, /disagreement-and-arbitration/, 'shows a dedicated disagreement and arbitration module when manager arbitration data exists')
assert.match(pricingLabSource, /arbitration-head/, 'renders a scannable arbitration header')
assert.match(pricingLabSource, /consensus-meter/, 'renders consensus score as a compact meter instead of a list row')
assert.match(pricingLabSource, /arbitration-summary-grid/, 'separates arbitration conclusion and reason into summary blocks')
assert.match(pricingLabSource, /arbitration-detail-grid/, 'groups disagreement focus and opinion handling into clear columns')
assert.match(pricingLabSource, /arbitration-decision-strip/, 'renders the adopted option, price, and strategy as a final decision strip')
assert.match(pricingLabSource, /import \{[^}]*watch[^}]*\} from 'vue'/s, 'uses a route watcher to handle cached pricing lab navigation')
assert.match(pricingLabSource, /watch\(\s*\(\) => \[\s*route\.path[\s\S]*route\.query\.productId[\s\S]*route\.query\.shopId[\s\S]*route\.query\.platform[\s\S]*route\.query\.productName[\s\S]*\][\s\S]*syncRoutePrefill/s, 're-applies product prefill when the cached lab route receives new query parameters')
assert.match(pricingLabSource, /onActivated\(\(\) => \{[\s\S]*syncRoutePrefill\(\)/, 're-applies product prefill when returning to an already-open smart pricing tab')

const match = pricingLabSource.match(
  /const coerceManagerArbitrationRecord =[\s\S]*?const extractManagerArbitrationFields =[\s\S]*?\nconst normalizeCard =/
)
assert.ok(match, 'keeps a dedicated helper for manager arbitration field extraction')

const outdir = join(root, 'node_modules', '.cache', 'pricing-lab-test')
const srcfile = join(outdir, 'extractManagerArbitrationFields.ts')
const outfile = join(outdir, 'extractManagerArbitrationFields.mjs')

await mkdir(outdir, { recursive: true })
await writeFile(
  srcfile,
  `type ManagerArbitrationItem = string | Record<string, unknown>\n` +
    `type ManagerArbitrationFields = Record<string, unknown>\n` +
    `${match[0].replace(/\nconst normalizeCard =$/, '\n')}\n` +
    `export { extractManagerArbitrationFields }\n`,
  'utf8'
)

await build({
  entryPoints: [srcfile],
  outfile,
  bundle: true,
  format: 'esm',
  platform: 'node',
  logLevel: 'silent'
})

const { extractManagerArbitrationFields } = await import(`${pathToFileURL(outfile).href}?${Date.now()}`)

assert.deepEqual(
  extractManagerArbitrationFields({
    consensusScore: 0,
    acceptedOpinions: ['root accepted'],
    selectedAgent: 'DATA_ANALYSIS',
    suggestion: {
      consensusScore: 0.82,
      acceptedOpinions: ['nested accepted'],
      rejectedOpinions: ['nested rejected'],
      selectedAgent: 'MARKET_INTEL'
    }
  }),
  {
    consensusScore: 0,
    disagreementSummary: null,
    disagreementPoints: null,
    disagreements: null,
    conflictPoints: null,
    conflicts: null,
    acceptedOpinions: ['root accepted'],
    rejectedOpinions: ['nested rejected'],
    arbitrationDecision: null,
    arbitrationSummary: null,
    arbitrationReason: null,
    decisionSummary: null,
    decisionReason: null,
    selectedAgent: 'DATA_ANALYSIS',
    selectedOption: null,
    selectedPrice: null,
    selectedStrategy: null
  },
  'prefers root arbitration fields while falling back to suggestion for missing values'
)

assert.deepEqual(
  extractManagerArbitrationFields({
    suggestion: {
      conflicts: ['legacy conflict'],
      arbitrationSummary: 'legacy summary',
      decisionReason: 'legacy reason',
      selectedOption: 'MARKET_INTEL'
    }
  }),
  {
    consensusScore: null,
    disagreementSummary: null,
    disagreementPoints: ['legacy conflict'],
    disagreements: null,
    conflictPoints: null,
    conflicts: ['legacy conflict'],
    acceptedOpinions: null,
    rejectedOpinions: null,
    arbitrationDecision: null,
    arbitrationSummary: 'legacy summary',
    arbitrationReason: null,
    decisionSummary: null,
    decisionReason: 'legacy reason',
    selectedAgent: null,
    selectedOption: 'MARKET_INTEL',
    selectedPrice: null,
    selectedStrategy: null
  },
  'reads legacy arbitration fields from nested suggestion payloads'
)

console.log('pricing lab tests passed')

import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const pricingLabSource = await readFile(join(root, 'src', 'views', 'PricingLab.vue'), 'utf8')
const pricingLabSnapshotSource = await readFile(join(root, 'src', 'utils', 'pricingLabSnapshot.ts'), 'utf8')

assert.match(pricingLabSource, /decision-overview-grid/, 'renders a dedicated top overview grid for decision progress')
assert.match(pricingLabSource, /parallel-analysis-panel/, 'splits the analysis agents into a dedicated parallel analysis area')
assert.match(pricingLabSource, /manager-arbitration-panel/, 'renders a separate manager arbitration area')
assert.match(pricingLabSource, /数据、市场、风控三个分析智能体会同时展示/, 'describes the analysis area as parallel visual lanes')
assert.doesNotMatch(pricingLabSource, /按固定顺序纵向展示/, 'does not describe the analysis area as a serial vertical sequence')
assert.match(pricingLabSource, /\.parallel-analysis-grid\{grid-template-columns:1fr\}/, 'renders analysis agents as a vertical stack')
assert.match(
  pricingLabSource,
  /const shouldAnimate = \(code: PricingAgentCode\) =>[\s\S]*analysisAgentCodeSet\.has\(code\)[\s\S]*streamArrivedCards\.has\(code\)[\s\S]*isActiveReveal\(revealQueue, code\)/,
  'allows analysis agents to animate independently while manager reveal remains queued'
)
assert.match(
  pricingLabSource,
  /if \(analysisAgentCodeSet\.has\(code\)\) \{[\s\S]*streamArrivedCards\.add\(code\)[\s\S]*beginReveal\(code\)[\s\S]*showCard\(code, card, stage\)[\s\S]*return[\s\S]*queueRevealCardRequest/,
  'bypasses the serial reveal queue for completed analysis cards'
)
assert.match(pricingLabSource, /const COMPACT_AGENT_LINE_LIMIT = 2/, 'keeps the compact agent line limit at two rows by default')
assert.match(
  pricingLabSource,
  /const compactLines = \([\s\S]*if \(lines\.length <= COMPACT_AGENT_LINE_LIMIT\) return lines[\s\S]*if \(isAgentSectionExpanded\(code, section\)\) return lines[\s\S]*return lines\.slice\(0, COMPACT_AGENT_LINE_LIMIT\)/,
  'compacts evidence and suggestion sections through a shared helper'
)
assert.match(
  pricingLabSource,
  /const visibleEvidenceLines = \(code: PricingAgentCode\) => \{[\s\S]*const lines = evidenceLines\(code\)[\s\S]*if \(shouldAnimate\(code\) && revealStages\[code\] === 'evidence'\) \{[\s\S]*return lines\.slice\(0, Math\.max\(ensureRevealLineCounts\(code\)\.evidence, 1\)\)[\s\S]*\}[\s\S]*if \(shouldAnimate\(code\) && revealStages\[code\] !== 'done'\) return lines[\s\S]*return compactLines\(lines, code, 'evidence'\)[\s\S]*\}/,
  'uses compact lines for completed evidence while keeping all revealed evidence visible until animation is done'
)
assert.match(
  pricingLabSource,
  /const visibleSuggestionLines = \(code: PricingAgentCode\) => \{[\s\S]*const lines = suggestionLines\(code\)[\s\S]*if \(shouldAnimate\(code\) && revealStages\[code\] !== 'done'\) \{[\s\S]*return lines\.slice\(0, Math\.max\(ensureRevealLineCounts\(code\)\.suggestion, 1\)\)[\s\S]*\}[\s\S]*return compactLines\(lines, code, 'suggestion'\)[\s\S]*\}/,
  'uses compact lines for completed suggestions while preserving reveal-line truncation during animation'
)
assert.match(
  pricingLabSource,
  /const canToggleEvidenceLines = \(code: PricingAgentCode\) =>[\s\S]*evidenceLines\(code\)\.length > COMPACT_AGENT_LINE_LIMIT[\s\S]*\(!shouldAnimate\(code\) \|\| revealStages\[code\] === 'done'\)/,
  'only shows the evidence toggle when more than two lines exist and animation is complete'
)
assert.match(
  pricingLabSource,
  /const canToggleSuggestionLines = \(code: PricingAgentCode\) =>[\s\S]*suggestionLines\(code\)\.length > COMPACT_AGENT_LINE_LIMIT[\s\S]*\(!shouldAnimate\(code\) \|\| revealStages\[code\] === 'done'\)/,
  'only shows the suggestion toggle when more than two lines exist and animation is complete'
)
assert.match(
  pricingLabSource,
  /const getSectionToggleText = \([\s\S]*if \(isAgentSectionExpanded\(code, section\)\) return '收起'[\s\S]*return `展开 \$\{hiddenLineCount\(total\)\} 条`/,
  'uses concise expand and collapse toggle copy'
)
assert.match(
  pricingLabSource,
  /<div v-if="canShowEvidence\(agent\.code\)" class="agent-section-head">[\s\S]*<h4>依据<\/h4>[\s\S]*<el-button[\s\S]*v-if="canToggleEvidenceLines\(agent\.code\)"[\s\S]*class="agent-section-toggle"[\s\S]*@click="toggleAgentSection\(agent\.code, 'evidence'\)"[\s\S]*getSectionToggleText\(agent\.code, 'evidence', evidenceLines\(agent\.code\)\.length\)/,
  'renders an evidence section header row with the compact toggle button wiring'
)
assert.match(
  pricingLabSource,
  /<div v-if="canShowSuggestion\(agent\.code\)" class="agent-section-head">[\s\S]*<h4>建议<\/h4>[\s\S]*<el-button[\s\S]*v-if="canToggleSuggestionLines\(agent\.code\)"[\s\S]*class="agent-section-toggle"[\s\S]*@click="toggleAgentSection\(agent\.code, 'suggestion'\)"[\s\S]*getSectionToggleText\(agent\.code, 'suggestion', suggestionLines\(agent\.code\)\.length\)/,
  'renders a suggestion section header row with the compact toggle button wiring'
)
assert.match(
  pricingLabSource,
  /const clearExpandedAgentSections = \(\) => \{[\s\S]*delete expandedAgentSections\[agent\.code\][\s\S]*\}/,
  'tracks expanded agent sections with a dedicated reset helper'
)
assert.match(
  pricingLabSource,
  /const clearRevealState = \(\) => \{[\s\S]*clearExpandedAgentSections\(\)[\s\S]*\}/,
  'clears expanded section state when reveal state resets'
)
assert.match(
  pricingLabSource,
  /const clearAgentRevealProgress = \(\) => \{[\s\S]*clearExpandedAgentSections\(\)[\s\S]*\}/,
  'clears expanded section state when switching reveal progress between attempts'
)
assert.match(
  pricingLabSource,
  /const resetState = \(\) => \{[\s\S]*clearRevealState\(\)[\s\S]*\}/,
  'resets task state through a reveal reset that also clears expanded sections'
)
assert.match(pricingLabSource, /opinion-matrix-panel/, 'renders a dedicated opinion matrix panel')
assert.match(pricingLabSource, /opinion-grid/, 'uses a grid layout for the opinion matrix')
assert.match(pricingLabSource, /opinionMatrixRows = computed/, 'derives matrix rows from reactive card state')
assert.match(
  pricingLabSource,
  /import \{[^}]*extractManagerArbitrationFields[^}]*normalizeAgentOpinion[^}]*type NormalizedAgentOpinion[^}]*\} from '\.\.\/utils\/agentOpinion'/s,
  'imports the shared agentOpinion normalizer utilities'
)
assert.match(pricingLabSource, /opinion:\s*normalizeAgentOpinion\(card\)/, 'stores normalized agent opinions on cards')
assert.match(pricingLabSource, /\.\.\.extractManagerArbitrationFields\(card\)/, 'normalizes manager arbitration fields on live cards through the shared util')
assert.match(pricingLabSnapshotSource, /\.\.\.extractManagerArbitrationFields\(log\)/, 'normalizes manager arbitration fields on snapshot logs through the shared util')
assert.match(pricingLabSnapshotSource, /agentOpinion: log\.agentOpinion \|\| null/, 'hydrates snapshot cards with raw agentOpinion payloads')
assert.match(pricingLabSource, /const runningCard = \(\): InternalAgentCardContent => \(\{[\s\S]*opinion: null[\s\S]*\.\.\.extractManagerArbitrationFields\(null\)/, 'initializes empty running cards with the shared arbitration shape')
assert.match(pricingLabSource, /<div class="opinion-grid opinion-grid-head">[\s\S]*席位[\s\S]*建议价[\s\S]*置信度\/风险[\s\S]*证据摘要[\s\S]*处理状态/s, 'renders opinion matrix headers for the unified comparison view')
assert.match(
  pricingLabSource,
  /const opinionMatrixRows = computed\(\(\) => agents\.map\(\(agent\) => \{[\s\S]*const displayStatus = getAgentDisplayStatus\(agent\.code\)[\s\S]*priceText:[\s\S]*confidenceText,[\s\S]*evidenceText,[\s\S]*stateText,[\s\S]*stage: displayStatus\.stage[\s\S]*\}\)\)/s,
  'derives opinion matrix rows from normalized opinions and per-card stage state'
)
assert.match(
  pricingLabSource,
  /const getAgentDisplayStatus[\s\S]*decisionOverview\.value\.isTimelineInconsistent[\s\S]*等待快照对齐/,
  'uses the shared decision overview to keep manager badge and matrix state aligned during inconsistent timelines'
)
assert.match(
  pricingLabSource,
  /<el-tag size="small" :type="getAgentStatusType\(agent\.code\)">\s*\{\{ getAgentStatusText\(agent\.code\) \}\}/,
  'renders agent badges through the shared status helpers'
)
assert.match(pricingLabSource, /matrix-state-chip/, 'renders matrix state chips for each seat')
assert.doesNotMatch(pricingLabSource, /const coerceManagerArbitrationRecord =/, 'does not keep local arbitration record coercion helpers')
assert.doesNotMatch(pricingLabSource, /const readManagerArbitrationField =/, 'does not keep local arbitration field readers')
assert.doesNotMatch(pricingLabSource, /const extractManagerArbitrationFields =/, 'does not keep inline arbitration extraction logic')
assert.match(pricingLabSource, /watch\(\s*\(\) => \[\s*route\.path[\s\S]*route\.query\.productId[\s\S]*route\.query\.shopId[\s\S]*route\.query\.platform[\s\S]*route\.query\.productName[\s\S]*\][\s\S]*syncRoutePrefill/s, 're-applies product prefill when the cached lab route receives new query parameters')
assert.match(pricingLabSource, /onActivated\(\(\) => \{[\s\S]*syncRoutePrefill\(\)/, 're-applies product prefill when returning to an already-open smart pricing tab')
assert.match(
  pricingLabSource,
  /const finalizeTaskFromServer = async \([\s\S]*liveRevealEnabled\.value = false[\s\S]*clearAgentRevealProgress\(\)[\s\S]*await loadSnapshot\(id, \{ applyLogs: true, mergeLogs: false \}\)[\s\S]*stopRealtime\(\)/,
  'forces a terminal snapshot reconciliation before realtime teardown'
)
assert.match(
  pricingLabSource,
  /if \(payload\.type === 'task_completed'\) \{[\s\S]*await finalizeTaskFromServer\(payload\.taskId\)/,
  'routes task_completed through the shared terminal finalizer'
)
assert.match(
  pricingLabSource,
  /if \(payload\.type === 'task_failed'\) \{[\s\S]*await finalizeTaskFromServer\(payload\.taskId\)/,
  'routes task_failed through the shared terminal finalizer'
)
assert.doesNotMatch(
  pricingLabSource,
  /task_completed[\s\S]*applyLogs: !hasRevealInProgress\(\)|task_failed[\s\S]*applyLogs: !hasRevealInProgress\(\)/,
  'does not skip terminal snapshot logs just because reveal animation is still in progress'
)
assert.match(
  pricingLabSource,
  /let snapshotLoadToken = 0/,
  'tracks a dedicated token for snapshot request ordering'
)
assert.match(
  pricingLabSource,
  /const requestToken = \+\+snapshotLoadToken[\s\S]*if \(requestToken !== snapshotLoadToken\) return/,
  'ignores stale snapshot responses that resolve after a newer request'
)
assert.match(
  pricingLabSource,
  /if \(requestToken === snapshotLoadToken\) applySnapshotComparison/,
  'applies comparison rows only for the newest snapshot response'
)

console.log('pricing lab tests passed')

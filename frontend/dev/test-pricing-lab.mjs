import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const pricingLabSource = await readFile(join(root, 'src', 'views', 'PricingLab.vue'), 'utf8')
const pricingLabSnapshotSource = await readFile(join(root, 'src', 'utils', 'pricingLabSnapshot.ts'), 'utf8')

assert.doesNotMatch(pricingLabSource, /decision-overview-grid/, 'does not render the removed top overview grid')
assert.doesNotMatch(pricingLabSource, /decision-overview-card/, 'does not render the removed top overview cards')
assert.match(pricingLabSource, /parallel-analysis-panel/, 'splits the analysis agents into a dedicated parallel analysis area')
assert.match(pricingLabSource, /manager-arbitration-panel/, 'renders a separate manager arbitration area')
assert.match(pricingLabSource, />智能决策流</, 'uses Chinese-only copy for the decision flow badge')
assert.doesNotMatch(pricingLabSource, />AI 决策流</, 'does not expose the AI abbreviation in the decision flow badge')
assert.match(pricingLabSource, /先并行回答收益、市场和风险三个商家最关心的问题/, 'describes the analysis area as merchant-focused parallel lanes')
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
assert.match(
  pricingLabSource,
  /const visibleEvidenceLines = \(code: PricingAgentCode\) => \{[\s\S]*const lines = evidenceLines\(code\)[\s\S]*if \(shouldAnimate\(code\) && revealStages\[code\] === 'evidence'\) \{[\s\S]*return lines\.slice\(0, Math\.max\(ensureRevealLineCounts\(code\)\.evidence, 1\)\)[\s\S]*\}[\s\S]*return lines[\s\S]*\}/,
  'shows all evidence lines after the reveal animation instead of compacting them'
)
assert.match(
  pricingLabSource,
  /const visibleSuggestionLines = \(code: PricingAgentCode\) => \{[\s\S]*const lines = suggestionLines\(code\)[\s\S]*if \(shouldAnimate\(code\) && revealStages\[code\] !== 'done'\) \{[\s\S]*return lines\.slice\(0, Math\.max\(ensureRevealLineCounts\(code\)\.suggestion, 1\)\)[\s\S]*\}[\s\S]*return lines[\s\S]*\}/,
  'shows all suggestion lines after the reveal animation instead of compacting them'
)
assert.doesNotMatch(pricingLabSource, /COMPACT_AGENT_LINE_LIMIT/, 'removes the compact line limit')
assert.doesNotMatch(pricingLabSource, /compactLines/, 'removes compact line slicing')
assert.doesNotMatch(pricingLabSource, /canToggleEvidenceLines/, 'removes the evidence collapse toggle guard')
assert.doesNotMatch(pricingLabSource, /canToggleSuggestionLines/, 'removes the suggestion collapse toggle guard')
assert.doesNotMatch(pricingLabSource, /getSectionToggleText/, 'removes expand/collapse toggle copy')
assert.doesNotMatch(pricingLabSource, /toggleAgentSection/, 'removes section expand/collapse click handlers')
assert.doesNotMatch(pricingLabSource, /expandedAgentSections/, 'removes expanded section state')
assert.doesNotMatch(pricingLabSource, /agent-section-toggle/, 'removes the visible expand/collapse buttons')
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
assert.match(pricingLabSource, /<div class="opinion-grid opinion-grid-head">[\s\S]*智能体[\s\S]*建议价[\s\S]*置信度[\s\S]*解决问题[\s\S]*处理状态/s, 'renders opinion matrix headers for the unified comparison view')
assert.doesNotMatch(pricingLabSource, /<span>席位<\/span>/, 'renames the opinion matrix seat column to agent')
assert.match(pricingLabSource, /name: '数据分析智能体'/, 'uses the requested data analysis agent name')
assert.match(pricingLabSource, /name: '市场情报智能体'/, 'uses the requested market intelligence agent name')
assert.match(pricingLabSource, /name: '风险控制智能体'/, 'uses the requested risk control agent name')
assert.match(pricingLabSource, /name: '经理决策智能体'/, 'uses the requested manager decision agent name')
assert.doesNotMatch(pricingLabSource, /name: '经营收益测算'|name: '竞品市场判断'|name: '利润底线校验'|name: '定价决策经理'/, 'does not keep old problem-framed labels as agent names')
assert.doesNotMatch(pricingLabSource, /置信度\/风险/, 'does not mix risk labels into the confidence column header')
assert.match(pricingLabSource, /const formatMatrixConfidencePercent = \(value: number \| null\) =>/, 'formats matrix confidence through a percentage helper')
assert.match(pricingLabSource, /const inferMatrixConfidence = \(opinion: NormalizedAgentOpinion \| null\) =>/, 'infers missing matrix confidence as a percentage value')
assert.doesNotMatch(pricingLabSource, /confidenceText[\s\S]{0,180}toNaturalChinese\(opinion\.riskLevel\)/, 'does not render risk words in the confidence column')
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
assert.match(pricingLabSource, /:disabled="starting \|\| !hasLlmConfig"/, 'disables the start button while a task request is already in flight')
assert.match(
  pricingLabSource,
  /const startTask = async \(\) => \{[\s\S]*if \(starting\.value\) return/,
  'guards startTask against duplicate clicks before async state changes settle'
)
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

import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const archiveSource = await readFile(join(root, 'src', 'views', 'Archive.vue'), 'utf8')
const archiveLogicSource = await readFile(join(root, 'src', 'composables', 'useArchivePage.ts'), 'utf8')

assert.match(archiveSource, /orderedLogCards/, 'renders pre-shaped archive log cards instead of raw log rows')
assert.match(archiveSource, /archive-agent-timeline/, 'wraps collaborative logs in an archive timeline surface')
assert.match(archiveSource, /archive-agent-avatar/, 'shows each pricing agent with a compact identity marker')
assert.match(archiveSource, /archive-agent-output-grid/, 'groups thinking, evidence, suggestion, and reason into a structured grid')
assert.match(archiveSource, /archive-suggestion-highlight/, 'highlights the primary agent price output')
assert.match(archiveSource, /archive-arbitration-panel/, 'renders manager disagreement and arbitration data in a dedicated panel')
assert.match(archiveSource, /archive-final-decision-strip/, 'surfaces the adopted agent, price, and strategy as final decision chips')
assert.match(archiveSource, /consensus-track/, 'keeps consensus score as a visual meter')
assert.match(archiveSource, /archive-evidence-board/, 'renders a decision evidence board above the timeline')
assert.match(archiveSource, /archive-matrix-grid/, 'renders a matrix summary grid for agent opinions')
assert.match(archiveSource, /archiveEvidenceBoard/, 'consumes the pre-shaped evidence board payload from the composable')
assert.doesNotMatch(archiveSource, /<article v-for="log in orderedLogs"/, 'does not render raw ordered logs directly')
assert.match(archiveSource, />意见矩阵</, 'aligns archive log summary with the smart-pricing opinion matrix')
assert.match(archiveSource, /智能体[\s\S]*建议价[\s\S]*置信度[\s\S]*解决问题[\s\S]*处理状态/, 'uses the same matrix columns as smart pricing')
assert.match(archiveSource, />商家结论</, 'renames archived thinking output to the merchant-facing conclusion')
assert.match(archiveSource, />关键依据</, 'renames archived evidence output to key evidence')
assert.match(archiveSource, />下一步建议</, 'renames archived suggestions to the smart-pricing next action wording')
assert.match(archiveSource, />为什么这样定价</, 'uses smart-pricing rationale wording for archived reasons')
assert.doesNotMatch(archiveSource, /Decision Evidence/, 'does not expose English evidence-board copy in the archive')
assert.doesNotMatch(archiveSource, />思考过程</, 'does not keep generic thinking-process wording')
assert.doesNotMatch(archiveSource, />建议原因</, 'does not keep generic suggestion-reason wording')

const outputGridRule = archiveSource.match(/\.archive-agent-output-grid\s*\{[^}]*\}/)?.[0] || ''
assert.match(outputGridRule, /grid-template-columns:\s*1fr/, 'stacks normal agent output sections vertically')
assert.doesNotMatch(outputGridRule, /repeat\(2/, 'does not render normal agent output sections side by side')

assert.match(archiveLogicSource, /getManagerArbitrationBlock/, 'reuses smart-pricing manager arbitration parsing for archive logs')
assert.match(archiveLogicSource, /orderedLogCards = computed/, 'prepares archive log cards in the composable')
assert.match(archiveLogicSource, /normalizeAgentOpinion/, 'normalizes agentOpinion payloads in one place for archive consumption')
assert.match(archiveLogicSource, /archiveEvidenceBoard = computed/, 'builds a dedicated evidence board summary for the archive drawer')
assert.doesNotMatch(archiveLogicSource, /suggestion\\.agentOpinion/, 'does not read nested suggestion.agentOpinion as a new-structure source')
assert.match(archiveLogicSource, /DATA_ANALYSIS:\s*'数据分析智能体'/, 'uses the smart-pricing data agent display name in archive logs')
assert.match(archiveLogicSource, /MARKET_INTEL:\s*'市场情报智能体'/, 'uses the smart-pricing market agent display name in archive logs')
assert.match(archiveLogicSource, /RISK_CONTROL:\s*'风险控制智能体'/, 'uses the smart-pricing risk agent display name in archive logs')
assert.match(archiveLogicSource, /MANAGER_COORDINATOR:\s*'经理决策智能体'/, 'uses the smart-pricing manager agent display name in archive logs')
assert.match(archiveLogicSource, /const matrixEvidencePreview =/, 'extracts the same merchant problem preview used by smart pricing')
assert.match(archiveLogicSource, /const formatMatrixConfidencePercent =/, 'formats archive matrix confidence as a percentage')
assert.match(archiveLogicSource, /const inferMatrixConfidence =/, 'infers archive matrix confidence when explicit confidence is absent')
assert.doesNotMatch(archiveLogicSource, /置信\s*\$\{confidenceText\}[\s\S]{0,120}风险/, 'does not mix risk wording into the archive confidence column')

console.log('archive log display tests passed')

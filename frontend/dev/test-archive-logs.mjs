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

const outputGridRule = archiveSource.match(/\.archive-agent-output-grid\s*\{[^}]*\}/)?.[0] || ''
assert.match(outputGridRule, /grid-template-columns:\s*1fr/, 'stacks normal agent output sections vertically')
assert.doesNotMatch(outputGridRule, /repeat\(2/, 'does not render normal agent output sections side by side')

assert.match(archiveLogicSource, /getManagerArbitrationBlock/, 'reuses smart-pricing manager arbitration parsing for archive logs')
assert.match(archiveLogicSource, /orderedLogCards = computed/, 'prepares archive log cards in the composable')
assert.match(archiveLogicSource, /normalizeAgentOpinion/, 'normalizes agentOpinion payloads in one place for archive consumption')
assert.match(archiveLogicSource, /archiveEvidenceBoard = computed/, 'builds a dedicated evidence board summary for the archive drawer')
assert.doesNotMatch(archiveLogicSource, /suggestion\\.agentOpinion/, 'does not read nested suggestion.agentOpinion as a new-structure source')

console.log('archive log display tests passed')

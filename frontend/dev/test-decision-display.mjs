import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { build } from 'esbuild'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const outdir = join(root, 'node_modules', '.cache', 'decision-display-test')
const agentOpinionOutfile = join(outdir, 'agentOpinion.mjs')
const decisionDisplayOutfile = join(outdir, 'decisionDisplay.mjs')

await mkdir(outdir, { recursive: true })
await build({
  entryPoints: [join(root, 'src', 'utils', 'agentOpinion.ts')],
  outfile: agentOpinionOutfile,
  bundle: true,
  format: 'esm',
  platform: 'node',
  logLevel: 'silent'
})
await build({
  entryPoints: [join(root, 'src', 'utils', 'decisionDisplay.ts')],
  outfile: decisionDisplayOutfile,
  bundle: true,
  format: 'esm',
  platform: 'node',
  logLevel: 'silent'
})

const { normalizeAgentOpinion } = await import(`${pathToFileURL(agentOpinionOutfile).href}?${Date.now()}`)
const { getManagerArbitrationBlock } = await import(`${pathToFileURL(decisionDisplayOutfile).href}?${Date.now()}`)

const normalizedNewOpinion = normalizeAgentOpinion({
  agentCode: 'MANAGER_COORDINATOR',
  summary: '旧摘要',
  confidenceScore: 0.12,
  consensusScore: 0.88,
  arbitrationDecision: '旧裁决',
  arbitrationReason: '旧理由',
  suggestion: {
    recommendedPrice: 99.9
  },
  agentOpinion: {
    opinionId: 'task:agent:MANAGER_COORDINATOR:1',
    agentCode: 'MANAGER_COORDINATOR',
    agentName: '经理协调智能体',
    status: 'ADOPTED',
    summary: '新结构摘要',
    confidence: 0.66,
    pricing: {
      recommendedPrice: 32.5
    },
    evidence: [
      { label: '价格带', value: '贴近竞品区间' }
    ],
    relations: {
      acceptedOpinionIds: ['task:agent:MARKET_INTEL:1'],
      rejectedOpinionIds: ['task:agent:RISK_CONTROL:1'],
      selectedOpinionIds: ['task:agent:MARKET_INTEL:1']
    },
    decision: {
      consensusScore: 0,
      arbitrationDecision: '采纳市场判断',
      arbitrationReason: '竞品带宽更稳定'
    }
  }
})

assert.ok(normalizedNewOpinion, 'normalizes the new agentOpinion payload')
assert.equal(normalizedNewOpinion.summary, '新结构摘要', 'prefers summary from the new agentOpinion payload')
assert.equal(normalizedNewOpinion.confidence, 0.66, 'prefers confidence from the new agentOpinion payload')
assert.equal(normalizedNewOpinion.recommendedPrice, 32.5, 'prefers pricing from the new agentOpinion payload')
assert.equal(normalizedNewOpinion.arbitration?.decisionSummary, '采纳市场判断', 'prefers arbitration decision from the new agentOpinion payload')
assert.equal(normalizedNewOpinion.arbitration?.decisionReason, '竞品带宽更稳定', 'prefers arbitration reason from the new agentOpinion payload')
assert.equal(normalizedNewOpinion.arbitration?.consensusScore, 0, 'keeps zero consensus score from the new agentOpinion payload')
assert.equal(normalizedNewOpinion.arbitration?.consensusScoreText, '0.00%', 'formats zero consensus score without dropping it')

const normalizedLegacyOpinion = normalizeAgentOpinion({
  resultSummary: '旧仲裁摘要',
  suggestedPrice: 28.8,
  evidence: [
    { label: '渠道判断', value: '旧证据仍可展示' }
  ],
  suggestion: {
    finalPrice: 31.5,
    strategy: 'MANUAL_REVIEW'
  },
  consensusScore: 0,
  conflicts: [
    { field: '价格带', reason: '与竞品价差过大' }
  ],
  acceptedOpinions: [
    { summary: '采纳市场方案' }
  ],
  rejectedOpinions: [
    { field: '利润率', reason: '低于风控底线' }
  ],
  arbitrationSummary: '保留市场价格带',
  arbitrationReason: '竞品更稳定',
  selectedOption: 'MARKET_INTEL'
})

assert.ok(normalizedLegacyOpinion, 'falls back to legacy payloads when agentOpinion is missing')
assert.equal(normalizedLegacyOpinion.summary, '旧仲裁摘要', 'falls back to legacy summary fields')
assert.equal(normalizedLegacyOpinion.recommendedPrice, 31.5, 'falls back to legacy suggestion pricing fields')
assert.equal(normalizedLegacyOpinion.arbitration?.decisionSummary, '保留市场价格带', 'falls back to legacy arbitration summary fields')
assert.equal(normalizedLegacyOpinion.arbitration?.decisionReason, '竞品更稳定', 'falls back to legacy arbitration reason fields')
assert.equal(normalizedLegacyOpinion.arbitration?.selectedAgentCode, 'MARKET_INTEL', 'falls back to legacy selected option fields')
assert.equal(normalizedLegacyOpinion.arbitration?.consensusScore, 0, 'keeps zero consensus score through legacy fallback')

for (const line of [
  ...(normalizedLegacyOpinion.arbitration?.disagreementPoints || []),
  ...(normalizedLegacyOpinion.arbitration?.acceptedOpinions || []),
  ...(normalizedLegacyOpinion.arbitration?.rejectedOpinions || [])
]) {
  assert.equal(typeof line, 'string', 'formats legacy arbitration object items as strings')
  assert.doesNotMatch(line, /\[object Object\]/, 'does not leak raw object stringification into arbitration text')
}

const arbitrationBlock = getManagerArbitrationBlock({
  suggestion: {
    consensusScore: 0,
    conflicts: [
      { field: '价格带', reason: '与竞品价差过大' }
    ],
    acceptedOpinions: [
      { summary: '采纳市场方案' }
    ],
    rejectedOpinions: [
      { field: '利润率', reason: '低于风控底线' }
    ],
    arbitrationSummary: '保留市场价格带',
    decisionReason: '竞品更稳定',
    selectedOption: 'MARKET_INTEL'
  }
})

assert.ok(arbitrationBlock, 'builds a display block from legacy fallback fields')
assert.equal(arbitrationBlock.consensusScoreText, '0.00%', 'decision display keeps zero consensus score visible')
assert.equal(arbitrationBlock.consensusScorePercent, 0, 'decision display keeps zero consensus score percent')
assert.ok(
  [...arbitrationBlock.disagreementLines, ...arbitrationBlock.decisionLines].every((line) => !line.includes('[object Object]')),
  'decision display never renders arbitration object arrays as [object Object]'
)

console.log('decision display tests passed')

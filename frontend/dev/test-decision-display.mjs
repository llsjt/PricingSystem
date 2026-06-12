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
const { getManagerArbitrationBlock, getSuggestionLines } = await import(`${pathToFileURL(decisionDisplayOutfile).href}?${Date.now()}`)

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

const normalizedMergeOpinion = normalizeAgentOpinion({
  agentCode: 'MANAGER_COORDINATOR',
  agentOpinion: {
    opinionId: 'task:agent:MANAGER_COORDINATOR:merge',
    agentCode: 'MANAGER_COORDINATOR',
    agentName: '经理协调智能体',
    status: 'MERGED',
    summary: '折中定价',
    relations: {
      acceptedOpinionIds: ['task:agent:MARKET_INTEL:1'],
      selectedOpinionIds: ['task:agent:MARKET_INTEL:1']
    },
    decision: {
      decisionType: 'MERGE',
      consensusScore: 0.72,
      arbitrationDecision: '综合专家意见',
      arbitrationReason: '市场与风控存在分歧，采用折中价'
    }
  }
})

assert.ok(normalizedMergeOpinion, 'normalizes MERGE arbitration payload')
assert.equal(normalizedMergeOpinion.arbitration?.decisionType, 'MERGE', 'keeps MERGE decision type')
assert.equal(normalizedMergeOpinion.arbitration?.selectedAgentCode, null, 'MERGE does not infer a selected single agent')
assert.equal(normalizedMergeOpinion.arbitration?.selectedAgentLabel, '综合专家意见折中定价', 'MERGE shows a composite decision label')

const mergeBlock = getManagerArbitrationBlock({
  agentOpinion: normalizedMergeOpinion.raw
})
assert.ok(mergeBlock?.decisionLines.includes('采纳方案：综合专家意见折中定价'), 'MERGE display uses composite decision wording')
assert.ok(
  !mergeBlock?.decisionLines.some((line) => line.includes('竞品市场判断')),
  'MERGE display does not claim a single accepted agent as the selected plan'
)

const normalizedRejectAllOpinion = normalizeAgentOpinion({
  agentCode: 'MANAGER_COORDINATOR',
  agentOpinion: {
    opinionId: 'task:agent:MANAGER_COORDINATOR:reject-all',
    agentCode: 'MANAGER_COORDINATOR',
    agentName: '经理协调智能体',
    status: 'BLOCKED',
    summary: '全部方案均需人工复核',
    relations: {
      acceptedOpinionIds: ['task:agent:DATA_ANALYSIS:1'],
      selectedOpinionIds: ['task:agent:DATA_ANALYSIS:1']
    },
    decision: {
      decisionType: 'REJECT_ALL',
      consensusScore: 0.22,
      arbitrationDecision: '拒绝自动采纳',
      arbitrationReason: '利润和风控结论冲突'
    }
  }
})

assert.ok(normalizedRejectAllOpinion, 'normalizes REJECT_ALL arbitration payload')
assert.equal(normalizedRejectAllOpinion.arbitration?.decisionType, 'REJECT_ALL', 'keeps REJECT_ALL decision type')
assert.equal(normalizedRejectAllOpinion.arbitration?.selectedAgentCode, null, 'REJECT_ALL does not infer a selected single agent')
assert.equal(normalizedRejectAllOpinion.arbitration?.selectedAgentLabel, '未采纳单一专家方案', 'REJECT_ALL shows a composite rejection label')

const rejectAllBlock = getManagerArbitrationBlock({
  agentOpinion: normalizedRejectAllOpinion.raw
})
assert.ok(rejectAllBlock?.decisionLines.includes('采纳方案：未采纳单一专家方案'), 'REJECT_ALL display uses composite rejection wording')
assert.ok(
  !rejectAllBlock?.decisionLines.some((line) => line.includes('经营收益测算')),
  'REJECT_ALL display does not claim a single accepted agent as the selected plan'
)

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

const merchantDataLines = getSuggestionLines('DATA_ANALYSIS', {
  recommendedPrice: 22,
  expectedSales: 96,
  expectedProfit: 620,
  priceChangeRate: 0.1,
  profitGrowth: 120,
  merchantPainPoint: '判断调价后销量和利润是否划算',
  merchantAction: '优先查看利润变化'
})
assert.ok(merchantDataLines.includes('调价幅度：+10.00%'), 'shows merchant-facing price change rate')
assert.ok(merchantDataLines.includes('利润变化：+¥120.00'), 'shows merchant-facing profit growth')
assert.ok(merchantDataLines.includes('解决痛点：判断调价后销量和利润是否划算'), 'shows merchant pain point')
assert.ok(merchantDataLines.includes('下一步：优先查看利润变化'), 'shows recommended merchant action')

const merchantRiskLines = getSuggestionLines('RISK_CONTROL', {
  recommendedPrice: 18.5,
  safeFloorPrice: 18.5,
  pass: false,
  needManualReview: true,
  merchantPainPoint: '确认是否会亏损、低毛利或突破价格红线',
  merchantAction: '按安全底价或约束修正后再提交人工审核'
})
assert.ok(merchantRiskLines.includes('安全底价：¥18.50'), 'shows risk guardrail floor')
assert.ok(merchantRiskLines.includes('是否需要人工复核：是'), 'shows manual review need')
assert.ok(merchantRiskLines.includes('下一步：按安全底价或约束修正后再提交人工审核'), 'shows risk next action')

const merchantManagerLines = getSuggestionLines('MANAGER_COORDINATOR', {
  finalPrice: 21.5,
  expectedSales: 98,
  expectedProfit: 650,
  profitGrowth: 150,
  strategy: '人工审核',
  merchantPainPoint: '给出商家可落地的最终价格、预期收益和复核动作',
  merchantAction: '进入人工审核，核对库存、活动节奏后再应用建议价'
})
assert.ok(merchantManagerLines.includes('利润变化：+¥150.00'), 'shows final profit delta')
assert.ok(merchantManagerLines.includes('解决痛点：给出商家可落地的最终价格、预期收益和复核动作'), 'shows manager pain point')
assert.ok(merchantManagerLines.includes('下一步：进入人工审核，核对库存、活动节奏后再应用建议价'), 'shows manager next action')

const genericFallbackLines = getSuggestionLines(null, {
  priceChangeRate: 0.1
})
assert.ok(genericFallbackLines.includes('调价幅度：10.00%'), 'formats rate-like fallback fields as percentages instead of currency')

console.log('decision display tests passed')

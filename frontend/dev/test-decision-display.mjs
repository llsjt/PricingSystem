import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { build } from 'esbuild'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const outdir = join(root, 'node_modules', '.cache', 'decision-display-test')
const outfile = join(outdir, 'decisionDisplay.mjs')

await mkdir(outdir, { recursive: true })
await build({
  entryPoints: [join(root, 'src', 'utils', 'decisionDisplay.ts')],
  outfile,
  bundle: true,
  format: 'esm',
  platform: 'node',
  logLevel: 'silent'
})

const {
  formatEvidenceValue,
  getLogAgentName,
  getManagerArbitrationBlock,
  getSuggestionLines
} = await import(`${pathToFileURL(outfile).href}?${Date.now()}`)

assert.equal(formatEvidenceValue('质量原因', ['valid competitors >= 5']), '有效竞品数不少于5个')
assert.equal(formatEvidenceValue('竞品状态', 'OK'), '正常')
assert.equal(formatEvidenceValue('硬约束通过', true), '是')
assert.equal(
  getLogAgentName({ agentName: '市场情报Agent', agentCode: 'MARKET_INTEL', roleName: '' }),
  '市场情报智能体'
)
assert.equal(
  getLogAgentName({ agentName: 'Manager Agent', agentCode: '', roleName: 'Manager Agent' }),
  '经理协调智能体'
)
assert.deepEqual(
  getSuggestionLines(null, {
    source: 'TMALL_CSV',
    sourceStatus: 'OK',
    dataQuality: 'LOW',
    usedCompetitorCount: 2,
    riskNotes: '本次竞品数据不足，仅供参考'
  }),
  [
    '竞品来源：天猫真实样本',
    '竞品状态：正常',
    '数据质量：低',
    '纳入分析竞品：2',
    '风险提示：本次竞品数据不足，仅供参考'
  ]
)

assert.deepEqual(
  getManagerArbitrationBlock({
    consensusScore: 0,
    disagreementSummary: '数据建议偏激进，市场建议更贴近竞品带宽',
    disagreementPoints: [
      '数据分析建议价：¥29.90',
      '市场情报建议价：¥31.50'
    ],
    acceptedOpinions: [
      '采纳市场情报给出的竞品区间',
      '采纳风控底价约束'
    ],
    rejectedOpinions: [
      '未完全采纳数据分析的激进提价建议'
    ],
    arbitrationDecision: '采纳市场情报建议价并保留风控底线',
    arbitrationReason: '在利润约束内更接近当前竞品价格带',
    selectedAgent: 'MARKET_INTEL',
    selectedPrice: 31.5,
    selectedStrategy: 'MANUAL_REVIEW'
  }),
  {
    consensusScoreText: '0.00%',
    consensusScorePercent: 0,
    disagreementSummary: '数据建议偏激进，市场建议更贴近竞品带宽',
    disagreementPoints: [
      '数据分析建议价：¥29.90',
      '市场情报建议价：¥31.50'
    ],
    decisionSummary: '采纳市场情报建议价并保留风控底线',
    decisionReason: '在利润约束内更接近当前竞品价格带',
    acceptedOpinions: [
      '采纳市场情报给出的竞品区间',
      '采纳风控底价约束'
    ],
    rejectedOpinions: [
      '未完全采纳数据分析的激进提价建议'
    ],
    selectedAgent: '市场情报智能体',
    selectedPrice: '¥31.50',
    selectedStrategy: '人工审核',
    disagreementLines: [
      '共识度：0.00%',
      '分歧摘要：数据建议偏激进，市场建议更贴近竞品带宽',
      '分歧点 1：数据分析建议价：¥29.90',
      '分歧点 2：市场情报建议价：¥31.50'
    ],
    decisionLines: [
      '裁决结论：采纳市场情报建议价并保留风控底线',
      '裁决理由：在利润约束内更接近当前竞品价格带',
      '采纳意见 1：采纳市场情报给出的竞品区间',
      '采纳意见 2：采纳风控底价约束',
      '未采纳意见 1：未完全采纳数据分析的激进提价建议',
      '采纳方案：市场情报智能体',
      '采纳价格：¥31.50',
      '采纳策略：人工审核'
    ]
  },
  'renders normalized manager arbitration fields, including zero consensus score'
)

assert.equal(
  getManagerArbitrationBlock({
    finalPrice: 29.9,
    summary: '综合决策完成'
  }),
  null,
  'keeps legacy manager suggestions compatible when no arbitration fields were returned'
)

assert.deepEqual(
  getManagerArbitrationBlock({
    suggestion: {
      consensusScore: 0,
      conflicts: ['legacy price gap'],
      acceptedOpinions: ['accept market'],
      rejectedOpinions: ['reject risk'],
      arbitrationSummary: 'legacy summary',
      decisionReason: 'legacy reason',
      selectedOption: 'MARKET_INTEL'
    }
  }),
  {
    consensusScoreText: '0.00%',
    consensusScorePercent: 0,
    disagreementSummary: null,
    disagreementPoints: [
      'legacy price gap'
    ],
    decisionSummary: 'legacy summary',
    decisionReason: 'legacy reason',
    acceptedOpinions: [
      'accept market'
    ],
    rejectedOpinions: [
      'reject risk'
    ],
    selectedAgent: '市场情报智能体',
    selectedPrice: null,
    selectedStrategy: null,
    disagreementLines: [
      '共识度：0.00%',
      '分歧点 1：legacy price gap'
    ],
    decisionLines: [
      '裁决结论：legacy summary',
      '裁决理由：legacy reason',
      '采纳意见 1：accept market',
      '未采纳意见 1：reject risk',
      '采纳方案：市场情报智能体'
    ]
  },
  'reads legacy arbitration fields from nested suggestion payloads'
)

console.log('decision display tests passed')

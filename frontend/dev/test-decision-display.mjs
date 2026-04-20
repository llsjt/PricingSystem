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

const { formatEvidenceValue, getLogAgentName, getSuggestionLines } = await import(`${pathToFileURL(outfile).href}?${Date.now()}`)

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

console.log('decision display tests passed')

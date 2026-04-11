<template>
  <div class="pricing-page">
    <el-alert
      v-if="!hasLlmConfig"
      title="请先配置大模型 API 密钥"
      type="warning"
      show-icon
      :closable="false"
      class="llm-alert"
    >
      <template #default>
        使用智能定价功能需要配置您自己的大模型 API 密钥。
        <router-link to="/profile" class="alert-link">前往个人中心配置</router-link>
      </template>
    </el-alert>
    <section class="panel-card">
      <div class="section-head">
        <div>
          <h2>任务流程</h2>
          <p>配置任务、智能决策、结果报告。</p>
        </div>
      </div>
      <el-steps :active="stepBarActive" finish-status="success" align-center>
        <el-step title="配置任务" />
        <el-step title="智能决策" />
        <el-step title="结果报告" />
      </el-steps>
    </section>

    <section v-if="activeStep === 0" class="panel-card">
      <div class="section-head"><div><h2>任务配置</h2><p>选择平台、店铺、商品并设置目标。</p></div></div>
      <el-form label-position="top" class="config-grid">
        <el-form-item label="平台">
          <el-select v-model="taskConfig.platform" clearable placeholder="请选择平台" @change="onPlatformChange">
            <el-option v-for="platform in platformOptions" :key="platform" :label="platform" :value="platform" />
          </el-select>
        </el-form-item>
        <el-form-item label="店铺">
          <el-select v-model="taskConfig.shopId" clearable placeholder="请选择店铺" :disabled="!taskConfig.platform" @change="onShopChange">
            <el-option v-for="shop in availableShops" :key="shop.id" :label="shop.shopName" :value="shop.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="商品">
          <el-select v-model="taskConfig.productId" filterable remote reserve-keyword :disabled="!canSearchProducts" :remote-method="searchProducts" :loading="searchLoading" :placeholder="productPlaceholder">
            <el-option v-for="product in productOptions" :key="product.id" :label="product.productName" :value="product.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="策略目标" class="full-span">
          <el-radio-group v-model="taskConfig.strategyGoal">
            <el-radio v-for="goal in goalOptions" :key="goal.label" :label="goal.label" border>{{ goal.name }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="约束条件" class="full-span">
          <el-input v-model="taskConfig.constraints" type="textarea" :rows="4" placeholder="例如：利润率不低于 15%，最低售价不低于成本价。" />
        </el-form-item>
      </el-form>
      <div class="toolbar"><el-button type="primary" :loading="starting" :disabled="!hasLlmConfig" @click="startTask">启动任务</el-button></div>
    </section>

    <section v-else-if="activeStep === 1" class="panel-card">
      <div class="section-head">
        <div><h2>多 Agent 决策</h2><p>实时流只通过 Java SSE 下发。</p></div>
        <div class="toolbar">
          <el-button v-if="canCancelTask" @click="cancelTask">取消任务</el-button>
          <el-button v-if="canReconfigureTask" @click="resetTask">重新配置任务</el-button>
          <el-button v-if="taskId" @click="refreshSnapshot">刷新进度</el-button>
          <el-button type="primary" :disabled="!canViewReport" @click="activeStep = 2">查看结果报告</el-button>
        </div>
      </div>
      <div class="status-bar">
        <el-tag :type="statusTag">{{ statusLabel }}</el-tag>
        <span v-if="state.errorMessage" class="error-text">{{ state.errorMessage }}</span>
      </div>
      <div class="agent-list">
        <article v-for="agent in agents" :key="agent.code" class="agent-box">
          <div class="agent-head">
            <h3>{{ agent.order }}. {{ agent.name }}</h3>
            <el-tag size="small" :type="state.cards[agent.code] ? 'success' : waitingOrder === agent.order ? 'warning' : 'info'">
              {{ state.cards[agent.code] ? '已完成' : waitingOrder === agent.order ? '分析中' : '等待中' }}
            </el-tag>
          </div>
          <template v-if="state.cards[agent.code]">
            <h4>思考过程</h4>
            <p class="thinking">{{ state.cards[agent.code]?.thinking || '-' }}</p>
            <h4>依据</h4>
            <ul><li v-for="(line, index) in evidenceLines(agent.code)" :key="`${agent.code}-e-${index}`">{{ line }}</li></ul>
            <h4>建议</h4>
            <ul><li v-for="(line, index) in suggestionLines(agent.code)" :key="`${agent.code}-s-${index}`">{{ line }}</li></ul>
            <template v-if="agent.code === 'MANAGER_COORDINATOR' && state.cards[agent.code]?.reasonWhy">
              <h4>为什么给出这个建议</h4>
              <p>{{ state.cards[agent.code]?.reasonWhy }}</p>
            </template>
          </template>
          <div v-else-if="isRunning(state.taskStatus) && waitingOrder === agent.order" class="waiting">正在分析中，请稍候...</div>
          <el-empty v-else description="等待该 Agent 输出结果" :image-size="80" />
        </article>
      </div>
    </section>

    <section v-else class="report-page">
      <div class="metric-grid">
        <div class="metric-card"><span>最终价格</span><strong>{{ currency(state.finalPrice) }}</strong></div>
        <div class="metric-card"><span>预期销量</span><strong>{{ expectedSales ?? '-' }}</strong></div>
        <div class="metric-card"><span>预期利润</span><strong>{{ currency(expectedProfit) }}</strong></div>
        <div class="metric-card"><span>执行策略</span><strong>{{ strategyText || '-' }}</strong></div>
      </div>
      <section class="panel-card">
        <div class="section-head">
          <div><h2>结果报告</h2><p>{{ reportSummary || '最终建议由 4 个 Agent 的分析结果综合得出。' }}</p></div>
          <div class="toolbar"><el-button @click="activeStep = 1">查看智能决策过程</el-button><el-button type="primary" @click="resetTask">重新配置任务</el-button></div>
        </div>
        <el-table :data="comparisonData" border stripe>
          <el-table-column prop="productTitle" label="商品名称" min-width="180" show-overflow-tooltip />
          <el-table-column label="原价" width="120"><template #default="{ row }">{{ currency(row.originalPrice) }}</template></el-table-column>
          <el-table-column label="建议价" width="120"><template #default="{ row }">{{ currency(row.suggestedPrice) }}</template></el-table-column>
          <el-table-column prop="expectedSales" label="预期销量" width="110" />
          <el-table-column label="预期利润" width="120"><template #default="{ row }">{{ currency(row.expectedProfit) }}</template></el-table-column>
          <el-table-column label="利润变化" width="120"><template #default="{ row }"><el-tag :type="Number(row.profitChange || 0) >= 0 ? 'success' : 'danger'">{{ signedCurrency(row.profitChange) }}</el-tag></template></el-table-column>
          <el-table-column prop="passStatus" label="风控结果" width="110" />
          <el-table-column prop="executeStrategy" label="执行策略" width="120" />
          <el-table-column prop="appliedStatus" label="应用状态" width="110" />
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.appliedStatus !== '已应用'" type="primary" link :loading="applyingIds.includes(Number(row.resultId))" @click="applyPrice(row)">应用建议</el-button>
              <el-tag v-else type="success">已应用</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </section>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { applyDecision, cancelPricingTask, createPricingTask, getPricingTaskSnapshot, getPricingTaskStreamUrl, type AgentCardContent, type DecisionComparisonItem, type DecisionLogItem, type PricingAgentCode, type PricingTaskSnapshot, type PricingTaskStatus, type PricingTaskStreamMessage } from '../api/decision'
import { getProductList } from '../api/product'
import { getLlmConfig } from '../api/llmConfig'
import { useShopStore } from '../stores/shop'
import { getAuthToken } from '../utils/authSession'
import { sanitizeErrorMessage } from '../utils/error'

interface ApiResponse<T> { code: number; data: T; message?: string }
interface ProductOption { id: number; productName: string }

const agents = [{ code: 'DATA_ANALYSIS', name: '数据分析Agent', order: 1 }, { code: 'MARKET_INTEL', name: '市场情报Agent', order: 2 }, { code: 'RISK_CONTROL', name: '风险控制Agent', order: 3 }, { code: 'MANAGER_COORDINATOR', name: '经理协调Agent', order: 4 }] as const
const goalOptions = [{ label: 'MAX_PROFIT', name: '利润优先' }, { label: 'CLEARANCE', name: '清仓促销' }, { label: 'MARKET_SHARE', name: '市场份额优先' }] as const
const emptyCards = () => ({ DATA_ANALYSIS: null, MARKET_INTEL: null, RISK_CONTROL: null, MANAGER_COORDINATOR: null }) as Record<PricingAgentCode, AgentCardContent | null>

const shopStore = useShopStore()
const taskConfig = reactive({ platform: '', shopId: undefined as number | undefined, productId: undefined as number | undefined, strategyGoal: 'MAX_PROFIT' as typeof goalOptions[number]['label'], constraints: '' })
const state = reactive({ taskStatus: 'IDLE' as PricingTaskStatus, cards: emptyCards(), finalPrice: null as number | null, strategy: '', finalSummary: '', errorMessage: '' })
const productOptions = ref<ProductOption[]>([])
const searchLoading = ref(false)
const starting = ref(false)
const activeStep = ref(0)
const taskId = ref<number | null>(null)
const comparisonData = ref<DecisionComparisonItem[]>([])
const archiveReportSummary = ref('')
const applyingIds = ref<number[]>([])
const hasLlmConfig = ref(false)
let aborter: AbortController | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null
let loadToken = 0

const platformOptions = computed(() => Array.from(new Set(shopStore.shops.map((shop) => String(shop.platform || '').trim()).filter(Boolean))))
const availableShops = computed(() => shopStore.shops.filter((shop) => shop.platform === taskConfig.platform))
const canSearchProducts = computed(() => Boolean(taskConfig.platform && taskConfig.shopId))
const productPlaceholder = computed(() => !taskConfig.platform ? '请先选择平台' : !taskConfig.shopId ? '请先选择店铺' : '输入商品名称搜索')
const canCancelTask = computed(() => Boolean(taskId.value && ['QUEUED', 'RUNNING', 'RETRYING'].includes(state.taskStatus)))
const canReconfigureTask = computed(() => state.taskStatus === 'CANCELLED')
const canViewReport = computed(() => ['COMPLETED', 'MANUAL_REVIEW'].includes(state.taskStatus) || Object.values(state.cards).filter(Boolean).length === agents.length)
const stepBarActive = computed(() => activeStep.value === 2 ? 3 : activeStep.value === 1 ? 2 : 1)
const waitingOrder = computed(() => isRunning(state.taskStatus) ? (agents.find((agent) => !state.cards[agent.code])?.order || 0) : 0)
const statusLabel = computed(() => ({ IDLE: '未开始', PENDING: '待执行', QUEUED: '待执行', RUNNING: '执行中', RETRYING: '重试中', MANUAL_REVIEW: '人工审核', COMPLETED: '已完成', FAILED: '失败', CANCELLED: '已取消' }[state.taskStatus] || state.taskStatus))
const statusTag = computed(() => state.taskStatus === 'FAILED' ? 'danger' : ['CANCELLED', 'MANUAL_REVIEW'].includes(state.taskStatus) ? 'warning' : state.taskStatus === 'COMPLETED' ? 'success' : 'info')
const managerSuggestion = computed<Record<string, unknown>>(() => state.cards.MANAGER_COORDINATOR?.suggestion && typeof state.cards.MANAGER_COORDINATOR.suggestion === 'object' ? state.cards.MANAGER_COORDINATOR.suggestion : {})
const expectedSales = computed(() => numberOf(managerSuggestion.value.expectedSales))
const expectedProfit = computed(() => numberOf(managerSuggestion.value.expectedProfit))
const strategyText = computed(() => state.strategy || String(managerSuggestion.value.strategy || ''))
const reportSummary = computed(() => archiveReportSummary.value.trim() || state.finalSummary || String(managerSuggestion.value.summary || ''))

const numberOf = (value: unknown) => { const n = Number(value); return Number.isFinite(n) ? n : null }
const currency = (value: unknown) => { const n = numberOf(value); return n == null ? '-' : n.toLocaleString('zh-CN', { style: 'currency', currency: 'CNY', minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
const signedCurrency = (value: unknown) => { const n = numberOf(value); return n == null ? '-' : `${n >= 0 ? '+' : '-'}${currency(Math.abs(n))}` }
const isRunning = (status: PricingTaskStatus) => ['PENDING', 'QUEUED', 'RUNNING', 'RETRYING'].includes(status)
const isTerminal = (status: PricingTaskStatus) => ['COMPLETED', 'MANUAL_REVIEW', 'FAILED', 'CANCELLED'].includes(status)
const normalizeCard = (card?: AgentCardContent | null): AgentCardContent => ({ thinking: String(card?.thinking || ''), evidence: Array.isArray(card?.evidence) ? card.evidence : [], suggestion: card?.suggestion && typeof card.suggestion === 'object' ? card.suggestion : {}, reasonWhy: card?.reasonWhy || null })
const stopRealtime = () => { if (aborter) { aborter.abort(); aborter = null } if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }
const resetState = () => { stopRealtime(); taskId.value = null; state.taskStatus = 'IDLE'; state.cards = emptyCards(); state.finalPrice = null; state.strategy = ''; state.finalSummary = ''; state.errorMessage = ''; comparisonData.value = []; archiveReportSummary.value = '' }
const evidenceLines = (code: PricingAgentCode) => (state.cards[code]?.evidence || []).map((item, i) => `${String(item.label || `依据${i + 1}`)}：${item.value == null ? '-' : typeof item.value === 'object' ? JSON.stringify(item.value) : String(item.value)}`).length ? (state.cards[code]?.evidence || []).map((item, i) => `${String(item.label || `依据${i + 1}`)}：${item.value == null ? '-' : typeof item.value === 'object' ? JSON.stringify(item.value) : String(item.value)}`) : ['暂无依据']
const suggestionLines = (code: PricingAgentCode) => { const s = state.cards[code]?.suggestion || {}; const lines: string[] = []; const range = s.priceRange as Record<string, unknown> | undefined; if (range && numberOf(range.min) != null && numberOf(range.max) != null) lines.push(`建议价格区间：${currency(range.min)} ~ ${currency(range.max)}`); for (const [key, value] of Object.entries(s)) { if (key === 'priceRange' || value == null) continue; lines.push(`${key}：${typeof value === 'number' ? value : String(value)}`) } return lines.length ? lines : ['暂无建议'] }

const onPlatformChange = async () => { taskConfig.shopId = undefined; taskConfig.productId = undefined; productOptions.value = []; if (availableShops.value.length === 1) { taskConfig.shopId = availableShops.value[0].id; await loadProducts() } }
const onShopChange = async () => { taskConfig.productId = undefined; productOptions.value = []; if (taskConfig.shopId) await loadProducts() }
const searchProducts = (keyword: string) => { void loadProducts(keyword) }
const loadProducts = async (keyword = '') => { const token = ++loadToken; if (!canSearchProducts.value) return; searchLoading.value = true; try { const res = await getProductList({ page: 1, size: 100, keyword, platform: taskConfig.platform || undefined, shopId: taskConfig.shopId }) as ApiResponse<{ records: Array<{ id: number; productName: string }> }>; if (token !== loadToken) return; productOptions.value = Array.isArray(res.data?.records) ? res.data.records.map((item) => ({ id: Number(item.id), productName: String(item.productName || '') })) : [] } finally { if (token === loadToken) searchLoading.value = false } }

const applySnapshotDetail = (detail?: PricingTaskSnapshot['detail'] | null) => { if (!detail) return; state.taskStatus = (detail.taskStatus || 'RUNNING') as PricingTaskStatus; state.finalPrice = detail.finalPrice != null ? Number(detail.finalPrice) : null; state.strategy = String(detail.strategy || ''); state.finalSummary = String(detail.finalSummary || '') }
const applySnapshotLogs = (logs: DecisionLogItem[]) => { const cards = emptyCards(); logs.sort((a, b) => Number(a.displayOrder || a.runOrder || 0) - Number(b.displayOrder || b.runOrder || 0)).forEach((log) => { const code = String(log.agentCode || '') as PricingAgentCode; if (code in cards) cards[code] = normalizeCard({ thinking: String(log.thinking || log.outputSummary || ''), evidence: log.evidence || [], suggestion: log.suggestion || {}, reasonWhy: log.reasonWhy || null }) }); state.cards = cards }
const applySnapshotComparison = (comparison: DecisionComparisonItem[]) => { comparisonData.value = comparison; archiveReportSummary.value = comparisonData.value.find((row) => String(row.resultSummary || '').trim())?.resultSummary || '' }
const loadSnapshot = async (id: number) => { const res = await getPricingTaskSnapshot(id) as ApiResponse<PricingTaskSnapshot>; if (res.code !== 200 || !res.data) return; applySnapshotDetail(res.data.detail); applySnapshotLogs(Array.isArray(res.data.logs) ? res.data.logs : []); applySnapshotComparison(Array.isArray(res.data.comparison) ? res.data.comparison : []) }

const handleStream = async (payload: PricingTaskStreamMessage) => { if (payload.type === 'task_started') state.taskStatus = (payload.status || 'RUNNING') as PricingTaskStatus; if (payload.type === 'agent_card') { const code = payload.agentCode as PricingAgentCode; if (code in state.cards) state.cards[code] = normalizeCard(payload.card) } if (payload.type === 'task_completed') { state.taskStatus = (payload.status || 'COMPLETED') as PricingTaskStatus; if (payload.result) { state.finalPrice = numberOf(payload.result.finalPrice); state.strategy = String(payload.result.strategy || state.strategy || ''); state.finalSummary = String(payload.result.summary || state.finalSummary || '') } if (taskId.value) await loadSnapshot(taskId.value); stopRealtime(); ElMessage[state.taskStatus === 'MANUAL_REVIEW' ? 'warning' : 'success'](state.taskStatus === 'MANUAL_REVIEW' ? '任务已完成，当前结果需要人工审核' : '智能决策已完成，可以查看结果报告') } if (payload.type === 'task_failed') { state.taskStatus = (payload.status || 'FAILED') as PricingTaskStatus; state.errorMessage = sanitizeErrorMessage(payload.message, state.taskStatus === 'CANCELLED' ? '任务已取消' : '任务执行失败'); if (taskId.value) await loadSnapshot(taskId.value); stopRealtime(); ElMessage[state.taskStatus === 'CANCELLED' || state.taskStatus === 'MANUAL_REVIEW' ? 'warning' : 'error'](state.errorMessage) } }

const startPolling = () => { if (pollTimer || !taskId.value) return; pollTimer = setInterval(async () => { if (!taskId.value) return; if (!isRunning(state.taskStatus)) { stopRealtime(); return } await loadSnapshot(taskId.value); if (isTerminal(state.taskStatus)) stopRealtime() }, 2000) }
const startStream = async (id: number) => { stopRealtime(); aborter = new AbortController(); try { const response = await fetch(getPricingTaskStreamUrl(id), { method: 'GET', headers: { Accept: 'text/event-stream', Authorization: `Bearer ${getAuthToken()}` }, credentials: 'include', signal: aborter.signal }); if (!response.ok || !response.body) throw new Error('stream failed'); const reader = response.body.getReader(); const decoder = new TextDecoder('utf-8'); let buffer = ''; while (true) { const { done, value } = await reader.read(); if (done) break; buffer += decoder.decode(value, { stream: true }); const chunks = buffer.split('\n\n'); buffer = chunks.pop() || ''; for (const chunk of chunks) { const data = chunk.split('\n').filter((line) => line.startsWith('data:')).map((line) => line.slice(5).trim()).join('\n'); if (!data) continue; try { await handleStream(JSON.parse(data) as PricingTaskStreamMessage) } catch {} } } } catch { if (taskId.value) await loadSnapshot(taskId.value) } finally { aborter = null } }

const startTask = async () => { if (!taskConfig.platform) return ElMessage.warning('请选择平台'); if (!taskConfig.shopId) return ElMessage.warning('请选择店铺'); if (!taskConfig.productId) return ElMessage.warning('请选择一个商品'); starting.value = true; try { resetState(); state.taskStatus = 'QUEUED'; const res = await createPricingTask({ productId: taskConfig.productId, constraints: taskConfig.constraints, strategyGoal: taskConfig.strategyGoal }) as ApiResponse<number>; if (res.code !== 200 || !res.data) { state.taskStatus = 'FAILED'; state.errorMessage = sanitizeErrorMessage(res.message, '启动任务失败'); return ElMessage.error(state.errorMessage) } taskId.value = Number(res.data); activeStep.value = 1; await loadSnapshot(taskId.value); void startStream(taskId.value); startPolling(); ElMessage.success('任务已启动，进入智能决策阶段') } catch { state.taskStatus = 'FAILED'; state.errorMessage = '启动任务失败'; ElMessage.error(state.errorMessage) } finally { starting.value = false } }
const cancelTask = async () => { if (!taskId.value || !canCancelTask.value) return; try { await ElMessageBox.confirm('确认取消当前任务吗？', '取消任务', { type: 'warning', confirmButtonText: '确认取消', cancelButtonText: '继续执行' }); await loadSnapshot(taskId.value); if (!['QUEUED', 'RUNNING', 'RETRYING'].includes(state.taskStatus)) return ElMessage.warning(`当前任务状态为 ${statusLabel.value}，不支持取消`); const res = await cancelPricingTask(taskId.value); if (res.code !== 200) return ElMessage.error(sanitizeErrorMessage(res.message, '取消任务失败')); stopRealtime(); state.taskStatus = 'CANCELLED'; state.errorMessage = '任务已取消'; await loadSnapshot(taskId.value); ElMessage.warning('任务已取消') } catch (error) { if (error !== 'cancel') ElMessage.error('取消任务失败') } }
const refreshSnapshot = async () => { if (!taskId.value) return; await loadSnapshot(taskId.value); if (isRunning(state.taskStatus) && !aborter) void startStream(taskId.value); if (isRunning(state.taskStatus)) startPolling(); ElMessage.success(`已刷新快照，当前已收到 ${Object.values(state.cards).filter(Boolean).length}/4 条分析结果`) }
const resetTask = () => { resetState(); activeStep.value = 0 }
const applyPrice = async (row: DecisionComparisonItem) => { const id = Number(row.resultId || 0); if (!id) return ElMessage.error('未找到可应用的结果记录'); try { await ElMessageBox.confirm(`确认将商品“${String(row.productTitle || '-')}”的售价更新为 ${currency(row.suggestedPrice)} 吗？`, '应用价格建议', { type: 'warning', confirmButtonText: '确认应用', cancelButtonText: '取消' }); applyingIds.value.push(id); const res = await applyDecision(id); if (res.code !== 200) return ElMessage.error(sanitizeErrorMessage(res.message, '应用失败')); ElMessage.success('价格建议已应用'); if (taskId.value) await loadSnapshot(taskId.value) } catch (error) { if (error !== 'cancel') ElMessage.error('应用失败') } finally { applyingIds.value = applyingIds.value.filter((item) => item !== id) } }

onMounted(async () => { getLlmConfig().then(res => { hasLlmConfig.value = !!res.data?.data?.hasApiKey }).catch(() => { hasLlmConfig.value = false }); const loaded = await shopStore.fetchShops(); if (loaded && platformOptions.value.length === 1) { taskConfig.platform = platformOptions.value[0]; await onPlatformChange() } })
onBeforeUnmount(() => stopRealtime())
</script>

<style scoped>
.llm-alert{margin-bottom:16px}.alert-link{color:#409eff;text-decoration:underline;margin-left:4px}.pricing-page{display:grid;gap:16px}.panel-card{padding:18px;border-radius:16px;background:#fff;border:1px solid rgba(15,23,42,.08);box-shadow:0 10px 30px rgba(15,23,42,.05)}.section-head{display:flex;justify-content:space-between;gap:16px;margin-bottom:16px}.section-head h2{margin:0 0 6px;font-size:28px;color:#172033}.section-head p{margin:0;color:#6b7280}.config-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0 14px}.full-span{grid-column:1/-1}.toolbar{display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap}.status-bar{display:flex;gap:10px;align-items:center;margin-bottom:16px}.error-text{color:#b42318}.agent-list{display:grid;gap:14px}.agent-box{padding:18px;border-radius:14px;border:1px solid rgba(226,232,240,.9);background:linear-gradient(180deg,#fff 0%,#f8fbff 100%)}.agent-head{display:flex;justify-content:space-between;gap:12px;margin-bottom:12px}.agent-head h3{margin:0;font-size:24px;color:#182236}.thinking{white-space:pre-wrap;line-height:1.8}.waiting{min-height:140px;display:grid;place-items:center;color:#64748b}.report-page,.metric-grid{display:grid;gap:12px}.metric-grid{grid-template-columns:repeat(4,minmax(0,1fr))}.metric-card{padding:18px;border-radius:14px;background:#fff;border:1px solid rgba(15,23,42,.08);box-shadow:0 10px 30px rgba(15,23,42,.05);display:grid;gap:8px}.metric-card span{font-size:13px;color:#64748b}.metric-card strong{font-size:24px;color:#172033}@media (max-width:1100px){.config-grid,.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media (max-width:760px){.config-grid,.metric-grid{grid-template-columns:1fr}.section-head,.agent-head{flex-direction:column;align-items:flex-start}.toolbar{justify-content:flex-start}}
</style>

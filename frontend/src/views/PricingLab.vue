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
        <router-link to="/models" class="alert-link">前往模型管理配置</router-link>
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
          <div class="constraint-panel">
            <div class="constraint-intro">
              <strong>定价硬约束</strong>
              <span>未填写的售价区间和降价幅度不会参与限制。</span>
            </div>
            <div class="constraint-grid">
              <div class="constraint-field">
                <span class="constraint-label">最低利润率</span>
                <div class="constraint-control">
                  <el-input-number v-model="constraintForm.minProfitRatePercent" :min="0.01" :max="99.99" :step="1" :precision="2" controls-position="right" />
                  <span class="constraint-unit">%</span>
                </div>
              </div>
              <div class="constraint-field">
                <span class="constraint-label">最低售价</span>
                <div class="constraint-control">
                  <el-input-number v-model="constraintForm.minPrice" :min="0.01" :step="1" :precision="2" controls-position="right" placeholder="不限制" />
                  <span class="constraint-unit">元</span>
                </div>
              </div>
              <div class="constraint-field">
                <span class="constraint-label">最高售价</span>
                <div class="constraint-control">
                  <el-input-number v-model="constraintForm.maxPrice" :min="0.01" :step="1" :precision="2" controls-position="right" placeholder="不限制" />
                  <span class="constraint-unit">元</span>
                </div>
              </div>
              <div class="constraint-field">
                <span class="constraint-label">最大降价幅度</span>
                <div class="constraint-control">
                  <el-input-number v-model="constraintForm.maxDiscountRatePercent" :min="0.01" :max="100" :step="1" :precision="2" controls-position="right" placeholder="不限制" />
                  <span class="constraint-unit">%</span>
                </div>
              </div>
              <div class="constraint-switch">
                <div>
                  <span class="constraint-label">强制人工审核</span>
                  <small>规则通过后仍进入人工确认。</small>
                </div>
                <el-switch v-model="constraintForm.forceManualReview" />
              </div>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <div class="toolbar"><el-button type="primary" :loading="starting" :disabled="!hasLlmConfig" @click="startTask">启动任务</el-button></div>
    </section>

    <section v-else-if="activeStep === 1" class="panel-card decision-chat-panel">
      <div class="section-head decision-chat-head">
        <div class="decision-chat-title">
          <span class="decision-chat-kicker">AI 决策流</span>
          <h2>多 Agent 决策</h2>
          <p>各 Agent 会按执行顺序生成分析消息。</p>
        </div>
        <div class="toolbar decision-toolbar">
          <el-button v-if="canCancelTask" @click="cancelTask">取消任务</el-button>
          <el-button v-if="canReconfigureTask" @click="resetTask">重新配置任务</el-button>
          <el-button v-if="taskId" @click="refreshSnapshot">刷新进度</el-button>
          <el-button v-if="canSkipReveal" @click="skipRevealAnimation">跳过动画</el-button>
          <el-button type="primary" :disabled="!canViewReport" @click="activeStep = 2">查看结果报告</el-button>
        </div>
      </div>
      <div v-if="visibleAgents.length === 0" class="agent-stream-empty">
        <div class="agent-stream-pulse"><span></span><span></span><span></span></div>
        <h3>智能定价任务已启动</h3>
        <p>正在准备商品上下文，首个 Agent 开始分析后会生成决策消息。</p>
      </div>
      <div v-else class="agent-list">
        <article v-for="agent in visibleAgents" :key="agent.code" class="agent-box" :class="{ 'is-streaming': isCardRunning(agent.code) || shouldAnimate(agent.code) }">
          <div class="agent-avatar" aria-hidden="true">{{ agentIcon[agent.code] }}</div>
          <div class="agent-message">
          <div class="agent-head">
            <div class="agent-identity">
              <div class="agent-title">
                <h3>{{ agent.order }}. {{ agent.name }}</h3>
                <span class="agent-role">{{ agentRoleLabel[agent.code] }}</span>
              </div>
            </div>
            <el-tag size="small" :type="isCardFailed(agent.code) ? 'danger' : isCardCompleted(agent.code) ? 'success' : isCardRunning(agent.code) ? 'warning' : 'info'">
              {{ isCardFailed(agent.code) ? '失败' : isCardCompleted(agent.code) ? '已完成' : isCardRunning(agent.code) ? '分析中' : '等待中' }}
            </el-tag>
          </div>
          <template v-if="isCardCompleted(agent.code)">
            <h4>分析摘要</h4>
            <TypewriterText v-if="shouldAnimate(agent.code)" :text="state.cards[agent.code]?.thinking || '-'" :speed="typewriterSpeed" class="thinking" @done="markThinkingDone(agent.code)" />
            <p v-else class="thinking">{{ state.cards[agent.code]?.thinking || '-' }}</p>
            <h4 v-if="canShowEvidence(agent.code)">依据</h4>
            <ul v-if="canShowEvidence(agent.code)" class="evidence-list">
              <li v-for="(line, index) in visibleEvidenceLines(agent.code)" :key="`${agent.code}-e-${index}`" :class="{ 'fade-in-item': shouldAnimate(agent.code) }" :style="{ '--i': index }">
                <TypewriterText v-if="isActiveEvidenceLine(agent.code, index)" :text="line" :speed="typewriterSpeed" @done="markEvidenceLineDone(agent.code)" />
                <span v-else>{{ line }}</span>
              </li>
            </ul>
            <h4 v-if="canShowSuggestion(agent.code)">建议</h4>
            <div v-if="canShowSuggestion(agent.code) && getHighlightPrice(agent.code) != null" class="result-strip">
              <span class="price-label">{{ getHighlightLabel(agent.code) }}</span>
              <span class="price-value"><span class="price-unit">¥</span><CountUp :value="getHighlightPrice(agent.code)" :duration="700" /></span>
            </div>
            <ul v-if="canShowSuggestion(agent.code)" class="suggestion-list">
              <li v-for="(line, index) in visibleSuggestionLines(agent.code)" :key="`${agent.code}-s-${index}`" :class="{ 'fade-in-item': shouldAnimate(agent.code) }" :style="{ '--i': index }">
                <TypewriterText v-if="isActiveSuggestionLine(agent.code, index)" :text="line" :speed="typewriterSpeed" @done="markSuggestionLineDone(agent.code)" />
                <span v-else>{{ line }}</span>
              </li>
            </ul>
            <template v-if="canShowReason(agent.code) && agent.code === 'MANAGER_COORDINATOR' && state.cards[agent.code]?.reasonWhy">
              <h4>为什么给出这个建议</h4>
              <TypewriterText v-if="isActiveReason(agent.code)" :text="state.cards[agent.code]?.reasonWhy || ''" :speed="typewriterSpeed" @done="markReasonDone(agent.code)" />
              <p v-else>{{ state.cards[agent.code]?.reasonWhy }}</p>
            </template>
          </template>
          <section v-else-if="isCardFailed(agent.code)" class="failed-card">
            <div class="failed-card-title">执行失败</div>
            <p class="failed-card-message">{{ getAgentFailureSummary(agent.code) }}</p>
          </section>
          <div v-else-if="isCardRunning(agent.code)" class="waiting running-pulse"><span class="pulse-dot"></span> 正在分析中...</div>
          <div v-else class="waiting">正在同步 Agent 输出...</div>
          </div>
        </article>
      </div>
    </section>

    <section v-else class="report-page">
      <div class="metric-grid">
        <div class="metric-card"><span>最终价格</span><strong><span class="price-unit">¥</span><CountUp :value="state.finalPrice" :duration="800" /></strong></div>
        <div class="metric-card"><span>预期销量</span><strong><CountUp v-if="expectedSales != null" :value="expectedSales" :decimals="0" :duration="700" /><template v-else>-</template></strong></div>
        <div class="metric-card"><span>预期利润</span><strong><span class="price-unit">¥</span><CountUp :value="expectedProfit" :duration="800" /></strong></div>
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
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { applyDecision, cancelPricingTask, createPricingTask, getPricingTaskSnapshot, getPricingTaskStreamUrl, type AgentCardContent, type DecisionComparisonItem, type DecisionLogItem, type PricingAgentCode, type PricingTaskSnapshot, type PricingTaskStatus, type PricingTaskStreamMessage } from '../api/decision'
import { getProductList } from '../api/product'
import { getLlmConfig } from '../api/llmConfig'
import { useShopStore } from '../stores/shop'
import { getAuthToken } from '../utils/authSession'
import { sanitizeErrorMessage } from '../utils/error'
import { getFailureSummary } from '../utils/failureSummary'
import { hasConfiguredLlmApiKey } from '../utils/llmConfigResponse'
import { clearRevealQueue, createRevealQueueState, finishReveal, isActiveReveal, queueRevealCardRequest } from '../utils/agentRevealQueue'
import { buildVisibleAgentTimeline, filterLatestAgentRunRound, resolveLatestAgentRunAttempt } from '../utils/agentTimeline'
import { formatEvidenceValue, getSuggestionLines, normalizeAgentCode, toNaturalChinese } from '../utils/decisionDisplay'
import { createDefaultPricingConstraintForm, serializePricingConstraints, validatePricingConstraintForm } from '../utils/pricingConstraints'
import { shouldKeepRevealEnabledAfterRefresh } from '../utils/revealRefresh'
import TypewriterText from '../components/TypewriterText.vue'
import CountUp from '../components/CountUp.vue'

interface ApiResponse<T> { code: number; data: T; message?: string }
interface ProductOption { id: number; productName: string }
type AgentStage = 'running' | 'completed' | 'failed'
type AgentRevealStage = 'thinking' | 'evidence' | 'suggestion' | 'reason' | 'done'
interface RevealLineCounts { evidence: number; suggestion: number }
type InternalAgentCardContent = AgentCardContent & { __stage?: AgentStage }
interface PendingRevealCard { card: AgentCardContent | null; stage: AgentStage }
interface SnapshotLoadOptions { applyLogs?: boolean }

const agents = [{ code: 'DATA_ANALYSIS', name: '数据分析Agent', order: 1 }, { code: 'MARKET_INTEL', name: '市场情报Agent', order: 2 }, { code: 'RISK_CONTROL', name: '风险控制Agent', order: 3 }, { code: 'MANAGER_COORDINATOR', name: '经理协调Agent', order: 4 }] as const
const agentRevealOrder = agents.map((agent) => agent.code) as PricingAgentCode[]
const goalOptions = [{ label: 'MAX_PROFIT', name: '利润优先' }, { label: 'CLEARANCE', name: '清仓促销' }, { label: 'MARKET_SHARE', name: '市场份额优先' }] as const
const emptyCards = () => ({ DATA_ANALYSIS: null, MARKET_INTEL: null, RISK_CONTROL: null, MANAGER_COORDINATOR: null }) as Record<PricingAgentCode, InternalAgentCardContent | null>
const typewriterSpeed = 24

const shopStore = useShopStore()
const router = useRouter()
const taskConfig = reactive({ platform: '', shopId: undefined as number | undefined, productId: undefined as number | undefined, strategyGoal: 'MAX_PROFIT' as typeof goalOptions[number]['label'] })
const constraintForm = reactive(createDefaultPricingConstraintForm())
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
const currentRunAttempt = ref<number | null>(null)
let aborter: AbortController | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null
let loadToken = 0
const liveRevealEnabled = ref(false)
const streamArrivedCards = reactive(new Set<PricingAgentCode>())
const revealQueue = reactive(createRevealQueueState<PricingAgentCode>())
const pendingRevealCards = reactive({} as Partial<Record<PricingAgentCode, PendingRevealCard>>)
const revealStages = reactive({} as Partial<Record<PricingAgentCode, AgentRevealStage>>)
const revealLineCounts = reactive({} as Partial<Record<PricingAgentCode, RevealLineCounts>>)

const normalizeCard = (card?: AgentCardContent | null, stage: AgentStage = 'completed'): InternalAgentCardContent => ({ thinking: String(card?.thinking || ''), evidence: Array.isArray(card?.evidence) ? card.evidence : [], suggestion: card?.suggestion && typeof card.suggestion === 'object' ? card.suggestion : {}, reasonWhy: card?.reasonWhy || null, __stage: stage })
const runningCard = (): InternalAgentCardContent => ({ thinking: '', evidence: [], suggestion: {}, reasonWhy: null, __stage: 'running' })
const failedCard = (card?: AgentCardContent | null): InternalAgentCardContent => normalizeCard(card, 'failed')
const isCardRunning = (code: PricingAgentCode) => state.cards[code]?.__stage === 'running'
const isCardFailed = (code: PricingAgentCode) => state.cards[code]?.__stage === 'failed'
const isCardCompleted = (code: PricingAgentCode) => state.cards[code]?.__stage === 'completed'
const isCardDone = (code: PricingAgentCode) => isCardCompleted(code) || isCardFailed(code)
const getAgentFailureSummary = (code: PricingAgentCode) => getFailureSummary(state.cards[code], '任务执行失败')
const shouldAnimate = (code: PricingAgentCode) => streamArrivedCards.has(code) && isActiveReveal(revealQueue, code)
const canShowEvidence = (code: PricingAgentCode) => !shouldAnimate(code) || revealStages[code] === 'evidence' || revealStages[code] === 'suggestion' || revealStages[code] === 'reason' || revealStages[code] === 'done'
const canShowSuggestion = (code: PricingAgentCode) => !shouldAnimate(code) || revealStages[code] === 'suggestion' || revealStages[code] === 'reason' || revealStages[code] === 'done'
const canShowReason = (code: PricingAgentCode) => !shouldAnimate(code) || revealStages[code] === 'reason' || revealStages[code] === 'done'
const completedCardCount = computed(() => agents.filter((agent) => isCardCompleted(agent.code)).length)

const platformOptions = computed(() => Array.from(new Set(shopStore.shops.map((shop) => String(shop.platform || '').trim()).filter(Boolean))))
const availableShops = computed(() => shopStore.shops.filter((shop) => shop.platform === taskConfig.platform))
const canSearchProducts = computed(() => Boolean(taskConfig.platform && taskConfig.shopId))
const productPlaceholder = computed(() => !taskConfig.platform ? '请先选择平台' : !taskConfig.shopId ? '请先选择店铺' : '输入商品名称搜索')
const canCancelTask = computed(() => Boolean(taskId.value && ['QUEUED', 'RUNNING', 'RETRYING'].includes(state.taskStatus)))
const canReconfigureTask = computed(() => state.taskStatus === 'CANCELLED')
const canViewReport = computed(() => ['COMPLETED', 'MANUAL_REVIEW'].includes(state.taskStatus) || completedCardCount.value === agents.length)
const canSkipReveal = computed(() => Boolean(taskId.value && activeStep.value === 1 && (liveRevealEnabled.value || hasRevealInProgress())))
const stepBarActive = computed(() => activeStep.value === 2 ? 3 : activeStep.value === 1 ? 2 : 1)
const statusLabel = computed(() => ({ IDLE: '未开始', PENDING: '待执行', QUEUED: '待执行', RUNNING: '执行中', RETRYING: '重试中', MANUAL_REVIEW: '人工审核', COMPLETED: '已完成', FAILED: '失败', CANCELLED: '已取消' }[state.taskStatus] || state.taskStatus))
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
const isArchivedTaskStatus = (status: PricingTaskStatus) => ['COMPLETED', 'MANUAL_REVIEW'].includes(status)
const stopPolling = () => { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }
const stopRealtime = () => { if (aborter) { aborter.abort(); aborter = null } stopPolling() }
const hasRevealInProgress = () => Boolean(revealQueue.active || revealQueue.queue.length)
const clearRevealState = () => { liveRevealEnabled.value = false; streamArrivedCards.clear(); clearRevealQueue(revealQueue); agents.forEach((agent) => { delete revealStages[agent.code]; delete revealLineCounts[agent.code]; delete pendingRevealCards[agent.code] }) }
const clearAgentRevealProgress = () => { streamArrivedCards.clear(); clearRevealQueue(revealQueue); agents.forEach((agent) => { delete revealStages[agent.code]; delete revealLineCounts[agent.code]; delete pendingRevealCards[agent.code] }) }
const toRunAttempt = (value: unknown): number | null => { const n = Number(value); return Number.isFinite(n) && n >= 0 ? n : null }
const syncStreamRunAttempt = (value: unknown) => {
  const attempt = toRunAttempt(value)
  if (attempt === null) return true
  if (currentRunAttempt.value !== null && attempt < currentRunAttempt.value) return false
  if (currentRunAttempt.value !== null && attempt > currentRunAttempt.value) {
    state.cards = emptyCards()
    clearAgentRevealProgress()
  }
  currentRunAttempt.value = attempt
  return true
}
const ensureRevealLineCounts = (code: PricingAgentCode) => {
  if (!revealLineCounts[code]) revealLineCounts[code] = { evidence: 0, suggestion: 0 }
  return revealLineCounts[code] as RevealLineCounts
}
const beginReveal = (code: PricingAgentCode) => { revealStages[code] = 'thinking'; revealLineCounts[code] = { evidence: 0, suggestion: 0 } }
const showCard = (code: PricingAgentCode, card: AgentCardContent | null, stage: AgentStage) => {
  state.cards[code] = stage === 'failed' ? failedCard(card) : normalizeCard(card, stage)
}
const activateQueuedReveal = (code: PricingAgentCode) => {
  const pending = pendingRevealCards[code]
  if (!pending) return
  delete pendingRevealCards[code]
  streamArrivedCards.add(code)
  beginReveal(code)
  showCard(code, pending.card, pending.stage)
  if (pending.stage === 'failed') completeReveal(code)
}
const queueStreamCard = (code: PricingAgentCode, card: AgentCardContent | null, stage: AgentStage) => {
  if (!liveRevealEnabled.value) {
    showCard(code, card, stage)
    return
  }
  const action = queueRevealCardRequest(revealQueue, pendingRevealCards, code, { card, stage }, agentRevealOrder)
  if (action === 'replace-active') {
    const pending = pendingRevealCards[code]
    if (!pending) return
    delete pendingRevealCards[code]
    streamArrivedCards.add(code)
    beginReveal(code)
    showCard(code, pending.card, pending.stage)
    if (pending.stage === 'failed') completeReveal(code)
    return
  }
  if (action === 'activate') activateQueuedReveal(code)
}
const completeReveal = (code: PricingAgentCode) => {
  revealStages[code] = 'done'
  streamArrivedCards.delete(code)
  const next = finishReveal(revealQueue, code)
  if (next) activateQueuedReveal(next)
}
const markThinkingDone = (code: PricingAgentCode) => {
  if (!shouldAnimate(code) || revealStages[code] !== 'thinking') return
  revealStages[code] = 'evidence'
  ensureRevealLineCounts(code).evidence = 1
}
const resetState = () => { stopRealtime(); clearRevealState(); taskId.value = null; currentRunAttempt.value = null; state.taskStatus = 'IDLE'; state.cards = emptyCards(); state.finalPrice = null; state.strategy = ''; state.finalSummary = ''; state.errorMessage = ''; comparisonData.value = []; archiveReportSummary.value = ''; streamArrivedCards.clear() }
const evidenceLines = (code: PricingAgentCode) => {
  const evidence = state.cards[code]?.evidence || []
  if (!evidence.length) return ['暂无依据']
  return evidence.map((item, index) => {
    const label = String(item.label || `依据${index + 1}`)
    return `${label}：${formatEvidenceValue(label, item.value)}`
  })
}
const suggestionLines = (code: PricingAgentCode) => {
  const suggestion = state.cards[code]?.suggestion && typeof state.cards[code]?.suggestion === 'object'
    ? state.cards[code]?.suggestion as Record<string, unknown>
    : {}
  const lines = getSuggestionLines(normalizeAgentCode(code), suggestion)
  if (code !== 'MARKET_INTEL') return lines
  const sourceStatus = String(suggestion.sourceStatus || '').toUpperCase()
  const dataQuality = String(suggestion.dataQuality || '').toUpperCase()
  const extra: string[] = []
  if (sourceStatus && sourceStatus !== 'OK') extra.push('提示：未获取到可靠竞品，市场建议已降级')
  else if (dataQuality === 'LOW') extra.push('提示：本次竞品数据不足，仅供参考')
  if (suggestion.pricingPosition) extra.push(`价格位置：${toNaturalChinese(suggestion.pricingPosition)}`)
  return [...lines, ...extra]
}
const visibleEvidenceLines = (code: PricingAgentCode) => {
  const lines = evidenceLines(code)
  if (!shouldAnimate(code) || revealStages[code] === 'suggestion' || revealStages[code] === 'done') return lines
  return lines.slice(0, Math.max(ensureRevealLineCounts(code).evidence, 1))
}
const visibleSuggestionLines = (code: PricingAgentCode) => {
  const lines = suggestionLines(code)
  if (!shouldAnimate(code) || revealStages[code] === 'done') return lines
  return lines.slice(0, Math.max(ensureRevealLineCounts(code).suggestion, 1))
}
const isActiveEvidenceLine = (code: PricingAgentCode, index: number) => shouldAnimate(code) && revealStages[code] === 'evidence' && index === visibleEvidenceLines(code).length - 1
const isActiveSuggestionLine = (code: PricingAgentCode, index: number) => shouldAnimate(code) && revealStages[code] === 'suggestion' && index === visibleSuggestionLines(code).length - 1
const markEvidenceLineDone = (code: PricingAgentCode) => {
  if (!shouldAnimate(code) || revealStages[code] !== 'evidence') return
  const counts = ensureRevealLineCounts(code)
  if (counts.evidence < evidenceLines(code).length) {
    counts.evidence += 1
    return
  }
  revealStages[code] = 'suggestion'
  counts.suggestion = 1
}
const markSuggestionLineDone = (code: PricingAgentCode) => {
  if (!shouldAnimate(code) || revealStages[code] !== 'suggestion') return
  const counts = ensureRevealLineCounts(code)
  if (counts.suggestion < suggestionLines(code).length) {
    counts.suggestion += 1
    return
  }
  if (code === 'MANAGER_COORDINATOR' && state.cards[code]?.reasonWhy) {
    revealStages[code] = 'reason'
    return
  }
  completeReveal(code)
}
const agentRoleLabel: Record<PricingAgentCode, string> = { DATA_ANALYSIS: '数据判断', MARKET_INTEL: '市场判断', RISK_CONTROL: '风险校验', MANAGER_COORDINATOR: '最终协调' }
const visibleAgents = computed(() => buildVisibleAgentTimeline(agents, state.cards))
const agentIcon: Record<PricingAgentCode, string> = { DATA_ANALYSIS: '数', MARKET_INTEL: '市', RISK_CONTROL: '控', MANAGER_COORDINATOR: '协' }
const getHighlightPrice = (code: PricingAgentCode): number | null => {
  const s = state.cards[code]?.suggestion && typeof state.cards[code]?.suggestion === 'object' ? state.cards[code]!.suggestion as Record<string, unknown> : {}
  const raw = code === 'MANAGER_COORDINATOR' ? s.finalPrice : s.recommendedPrice
  const n = Number(raw)
  return Number.isFinite(n) && n > 0 ? n : null
}
const getHighlightLabel = (code: PricingAgentCode) => code === 'MANAGER_COORDINATOR' ? '最终建议价' : code === 'RISK_CONTROL' ? '风控建议价' : '建议定价'
const isActiveReason = (code: PricingAgentCode) => shouldAnimate(code) && revealStages[code] === 'reason'
const markReasonDone = (code: PricingAgentCode) => {
  if (!isActiveReason(code)) return
  completeReveal(code)
}

const onPlatformChange = async () => { taskConfig.shopId = undefined; taskConfig.productId = undefined; productOptions.value = []; if (availableShops.value.length === 1) { taskConfig.shopId = availableShops.value[0].id; await loadProducts() } }
const onShopChange = async () => { taskConfig.productId = undefined; productOptions.value = []; if (taskConfig.shopId) await loadProducts() }
const searchProducts = (keyword: string) => { void loadProducts(keyword) }
const loadProducts = async (keyword = '') => { const token = ++loadToken; if (!canSearchProducts.value) return; searchLoading.value = true; try { const res = await getProductList({ page: 1, size: 100, keyword, platform: taskConfig.platform || undefined, shopId: taskConfig.shopId }) as ApiResponse<{ records: Array<{ id: number; productName: string }> }>; if (token !== loadToken) return; productOptions.value = Array.isArray(res.data?.records) ? res.data.records.map((item) => ({ id: Number(item.id), productName: String(item.productName || '') })) : [] } finally { if (token === loadToken) searchLoading.value = false } }

const applySnapshotDetail = (detail?: PricingTaskSnapshot['detail'] | null) => { if (!detail) return; state.taskStatus = (detail.taskStatus || 'RUNNING') as PricingTaskStatus; state.finalPrice = detail.finalPrice != null ? Number(detail.finalPrice) : null; state.strategy = String(detail.strategy || ''); state.finalSummary = String(detail.finalSummary || '') }
const applySnapshotLogs = (logs: DecisionLogItem[]) => {
  clearRevealState()
  const cards = emptyCards()
  const latestLogs = filterLatestAgentRunRound(logs)
  currentRunAttempt.value = resolveLatestAgentRunAttempt(latestLogs)
  latestLogs.sort((a, b) => Number(a.displayOrder || a.runOrder || 0) - Number(b.displayOrder || b.runOrder || 0) || Number(a.id || 0) - Number(b.id || 0)).forEach((log) => {
    const code = String(log.agentCode || '') as PricingAgentCode
    if (!(code in cards)) return
    const stage = log.stage === 'running' ? 'running' : log.stage === 'failed' ? 'failed' : 'completed'
    if (stage === 'running') {
      if (!cards[code]) cards[code] = runningCard()
      return
    }
    const cardPayload = { thinking: String(log.thinking || log.outputSummary || ''), evidence: log.evidence || [], suggestion: log.suggestion || {}, reasonWhy: log.reasonWhy || null }
    cards[code] = stage === 'failed' ? failedCard(cardPayload) : normalizeCard(cardPayload)
  })
  state.cards = cards
}
const applySnapshotComparison = (comparison: DecisionComparisonItem[]) => { comparisonData.value = comparison; archiveReportSummary.value = comparisonData.value.find((row) => String(row.resultSummary || '').trim())?.resultSummary || '' }
const loadSnapshot = async (id: number, options: SnapshotLoadOptions = {}) => {
  const res = await getPricingTaskSnapshot(id) as ApiResponse<PricingTaskSnapshot>
  if (res.code !== 200 || !res.data) return
  applySnapshotDetail(res.data.detail)
  if (options.applyLogs !== false) applySnapshotLogs(Array.isArray(res.data.logs) ? res.data.logs : [])
  applySnapshotComparison(Array.isArray(res.data.comparison) ? res.data.comparison : [])
}
const skipRevealAnimation = async () => {
  liveRevealEnabled.value = false
  if (taskId.value) await loadSnapshot(taskId.value)
  ElMessage.info('已切换为静态进度快照')
}
const openExistingTaskArchive = async (id: number) => {
  ElMessage.info('该任务已经执行过，已为你打开决策档案详情')
  await router.push({ path: '/archive', query: { taskId: String(id) } })
}

const handleStream = async (payload: PricingTaskStreamMessage) => {
  if (payload.type === 'task_started') state.taskStatus = (payload.status || 'RUNNING') as PricingTaskStatus
  if (payload.type === 'agent_card') {
    const code = payload.agentCode as PricingAgentCode
    if (!syncStreamRunAttempt(payload.runAttempt)) return
    if (code in state.cards) {
      if (payload.stage === 'running') {
        if (!state.cards[code]) state.cards[code] = runningCard()
      } else {
        queueStreamCard(code, payload.card, payload.stage === 'failed' ? 'failed' : 'completed')
      }
    }
  }
  if (payload.type === 'task_completed') {
    state.taskStatus = (payload.status || 'COMPLETED') as PricingTaskStatus
    liveRevealEnabled.value = false
    if (payload.result) {
      state.finalPrice = numberOf(payload.result.finalPrice)
      state.strategy = String(payload.result.strategy || state.strategy || '')
      state.finalSummary = String(payload.result.summary || state.finalSummary || '')
    }
    if (taskId.value) await loadSnapshot(taskId.value, { applyLogs: !hasRevealInProgress() })
    stopRealtime()
    ElMessage[state.taskStatus === 'MANUAL_REVIEW' ? 'warning' : 'success'](state.taskStatus === 'MANUAL_REVIEW' ? '任务已完成，当前结果需要人工审核' : '智能决策已完成，可以查看结果报告')
  }
  if (payload.type === 'task_failed') {
    state.taskStatus = (payload.status || 'FAILED') as PricingTaskStatus
    liveRevealEnabled.value = false
    state.errorMessage = sanitizeErrorMessage(payload.message, state.taskStatus === 'CANCELLED' ? '任务已取消' : '任务执行失败')
    if (taskId.value) await loadSnapshot(taskId.value, { applyLogs: !hasRevealInProgress() })
    stopRealtime()
    ElMessage[state.taskStatus === 'CANCELLED' || state.taskStatus === 'MANUAL_REVIEW' ? 'warning' : 'error'](state.errorMessage)
  }
}

const startPolling = () => {
  if (pollTimer || !taskId.value) return
  pollTimer = setInterval(async () => {
    if (!taskId.value) return
    if (!isRunning(state.taskStatus)) {
      stopRealtime()
      return
    }
    await loadSnapshot(taskId.value, { applyLogs: !liveRevealEnabled.value && !hasRevealInProgress() })
    if (isTerminal(state.taskStatus)) {
      if (liveRevealEnabled.value || hasRevealInProgress()) stopPolling()
      else stopRealtime()
    }
  }, 2000)
}
const startStream = async (id: number) => {
  stopRealtime()
  const controller = new AbortController()
  aborter = controller
  try {
    const response = await fetch(getPricingTaskStreamUrl(id), { method: 'GET', headers: { Accept: 'text/event-stream', Authorization: `Bearer ${getAuthToken()}` }, credentials: 'include', signal: controller.signal })
    if (!response.ok || !response.body) throw new Error('stream failed')
    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const chunks = buffer.split('\n\n')
      buffer = chunks.pop() || ''
      for (const chunk of chunks) {
        const data = chunk.split('\n').filter((line) => line.startsWith('data:')).map((line) => line.slice(5).trim()).join('\n')
        if (!data) continue
        try { await handleStream(JSON.parse(data) as PricingTaskStreamMessage) } catch {}
      }
    }
  } catch {
    if (!controller.signal.aborted && taskId.value) {
      clearRevealState()
      await loadSnapshot(taskId.value)
    }
  } finally {
    if (aborter === controller) aborter = null
  }
}

const startTask = async () => {
  if (!taskConfig.platform) return ElMessage.warning('请选择平台')
  if (!taskConfig.shopId) return ElMessage.warning('请选择店铺')
  if (!taskConfig.productId) return ElMessage.warning('请选择一个商品')
  const constraintError = validatePricingConstraintForm(constraintForm)
  if (constraintError) return ElMessage.warning(constraintError)
  const constraints = serializePricingConstraints(constraintForm)
  starting.value = true
  try {
    resetState()
    state.taskStatus = 'QUEUED'
    const res = await createPricingTask({ productId: taskConfig.productId, constraints, strategyGoal: taskConfig.strategyGoal }) as ApiResponse<number>
    if (res.code !== 200 || !res.data) {
      state.taskStatus = 'FAILED'
      state.errorMessage = sanitizeErrorMessage(res.message, '启动任务失败')
      return ElMessage.error(state.errorMessage)
    }
    taskId.value = Number(res.data)
    await loadSnapshot(taskId.value, { applyLogs: false })
    if (isArchivedTaskStatus(state.taskStatus)) {
      await openExistingTaskArchive(taskId.value)
      return
    }
    liveRevealEnabled.value = true
    activeStep.value = 1
    void startStream(taskId.value)
    startPolling()
    ElMessage.success('任务已启动，进入智能决策阶段')
  } catch {
    state.taskStatus = 'FAILED'
    state.errorMessage = '启动任务失败'
    ElMessage.error(state.errorMessage)
  } finally {
    starting.value = false
  }
}
const cancelTask = async () => { if (!taskId.value || !canCancelTask.value) return; try { await ElMessageBox.confirm('确认取消当前任务吗？', '取消任务', { type: 'warning', confirmButtonText: '确认取消', cancelButtonText: '继续执行' }); await loadSnapshot(taskId.value); if (!['QUEUED', 'RUNNING', 'RETRYING'].includes(state.taskStatus)) return ElMessage.warning(`当前任务状态为 ${statusLabel.value}，不支持取消`); const res = await cancelPricingTask(taskId.value); if (res.code !== 200) return ElMessage.error(sanitizeErrorMessage(res.message, '取消任务失败')); stopRealtime(); state.taskStatus = 'CANCELLED'; state.errorMessage = '任务已取消'; await loadSnapshot(taskId.value); ElMessage.warning('任务已取消') } catch (error) { if (error !== 'cancel') ElMessage.error('取消任务失败') } }
const refreshSnapshot = async () => {
  if (!taskId.value) return
  const wasRevealEnabled = liveRevealEnabled.value
  clearRevealState()
  await loadSnapshot(taskId.value)
  liveRevealEnabled.value = shouldKeepRevealEnabledAfterRefresh(state.taskStatus, wasRevealEnabled)
  if (isRunning(state.taskStatus) && !aborter) void startStream(taskId.value)
  if (isRunning(state.taskStatus)) startPolling()
  ElMessage.success(`已刷新快照，当前已完成 ${completedCardCount.value}/4 条分析结果`)
}
const resetTask = () => { resetState(); activeStep.value = 0 }
const applyPrice = async (row: DecisionComparisonItem) => { const id = Number(row.resultId || 0); if (!id) return ElMessage.error('未找到可应用的结果记录'); try { await ElMessageBox.confirm(`确认将商品“${String(row.productTitle || '-')}”的售价更新为 ${currency(row.suggestedPrice)} 吗？`, '应用价格建议', { type: 'warning', confirmButtonText: '确认应用', cancelButtonText: '取消' }); applyingIds.value.push(id); const res = await applyDecision(id); if (res.code !== 200) return ElMessage.error(sanitizeErrorMessage(res.message, '应用失败')); ElMessage.success('价格建议已应用'); if (taskId.value) await loadSnapshot(taskId.value) } catch (error) { if (error !== 'cancel') ElMessage.error('应用失败') } finally { applyingIds.value = applyingIds.value.filter((item) => item !== id) } }

onMounted(async () => { getLlmConfig().then((response) => { hasLlmConfig.value = hasConfiguredLlmApiKey(response) }).catch(() => { hasLlmConfig.value = false }); const loaded = await shopStore.fetchShops(); if (loaded && platformOptions.value.length === 1) { taskConfig.platform = platformOptions.value[0]; await onPlatformChange() } })
onBeforeUnmount(() => { stopRealtime(); clearRevealState() })
</script>

<style scoped>
.llm-alert{margin-bottom:16px}
.alert-link{color:#409eff;text-decoration:underline;margin-left:4px}
.pricing-page{display:grid;gap:16px}
.panel-card{padding:18px;border-radius:16px;background:#fff;border:1px solid rgba(15,23,42,.08);box-shadow:0 10px 30px rgba(15,23,42,.05)}
.section-head{display:flex;justify-content:space-between;gap:16px;margin-bottom:16px}
.section-head h2{margin:0 0 6px;font-size:28px;color:#172033}
.section-head p{margin:0;color:#6b7280}
.config-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0 14px}
.full-span{grid-column:1/-1}
.toolbar{display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap}
.constraint-panel{width:100%;display:grid;gap:14px;padding:14px 16px;border:1px solid #e2e8f0;border-radius:8px;background:#f8fafc}
.constraint-intro{display:flex;justify-content:space-between;align-items:center;gap:12px;color:#64748b;line-height:1.6}
.constraint-intro strong{font-size:14px;color:#172033}
.constraint-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.constraint-field,.constraint-switch{min-width:0;padding:12px;border:1px solid #e2e8f0;border-radius:8px;background:#fff}
.constraint-field{display:grid;gap:8px}
.constraint-label{display:block;font-size:13px;font-weight:700;color:#334155;line-height:1.4}
.constraint-control{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:8px}
.constraint-control :deep(.el-input-number){width:100%}
.constraint-unit{font-size:13px;font-weight:700;color:#64748b}
.constraint-switch{grid-column:1/-1;display:flex;justify-content:space-between;align-items:center;gap:16px}
.constraint-switch small{display:block;margin-top:4px;font-size:12px;color:#64748b;line-height:1.5}

/* ========== Agent decision chat ========== */
.decision-chat-panel{background:#f8fafc;border-color:#e2e8f0;box-shadow:none}
.decision-chat-head{align-items:flex-start;padding-bottom:14px;margin-bottom:16px;border-bottom:1px solid #e2e8f0}
.decision-chat-title{display:grid;gap:4px;min-width:0}
.decision-chat-title h2{margin:0;font-size:24px;color:#0f172a}
.decision-chat-title p{margin:0;color:#64748b;line-height:1.6}
.decision-chat-kicker{width:fit-content;font-size:12px;font-weight:700;color:#1f6feb;background:rgba(31,111,235,.09);border:1px solid rgba(31,111,235,.12);border-radius:8px;padding:3px 8px}
.decision-toolbar{align-items:center}

.agent-stream-empty{min-height:220px;display:grid;place-items:center;text-align:center;padding:34px 18px;border:1px solid #e2e8f0;border-radius:8px;background:#fff;color:#475569}
.agent-stream-empty h3{margin:14px 0 6px;font-size:19px;color:#0f172a}
.agent-stream-empty p{margin:0;line-height:1.7;color:#64748b}
.agent-stream-pulse{display:flex;align-items:center;justify-content:center;gap:6px;height:26px}
.agent-stream-pulse span{width:6px;height:6px;border-radius:50%;background:#1f6feb;animation:typing-dot 1s ease-in-out infinite}
.agent-stream-pulse span:nth-child(2){animation-delay:.12s}
.agent-stream-pulse span:nth-child(3){animation-delay:.24s}

.agent-list{display:grid;gap:14px}
.agent-box{--agent-color:#1f6feb;display:grid;grid-template-columns:34px minmax(0,1fr);gap:12px;align-items:start;animation:agent-enter .26s ease-out both}
.agent-message{min-width:0;padding:16px 18px;border:1px solid #e2e8f0;border-radius:8px;background:#fff;box-shadow:0 1px 2px rgba(15,23,42,.04)}
.agent-box.is-streaming .agent-message{border-color:rgba(31,111,235,.22)}
.agent-avatar{width:34px;height:34px;border-radius:8px;background:#eff6ff;color:#1d4ed8;border:1px solid #dbeafe;display:grid;place-items:center;font-size:14px;font-weight:700;line-height:1;flex-shrink:0}

.agent-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:12px}
.agent-identity{display:flex;align-items:flex-start;gap:12px;min-width:0}
.agent-title{display:flex;flex-direction:column;gap:4px;min-width:0}
.agent-title h3{margin:0;font-size:16px;font-weight:700;color:#0f172a;letter-spacing:0}
.agent-role{display:inline-block;width:fit-content;font-size:12px;font-weight:600;color:#64748b;background:#f8fafc;border:1px solid #e2e8f0;padding:2px 8px;border-radius:8px;line-height:1.5}

.agent-box h4{margin:14px 0 8px;font-size:13px;font-weight:700;color:#334155;letter-spacing:0}
.thinking{white-space:pre-wrap;line-height:1.8;color:#475569;font-size:14px;margin:0}

.evidence-list,.suggestion-list{margin:0;padding:0;list-style:none;display:grid;gap:8px}
.evidence-list li,.suggestion-list li{padding:9px 11px;background:#f8fafc;border:1px solid #edf2f7;border-radius:8px;line-height:1.65;color:#334155;font-size:14px}

.result-strip{margin:6px 0 10px;padding:12px 14px;border-radius:8px;background:#f8fafc;border:1px solid #dbeafe;display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.price-label{font-size:13px;color:#64748b;font-weight:600}
.price-value{font-size:26px;font-weight:800;color:#1f6feb;letter-spacing:0;font-variant-numeric:tabular-nums;line-height:1}
.price-unit{font-size:16px;font-weight:600;opacity:.7;margin-right:3px}

.failed-card{display:grid;gap:8px;padding:12px 14px;border-radius:8px;border:1px solid #fecaca;background:#fef2f2}
.failed-card-title{font-size:14px;font-weight:700;color:#b42318}
.failed-card-message{margin:0;line-height:1.7;color:#7a271a}
.waiting{min-height:104px;display:grid;place-items:center;color:#94a3b8}
.running-pulse{display:flex;align-items:center;justify-content:center;gap:10px;color:#1f6feb;font-size:14px;font-weight:600}
.pulse-dot{width:8px;height:8px;border-radius:50%;background:#1f6feb;animation:pulse 1.2s ease-in-out infinite}

.fade-in-item{opacity:0;animation:fadeSlideIn .38s cubic-bezier(.16,1,.3,1) forwards;animation-delay:calc(var(--i, 0) * 60ms)}

@keyframes agent-enter{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
@keyframes pulse{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(1.6);opacity:.4}}
@keyframes fadeSlideIn{from{opacity:0;transform:translateX(-6px)}to{opacity:1;transform:translateX(0)}}
@keyframes typing-dot{0%,80%,100%{opacity:.35;transform:translateY(0)}40%{opacity:1;transform:translateY(-4px)}}

/* ========== Report page ========== */
.report-page,.metric-grid{display:grid;gap:14px}
.metric-grid{grid-template-columns:repeat(4,minmax(0,1fr))}
.metric-card{padding:20px;border-radius:14px;background:#fff;border:1px solid rgba(15,23,42,.06);box-shadow:0 1px 2px rgba(15,23,42,.04),0 10px 30px rgba(15,23,42,.05);display:grid;gap:10px;transition:box-shadow .25s ease,transform .25s ease}
.metric-card:hover{transform:translateY(-2px);box-shadow:0 2px 4px rgba(15,23,42,.06),0 16px 40px rgba(15,23,42,.08)}
.metric-card span{font-size:13px;color:#64748b;font-weight:500}
.metric-card strong{font-size:26px;color:#0f172a;font-weight:700;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
@media (max-width:1100px){.config-grid,.metric-grid,.constraint-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:760px){.config-grid,.metric-grid,.constraint-grid{grid-template-columns:1fr}.constraint-intro,.constraint-switch,.section-head,.agent-head{flex-direction:column;align-items:flex-start}.toolbar{justify-content:flex-start}.agent-box{grid-template-columns:30px minmax(0,1fr);gap:10px}.agent-avatar{width:30px;height:30px}.result-strip{flex-direction:column;align-items:flex-start;gap:4px}}
@media (prefers-reduced-motion:reduce){.agent-box,.metric-card,.fade-in-item,.pulse-dot,.agent-stream-pulse span{animation:none!important;transition:none!important}.metric-card:hover{transform:none}}
</style>

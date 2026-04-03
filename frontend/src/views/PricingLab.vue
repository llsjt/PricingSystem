<template>
  <div class="page-shell pricing-page">
    <section class="panel-card step-panel">
      <div class="section-head">
        <div class="section-title">
          <h3>任务流程</h3>
          <p>配置任务、智能决策、结果报告。</p>
        </div>
      </div>

      <el-steps :active="stepBarActive" finish-status="success" align-center class="steps">
        <el-step title="配置任务" />
        <el-step title="智能决策" />
        <el-step title="结果报告" />
      </el-steps>
    </section>

    <div v-if="activeStep === 0" class="responsive-two">
      <section class="panel-card config-panel">
        <div class="section-head">
          <div class="section-title">
            <h3>任务配置</h3>
            <p>选择商品并设置目标与约束后，系统会自动启动多 Agent 决策。</p>
          </div>
        </div>

        <el-form :model="taskConfig" label-position="top" class="config-form">
          <el-form-item label="选择商品">
            <el-select
              v-model="taskConfig.productId"
              filterable
              remote
              reserve-keyword
              placeholder="输入商品名称搜索"
              :remote-method="searchProducts"
              :loading="searchLoading"
            >
              <el-option v-for="item in productOptions" :key="item.id" :label="item.productName" :value="item.id">
                <div class="option-row">
                  <span>{{ item.productName }}</span>
                  <span class="option-id">ID {{ item.id }}</span>
                </div>
              </el-option>
            </el-select>
          </el-form-item>

          <el-form-item label="策略目标">
            <el-radio-group v-model="taskConfig.strategyGoal" class="goal-group">
              <el-radio label="MAX_PROFIT" border>利润优先</el-radio>
              <el-radio label="CLEARANCE" border>清仓促销</el-radio>
              <el-radio label="MARKET_SHARE" border>市场份额优先</el-radio>
            </el-radio-group>
          </el-form-item>

          <el-form-item label="约束条件">
            <el-input
              v-model="taskConfig.constraints"
              type="textarea"
              :rows="4"
              placeholder="例如：利润率不低于15%，降价幅度不超过10%，最低售价不低于69元"
            />
          </el-form-item>

          <div class="toolbar-actions">
            <el-button :loading="starting" type="primary" size="large" @click="startTask">启动任务</el-button>
          </div>
        </el-form>
      </section>

      <section class="panel-card helper-panel">
        <div class="section-head">
          <div class="section-title">
            <h3>配置摘要</h3>
            <p>确认本次任务的关键参数。</p>
          </div>
        </div>

        <div class="summary-card">
          <div class="summary-line">商品：{{ selectedProductName || '尚未选择' }}</div>
          <div class="summary-line">目标：{{ strategyGoalText }}</div>
          <div class="summary-line">约束：{{ taskConfig.constraints || '未设置' }}</div>
        </div>

        <div class="tips-list">
          <article class="tip-item">
            <strong>利润优先</strong>
            <span>优先拉升单件收益，但仍会受风控底线约束。</span>
          </article>
          <article class="tip-item">
            <strong>清仓促销</strong>
            <span>优先提升销量，价格会更接近市场下沿。</span>
          </article>
          <article class="tip-item">
            <strong>市场份额优先</strong>
            <span>在可控利润范围内争取更高市场接受度。</span>
          </article>
        </div>
      </section>
    </div>

    <div v-else-if="activeStep === 1" class="decision-layout">
      <section class="panel-card agent-stream-panel">
        <div class="section-head">
          <div class="section-title">
            <h3>多Agent决策</h3>
            <p>以下内容按 1 → 4 顺序流式展示，滚动即可查看完整过程。</p>
          </div>
          <div class="toolbar-actions">
            <el-button type="primary" :disabled="!canViewReport" @click="goToReport">查看结果报告</el-button>
          </div>
        </div>

        <div class="agent-stream-scroll">
          <article v-for="meta in agentOrder" :key="meta.code" class="agent-card stream-card">
          <div class="card-head">
            <h3>{{ meta.order }}. {{ meta.name }}</h3>
            <el-tag
              size="small"
              :type="typingStates[meta.code]?.thinkingDone ? 'success' : taskState.cards[meta.code] ? 'warning' : 'info'"
            >
              {{ typingStates[meta.code]?.thinkingDone ? '已完成' : taskState.cards[meta.code] ? '思考中...' : '等待中' }}
            </el-tag>
          </div>

          <div v-if="taskState.cards[meta.code]" class="card-body">
            <!-- 思考过程：逐字流式输出 -->
            <section class="card-section">
              <h4>思考过程</h4>
              <p class="typing-text">
                <span>{{ typingStates[meta.code]?.thinkingText || '' }}</span>
                <span v-if="!typingStates[meta.code]?.thinkingDone" class="typing-cursor"></span>
              </p>
            </section>

            <!-- 依据：思考完成后淡入展开 -->
            <transition name="card-fade">
              <section v-if="typingStates[meta.code]?.showEvidence" class="card-section">
                <h4>依据</h4>
                <ul class="info-list">
                  <li v-for="(item, idx) in taskState.cards[meta.code]?.evidence || []" :key="idx">
                    <strong>{{ String(item.label || `依据${idx + 1}`) }}：</strong>
                    <span>{{ formatEvidenceValue(item.label, item.value) }}</span>
                  </li>
                </ul>
              </section>
            </transition>

            <!-- 建议：依据展示后淡入展开 -->
            <transition name="card-fade">
              <section v-if="typingStates[meta.code]?.showSuggestion" class="card-section">
                <h4>建议</h4>
                <ul class="info-list">
                  <li v-for="(line, index) in getSuggestionLines(meta.code, taskState.cards[meta.code]?.suggestion)" :key="index">
                    {{ line }}
                  </li>
                </ul>
              </section>
            </transition>

            <!-- 经理Agent：决策理由 -->
            <transition name="card-fade">
              <section v-if="meta.code === 'MANAGER_COORDINATOR' && typingStates[meta.code]?.showReason" class="card-section">
                <h4>为什么给出这个建议</h4>
                <p>{{ taskState.cards[meta.code]?.reasonWhy || '-' }}</p>
              </section>
            </transition>
          </div>

          <!-- 等待状态：当前正在处理的 Agent 显示加载动画 -->
          <div v-else-if="taskState.taskStatus === 'RUNNING' && meta.order === streamCursor" class="waiting-active">
            <div class="thinking-dots">
              <span></span><span></span><span></span>
            </div>
            <p class="waiting-text">正在分析中，请稍候...</p>
          </div>
          <el-empty v-else description="等待该 Agent 输出卡片" :image-size="80" />
          </article>
        </div>
      </section>
    </div>

    <div v-else class="report-layout">
      <section class="metric-grid">
        <article class="metric-card">
          <div class="metric-label">最终价格</div>
          <div class="metric-value">{{ formatCurrency(taskState.finalPrice) }}</div>
        </article>
        <article class="metric-card">
          <div class="metric-label">预期销量</div>
          <div class="metric-value">{{ reportExpectedSales ?? '-' }}</div>
        </article>
        <article class="metric-card">
          <div class="metric-label">预期利润</div>
          <div class="metric-value">{{ formatCurrency(reportExpectedProfit) }}</div>
        </article>
        <article class="metric-card">
          <div class="metric-label">执行策略</div>
          <div class="metric-value strategy-value">{{ reportStrategy || '-' }}</div>
        </article>
      </section>

      <section class="panel-card report-panel">
        <div class="section-head">
          <div class="section-title">
            <h3>结果报告</h3>
            <p>最终建议由 4 个 Agent 的分析结果综合得出。</p>
          </div>
          <div class="toolbar-actions">
            <el-button @click="goToDecision">查看智能决策过程</el-button>
            <el-button type="primary" @click="goToConfig">重新配置任务</el-button>
          </div>
        </div>

        <div class="report-table">
          <el-table :data="comparisonData" border stripe>
            <el-table-column prop="productTitle" label="商品名称" min-width="180" show-overflow-tooltip />
            <el-table-column label="原价" width="120">
              <template #default="{ row }">{{ formatCurrency(row.originalPrice) }}</template>
            </el-table-column>
            <el-table-column label="建议价" width="120">
              <template #default="{ row }">
                <span class="price-text" style="color: #ff9900; font-weight: bold;">{{ formatCurrency(row.suggestedPrice) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="预期销量" width="110">
              <template #default="{ row }">{{ row.expectedSales || 0 }}</template>
            </el-table-column>
            <el-table-column label="预期利润" width="120">
              <template #default="{ row }">{{ formatCurrency(row.expectedProfit) }}</template>
            </el-table-column>
            <el-table-column label="利润变化" width="120">
              <template #default="{ row }">
                <el-tag :type="Number(row.profitChange || 0) >= 0 ? 'success' : 'danger'" effect="light">
                  {{ formatSignedCurrency(row.profitChange) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="passStatus" label="风控结果" width="110" />
            <el-table-column prop="executeStrategy" label="执行策略" width="120" />
            <el-table-column label="应用状态" width="110">
              <template #default="{ row }">
                <el-tag :type="row.appliedStatus === '已应用' ? 'success' : 'info'" effect="light">
                  {{ row.appliedStatus || '未应用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-tag v-if="row.appliedStatus === '已应用'" type="success" effect="light">已应用</el-tag>
                <el-button
                  v-else
                  type="primary"
                  link
                  :loading="applyingResultIds.includes(Number(row.resultId))"
                  @click="applyPrice(row)"
                >
                  应用建议
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  applyDecision,
  createPricingTask,
  getTaskComparison,
  getPricingTaskDetail,
  getPricingTaskLogs,
  getPricingTaskWebSocketUrl,
  type AgentCardContent,
  type DecisionComparisonItem,
  type DecisionLogItem,
  type PricingAgentCardMessage,
  type PricingAgentCode,
  type PricingTaskCompletedMessage,
  type PricingTaskDetail,
  type PricingTaskFailedMessage,
  type PricingTaskStartedMessage,
  type PricingTaskStatus,
  type PricingWsMessage
} from '../api/decision'
import { getProductList } from '../api/product'
import { createApplyDecisionConfirmMessage, formatEvidenceValue, getSuggestionLines } from '../utils/decisionDisplay'
import { formatCurrency as sharedFormatCurrency, formatSignedCurrency as sharedFormatSignedCurrency } from '../utils/formatters'

interface ApiResponse<T> {
  code: number
  data: T
  message?: string
}

interface ProductOption {
  id: number
  productName: string
}

interface AgentOrderItem {
  code: PricingAgentCode
  name: string
  order: number
}

interface EvidenceItem {
  label?: unknown
  value?: unknown
}

interface StreamCardItem {
  order: number
  code: PricingAgentCode
  card: AgentCardContent
}

interface PricingPageState {
  taskStatus: PricingTaskStatus
  cards: Record<PricingAgentCode, AgentCardContent | null>
  finalPrice: number | null
  strategy: string
  finalSummary: string
  errorMessage: string
}

const EMPTY_CARDS = (): Record<PricingAgentCode, AgentCardContent | null> => ({
  DATA_ANALYSIS: null,
  MARKET_INTEL: null,
  RISK_CONTROL: null,
  MANAGER_COORDINATOR: null
})

const agentOrder: AgentOrderItem[] = [
  { code: 'DATA_ANALYSIS', name: '数据分析Agent', order: 1 },
  { code: 'MARKET_INTEL', name: '市场情报Agent', order: 2 },
  { code: 'RISK_CONTROL', name: '风险控制Agent', order: 3 },
  { code: 'MANAGER_COORDINATOR', name: '经理协调Agent', order: 4 }
]

const taskConfig = reactive({
  productId: undefined as number | undefined,
  strategyGoal: 'MAX_PROFIT',
  constraints: ''
})

const taskState = reactive<PricingPageState>({
  taskStatus: 'IDLE',
  cards: EMPTY_CARDS(),
  finalPrice: null,
  strategy: '',
  finalSummary: '',
  errorMessage: ''
})

const productOptions = ref<ProductOption[]>([])
const searchLoading = ref(false)
const starting = ref(false)
const currentTaskId = ref<number | null>(null)
const activeStep = ref(0)
const archiveReportSummary = ref('')
const comparisonData = ref<DecisionComparisonItem[]>([])
const applyingResultIds = ref<number[]>([])

let latestProductLoadToken = 0
let wsClient: WebSocket | null = null
let streamLoopRunning = false
let streamToken = 0

const pendingCards = reactive<Record<number, StreamCardItem | null>>({
  1: null,
  2: null,
  3: null,
  4: null
})
const streamCursor = ref(1)

// ── 流式打字机效果 ──────────────────────────────────────────
interface TypingState {
  thinkingText: string       // 当前显示的思考文字（逐字递增）
  thinkingDone: boolean      // 思考打字完成
  showEvidence: boolean      // 是否显示依据区块
  showSuggestion: boolean    // 是否显示建议区块
  showReason: boolean        // 是否显示理由区块（经理Agent）
}

const EMPTY_TYPING = (): TypingState => ({
  thinkingText: '',
  thinkingDone: false,
  showEvidence: false,
  showSuggestion: false,
  showReason: false
})

const typingStates = reactive<Record<PricingAgentCode, TypingState>>({
  DATA_ANALYSIS: EMPTY_TYPING(),
  MARKET_INTEL: EMPTY_TYPING(),
  RISK_CONTROL: EMPTY_TYPING(),
  MANAGER_COORDINATOR: EMPTY_TYPING()
})

// 保存 typing interval ID，方便清理
const typingTimerIds: Record<string, ReturnType<typeof setInterval> | null> = {
  DATA_ANALYSIS: null,
  MARKET_INTEL: null,
  RISK_CONTROL: null,
  MANAGER_COORDINATOR: null
}

// 清理某个 Agent 的打字定时器
const clearTypingTimer = (code: string) => {
  if (typingTimerIds[code]) {
    clearInterval(typingTimerIds[code]!)
    typingTimerIds[code] = null
  }
}

// 启动打字机效果：逐字显示思考内容，然后依次展开依据、建议
const startTypingEffect = (code: PricingAgentCode, immediate = false) => {
  clearTypingTimer(code)
  const card = taskState.cards[code]
  if (!card) return

  const state = typingStates[code]
  const fullThinking = card.thinking || ''

  // 快照加载时跳过动画，直接展示全部内容
  if (immediate || !fullThinking) {
    state.thinkingText = fullThinking
    state.thinkingDone = true
    state.showEvidence = true
    state.showSuggestion = true
    state.showReason = true
    return
  }

  // 重置状态
  state.thinkingText = ''
  state.thinkingDone = false
  state.showEvidence = false
  state.showSuggestion = false
  state.showReason = false

  let idx = 0
  // 每30ms输出2-4个字符，模拟 LLM 逐字输出效果
  typingTimerIds[code] = setInterval(() => {
    if (idx < fullThinking.length) {
      const chunkSize = Math.min(3, fullThinking.length - idx)
      state.thinkingText += fullThinking.slice(idx, idx + chunkSize)
      idx += chunkSize
    } else {
      clearTypingTimer(code)
      state.thinkingDone = true
      // 依次展开依据、建议、理由区块（各间隔300ms）
      setTimeout(() => {
        state.showEvidence = true
        setTimeout(() => {
          state.showSuggestion = true
          setTimeout(() => { state.showReason = true }, 200)
        }, 300)
      }, 300)
    }
  }, 30)
}

// 重置所有打字状态
const resetTypingStates = () => {
  for (const code of Object.keys(typingStates) as PricingAgentCode[]) {
    clearTypingTimer(code)
    typingStates[code] = EMPTY_TYPING()
  }
}

const completedCount = computed(() => Object.values(taskState.cards).filter((item) => item !== null).length)

const stepBarActive = computed(() => {
  if (activeStep.value === 2) return 3
  if (activeStep.value === 1) return 2
  return 1
})

const statusText = computed(() => {
  const mapping: Record<string, string> = {
    IDLE: '未开始',
    PENDING: '待执行',
    RUNNING: '执行中',
    COMPLETED: '已完成',
    FAILED: '执行失败'
  }
  return mapping[taskState.taskStatus] || taskState.taskStatus
})

const strategyGoalText = computed(() => {
  const mapping: Record<string, string> = {
    MAX_PROFIT: '利润优先',
    CLEARANCE: '清仓促销',
    MARKET_SHARE: '市场份额优先'
  }
  return mapping[taskConfig.strategyGoal] || taskConfig.strategyGoal
})

const selectedProductName = computed(() => {
  return productOptions.value.find((item) => item.id === taskConfig.productId)?.productName || ''
})

const managerSuggestion = computed(() => {
  const raw = taskState.cards.MANAGER_COORDINATOR?.suggestion
  if (raw && typeof raw === 'object') return raw as Record<string, unknown>
  return {}
})

const reportExpectedSales = computed(() => toNumber(managerSuggestion.value.expectedSales))
const reportExpectedProfit = computed(() => toNumber(managerSuggestion.value.expectedProfit))
const reportStrategy = computed(() => taskState.strategy || String(managerSuggestion.value.strategy || ''))
const reportSummary = computed(() => {
  const fromArchive = archiveReportSummary.value.trim()
  if (fromArchive) return fromArchive
  return taskState.finalSummary || String(managerSuggestion.value.summary || '')
})
const canViewReport = computed(() => taskState.taskStatus === 'COMPLETED' || completedCount.value >= 4)

const decisionProgress = computed(() => {
  if (taskState.taskStatus === 'FAILED') return 100
  if (taskState.taskStatus === 'COMPLETED') return 100
  if (taskState.taskStatus === 'RUNNING') return Math.min(20 + completedCount.value * 20, 95)
  if (taskState.taskStatus === 'PENDING') return 10
  return 0
})

const searchProducts = (query: string) => {
  loadProducts(query)
}

const loadProducts = async (query = '') => {
  const loadToken = ++latestProductLoadToken
  searchLoading.value = true
  try {
    const pageSize = 100
    const allProducts: ProductOption[] = []
    let page = 1
    let pages = 1

    while (page <= pages) {
      const res = (await getProductList({ page, size: pageSize, keyword: query })) as ApiResponse<{
        records: Array<{ id: number; productName: string }>
        pages: number
      }>
      if (loadToken !== latestProductLoadToken) return
      if (res.code !== 200) break

      const records = Array.isArray(res.data?.records) ? res.data.records : []
      records.forEach((item) => {
        allProducts.push({
          id: Number(item.id),
          productName: String(item.productName || '')
        })
      })

      const apiPages = Number(res.data?.pages || 1)
      pages = Number.isFinite(apiPages) && apiPages > 0 ? apiPages : 1
      page += 1
    }

    if (loadToken === latestProductLoadToken) {
      const uniqueById = new Map<number, ProductOption>()
      allProducts.forEach((item) => {
        if (item.id) uniqueById.set(item.id, item)
      })
      productOptions.value = Array.from(uniqueById.values())
    }
  } finally {
    if (loadToken === latestProductLoadToken) {
      searchLoading.value = false
    }
  }
}

const stopWebSocket = () => {
  if (wsClient) {
    wsClient.close()
    wsClient = null
  }
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

const orderByCode: Record<PricingAgentCode, number> = {
  DATA_ANALYSIS: 1,
  MARKET_INTEL: 2,
  RISK_CONTROL: 3,
  MANAGER_COORDINATOR: 4
}

const resolveOrder = (code: PricingAgentCode, displayOrder?: number | null, runOrder?: number | null) => {
  if (displayOrder && displayOrder >= 1 && displayOrder <= 4) return displayOrder
  if (runOrder && runOrder >= 1 && runOrder <= 4) return runOrder
  return orderByCode[code]
}

const resetCardStreaming = () => {
  streamToken += 1
  streamLoopRunning = false
  streamCursor.value = 1
  pendingCards[1] = null
  pendingCards[2] = null
  pendingCards[3] = null
  pendingCards[4] = null
  resetTypingStates()
}

const runStreamLoop = async (token: number) => {
  if (streamLoopRunning) return
  streamLoopRunning = true
  try {
    while (token === streamToken) {
      const nextOrder = streamCursor.value
      const next = pendingCards[nextOrder]
      if (!next) break

      pendingCards[nextOrder] = null
      await sleep(450)
      if (token !== streamToken) return

      taskState.cards[next.code] = normalizeCard(next.card)
      // 实时推送的卡片启动打字机动画
      startTypingEffect(next.code, false)
      streamCursor.value += 1
    }
  } finally {
    if (token === streamToken) {
      streamLoopRunning = false
    }
  }
}

// isSnapshot 参数：快照加载时跳过打字动画，直接展示全部内容
const queueCardForStreaming = (item: StreamCardItem, isSnapshot = false) => {
  if (item.order < streamCursor.value) {
    taskState.cards[item.code] = normalizeCard(item.card)
    startTypingEffect(item.code, isSnapshot)
    return
  }
  if (item.order < 1 || item.order > 4) {
    taskState.cards[item.code] = normalizeCard(item.card)
    startTypingEffect(item.code, isSnapshot)
    return
  }
  pendingCards[item.order] = item
  if (isSnapshot) {
    // 快照模式：立即展示，不等待流式延迟
    pendingCards[item.order] = null
    taskState.cards[item.code] = normalizeCard(item.card)
    startTypingEffect(item.code, true)
    streamCursor.value = Math.max(streamCursor.value, item.order + 1)
  } else {
    void runStreamLoop(streamToken)
  }
}

const normalizeCard = (card?: AgentCardContent | null): AgentCardContent => {
  return {
    thinking: String(card?.thinking || ''),
    evidence: Array.isArray(card?.evidence) ? card.evidence : [],
    suggestion: card?.suggestion && typeof card.suggestion === 'object' ? card.suggestion : {},
    reasonWhy: card?.reasonWhy || null
  }
}

const applyLogSnapshot = (logs: DecisionLogItem[]) => {
  const streamItems: StreamCardItem[] = []
  for (const log of logs) {
    const code = String(log.agentCode || '') as PricingAgentCode
    if (!code || !(code in taskState.cards)) continue
    const card = normalizeCard({
      thinking: String(log.thinking || log.outputSummary || ''),
      evidence: log.evidence || [],
      suggestion: log.suggestion || {},
      reasonWhy: log.reasonWhy || null
    })
    streamItems.push({
      order: resolveOrder(code, log.displayOrder, log.runOrder),
      code,
      card
    })
  }

  // 快照加载：跳过打字动画，直接展示全部内容
  streamItems
    .sort((a, b) => a.order - b.order)
    .forEach((item) => {
      queueCardForStreaming(item, true)
    })
}

const toStreamCardFromPayload = (payload: PricingAgentCardMessage): StreamCardItem | null => {
  const code = payload.agentCode as PricingAgentCode
  if (!(code in taskState.cards)) return null
  return {
    order: resolveOrder(code, payload.displayOrder, null),
    code,
    card: normalizeCard(payload.card)
  }
}

const loadTaskLogs = async (taskId: number) => {
  const res = (await getPricingTaskLogs(taskId)) as ApiResponse<DecisionLogItem[]>
  if (res.code === 200) {
    applyLogSnapshot(Array.isArray(res.data) ? res.data : [])
  }
}

const loadArchiveSummary = async (taskId: number) => {
  try {
    const res = (await getTaskComparison(taskId)) as ApiResponse<DecisionComparisonItem[]>
    if (res.code !== 200) {
      archiveReportSummary.value = ''
      comparisonData.value = []
      return
    }
    const rows = Array.isArray(res.data) ? res.data : []
    comparisonData.value = rows
    const row = rows.find((item) => String(item.resultSummary || '').trim())
    archiveReportSummary.value = row ? String(row.resultSummary || '').trim() : ''
  } catch {
    archiveReportSummary.value = ''
    comparisonData.value = []
  }
}

const loadTaskDetail = async (taskId: number) => {
  const res = (await getPricingTaskDetail(taskId)) as ApiResponse<PricingTaskDetail>
  if (res.code !== 200) return
  const detail = res.data
  if (!detail) return

  taskState.taskStatus = (detail.taskStatus || 'RUNNING') as PricingTaskStatus
  taskState.finalPrice = detail.finalPrice != null ? Number(detail.finalPrice) : null
  taskState.strategy = String(detail.strategy || '')
  taskState.finalSummary = String(detail.finalSummary || '')
}

const loadTaskSnapshot = async (taskId: number) => {
  await Promise.all([loadTaskDetail(taskId), loadTaskLogs(taskId), loadArchiveSummary(taskId)])
}

const handleTaskStarted = (payload: PricingTaskStartedMessage) => {
  taskState.taskStatus = (payload.status || 'RUNNING') as PricingTaskStatus
}

const handleAgentCard = (payload: PricingAgentCardMessage) => {
  const streamItem = toStreamCardFromPayload(payload)
  if (!streamItem) return
  queueCardForStreaming(streamItem)
}

const handleTaskCompleted = async (payload: PricingTaskCompletedMessage) => {
  taskState.taskStatus = 'COMPLETED'
  if (payload.result) {
    taskState.finalPrice = payload.result.finalPrice != null ? Number(payload.result.finalPrice) : null
    taskState.strategy = String(payload.result.strategy || '')
    taskState.finalSummary = String(payload.result.summary || '')
  }
  if (currentTaskId.value) {
    await loadTaskSnapshot(currentTaskId.value)
  }
  stopWebSocket()
  ElMessage.success('智能决策已完成，可查看结果报告')
}

const handleTaskFailed = async (payload: PricingTaskFailedMessage) => {
  taskState.taskStatus = 'FAILED'
  taskState.errorMessage = payload.message || '任务执行失败'
  if (currentTaskId.value) {
    await loadTaskSnapshot(currentTaskId.value)
  }
  activeStep.value = 1
  stopWebSocket()
  ElMessage.error(taskState.errorMessage)
}

const handleWebSocketMessage = async (payload: PricingWsMessage) => {
  switch (payload.type) {
    case 'task_started':
      handleTaskStarted(payload)
      break
    case 'agent_card':
      handleAgentCard(payload)
      break
    case 'task_completed':
      await handleTaskCompleted(payload)
      break
    case 'task_failed':
      await handleTaskFailed(payload)
      break
    default:
      break
  }
}

const startWebSocket = (taskId: number) => {
  stopWebSocket()
  wsClient = new WebSocket(getPricingTaskWebSocketUrl(taskId))

  wsClient.onmessage = async (event: MessageEvent) => {
    try {
      const payload = JSON.parse(String(event.data || '{}')) as PricingWsMessage
      await handleWebSocketMessage(payload)
    } catch {
      // 忽略格式错误消息，保持连接。
    }
  }

  wsClient.onerror = async () => {
    if (currentTaskId.value) {
      await loadTaskSnapshot(currentTaskId.value)
    }
  }

  wsClient.onclose = async () => {
    wsClient = null
    if (taskState.taskStatus === 'RUNNING' && currentTaskId.value) {
      await loadTaskSnapshot(currentTaskId.value)
    }
  }
}

const startTask = async () => {
  if (!taskConfig.productId) {
    ElMessage.warning('请选择一个商品')
    return
  }

  starting.value = true
  try {
    taskState.taskStatus = 'PENDING'
    resetCardStreaming()
    taskState.cards = EMPTY_CARDS()
    taskState.finalPrice = null
    taskState.strategy = ''
    taskState.finalSummary = ''
    archiveReportSummary.value = ''
    taskState.errorMessage = ''

    const res = (await createPricingTask({
      productId: taskConfig.productId,
      constraints: taskConfig.constraints,
      strategyGoal: taskConfig.strategyGoal
    })) as ApiResponse<number>

    if (res.code !== 200 || !res.data) {
      taskState.taskStatus = 'FAILED'
      taskState.errorMessage = res.message || '启动任务失败'
      ElMessage.error(taskState.errorMessage)
      return
    }

    currentTaskId.value = Number(res.data)
    taskState.taskStatus = 'RUNNING'
    activeStep.value = 1
    await loadTaskSnapshot(currentTaskId.value)
    startWebSocket(currentTaskId.value)
    ElMessage.success('任务已启动，进入智能决策阶段')
  } catch {
    taskState.taskStatus = 'FAILED'
    taskState.errorMessage = '启动任务失败'
    ElMessage.error(taskState.errorMessage)
  } finally {
    starting.value = false
  }
}

const refreshSnapshot = async () => {
  if (!currentTaskId.value) return
  await loadTaskSnapshot(currentTaskId.value)
  if (taskState.taskStatus === 'RUNNING' && !wsClient) {
    startWebSocket(currentTaskId.value)
  }
  ElMessage.success(`已刷新快照，当前已收到 ${completedCount.value}/4 张卡片`)
}

const goToReport = () => {
  if (!canViewReport.value) {
    ElMessage.warning('任务尚未完成，暂不能查看结果报告')
    return
  }
  if (currentTaskId.value && !archiveReportSummary.value.trim()) {
    void loadArchiveSummary(currentTaskId.value)
  }
  activeStep.value = 2
}

const goToDecision = () => {
  activeStep.value = 1
}

const goToConfig = () => {
  activeStep.value = 0
}

const resetTask = () => {
  stopWebSocket()
  resetCardStreaming()
  currentTaskId.value = null
  taskState.taskStatus = 'IDLE'
  taskState.cards = EMPTY_CARDS()
  taskState.finalPrice = null
  taskState.strategy = ''
  taskState.finalSummary = ''
  archiveReportSummary.value = ''
  comparisonData.value = []
  taskState.errorMessage = ''
  activeStep.value = 0
}

const toNumber = (value: unknown): number | null => {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

const formatCurrency = (value?: number | null) => {
  return sharedFormatCurrency(value, { fallbackText: '-' })
}

const formatSignedCurrency = (value?: number | string | null) => {
  return sharedFormatSignedCurrency(value, { fallbackText: '-' })
}

const applyPrice = async (row: DecisionComparisonItem) => {
  const resultId = Number(row.resultId || 0)
  if (!resultId) {
    ElMessage.error('未找到可应用的结果记录')
    return
  }

  try {
    await ElMessageBox.confirm(
      createApplyDecisionConfirmMessage(row.productTitle, row.suggestedPrice as number),
      '应用价格建议',
      {
        type: 'warning',
        confirmButtonText: '确认应用',
        cancelButtonText: '取消'
      }
    )

    applyingResultIds.value.push(resultId)
    const res: any = await applyDecision(resultId)
    if (res.code !== 200) {
      ElMessage.error(res.message || '应用失败')
      return
    }

    ElMessage.success('价格建议已应用')
    if (currentTaskId.value) {
      await loadArchiveSummary(currentTaskId.value)
    }
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('应用失败')
    }
  } finally {
    applyingResultIds.value = applyingResultIds.value.filter((id) => id !== resultId)
  }
}

onMounted(() => {
  loadProducts()
})

onBeforeUnmount(() => {
  stopWebSocket()
  resetTypingStates()
})
</script>

<style scoped>
.pricing-page {
  gap: 14px;
}

.step-panel,
.config-panel,
.helper-panel,
.status-panel,
.report-panel {
  padding: 20px;
}

.steps {
  padding-top: 0;
}

.config-form {
  display: grid;
  gap: 10px;
}

.goal-group {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.goal-group :deep(.el-radio) {
  margin-right: 0;
}

.option-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.option-id {
  color: var(--text-3);
  font-size: 12px;
}

.summary-card {
  display: grid;
  gap: 10px;
  padding: 14px;
  border-radius: 10px;
  background: var(--surface-2);
  border: 1px solid var(--line-soft);
}

.summary-line {
  margin-top: 10px;
  color: var(--text-2);
  line-height: 1.7;
}

.tips-list {
  margin-top: 14px;
  display: grid;
  gap: 12px;
}

.tip-item {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--line-soft);
  background: var(--surface-2);
}

.decision-layout {
  display: grid;
  gap: 14px;
}

.status-grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.status-item {
  background: var(--surface-2);
  border: 1px solid var(--line-soft);
  border-radius: 10px;
  padding: 12px 14px;
  display: grid;
  gap: 6px;
}

.error-alert {
  margin-top: 10px;
}

.agent-stream-panel {
  padding: 16px 20px;
}

.agent-stream-scroll {
  max-height: none;
  overflow: visible;
  padding-right: 0;
  display: grid;
  gap: 14px;
}

.stream-card {
  background: #fff;
  border: 1px solid var(--line-soft);
  border-radius: 10px;
  padding: 18px;
  transition: border-color 0.3s ease;
}

/* ── 流式打字机效果 ───────────────────────────── */
.typing-text {
  white-space: pre-wrap;
  line-height: 1.8;
}

.typing-cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  background: var(--el-color-primary);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: cursor-blink 0.8s step-end infinite;
}

@keyframes cursor-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* 区块淡入动画 */
.card-fade-enter-active {
  animation: card-slide-in 0.4s ease-out;
}

@keyframes card-slide-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 当前正在处理的 Agent 等待状态 */
.waiting-active {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 0;
  gap: 12px;
}

.waiting-text {
  color: var(--text-3);
  font-size: 13px;
}

.thinking-dots {
  display: flex;
  gap: 6px;
}

.thinking-dots span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--el-color-primary);
  animation: dot-bounce 1.4s ease-in-out infinite;
}

.thinking-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.thinking-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes dot-bounce {
  0%, 80%, 100% {
    opacity: 0.3;
    transform: scale(0.8);
  }
  40% {
    opacity: 1;
    transform: scale(1.1);
  }
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.card-body {
  display: grid;
  gap: 12px;
}

.card-section {
  background: var(--surface-2);
  border: 1px solid var(--line-soft);
  border-radius: 10px;
  padding: 12px 14px;
}

.card-section h4 {
  margin: 0 0 8px;
  font-size: 14px;
}

.card-section p {
  margin: 0;
  line-height: 1.7;
}

.info-list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 6px;
  line-height: 1.7;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.metric-card {
  background: #fff;
  border: 1px solid var(--line-soft);
  border-radius: 10px;
  padding: 16px;
}

.metric-label {
  color: var(--text-2);
  font-size: 13px;
}

.metric-value {
  margin-top: 8px;
  font-size: 24px;
  font-weight: 700;
}

.strategy-value {
  font-size: 18px;
}

.report-table {
  margin-top: 14px;
}

@media (max-width: 1200px) {
  .metric-grid,
  .status-grid {
    grid-template-columns: 1fr;
  }
}
</style>

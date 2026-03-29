<template>
  <div class="page-shell pricing-page">
    <section class="panel-card config-panel">
      <div class="section-head">
        <div class="section-title">
          <h3>多 Agent 定价任务</h3>
          <p>按“一个 Agent 一张卡片”展示执行过程与最终建议。</p>
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
          <el-button :disabled="!currentTaskId" @click="refreshSnapshot">刷新快照</el-button>
          <el-button :disabled="!currentTaskId" @click="resetTask">重置</el-button>
        </div>
      </el-form>
    </section>

    <section class="panel-card status-panel">
      <div class="status-grid">
        <article class="status-item">
          <span>任务ID</span>
          <strong>{{ currentTaskId || '-' }}</strong>
        </article>
        <article class="status-item">
          <span>任务状态</span>
          <strong>{{ taskState.taskStatus }}</strong>
        </article>
        <article class="status-item">
          <span>最终价格</span>
          <strong>{{ formatCurrency(taskState.finalPrice) }}</strong>
        </article>
        <article class="status-item">
          <span>执行策略</span>
          <strong>{{ taskState.strategy || '-' }}</strong>
        </article>
      </div>
      <div class="summary-line">最终摘要：{{ taskState.finalSummary || '-' }}</div>
      <el-alert
        v-if="taskState.errorMessage"
        :title="taskState.errorMessage"
        type="error"
        :closable="false"
        class="error-alert"
      />
    </section>

    <section class="card-grid">
      <article v-for="meta in agentOrder" :key="meta.code" class="panel-card agent-card">
        <div class="card-head">
          <h3>{{ meta.order }}. {{ meta.name }}</h3>
          <el-tag size="small" :type="taskState.cards[meta.code] ? 'success' : 'info'">
            {{ taskState.cards[meta.code] ? '已完成' : '等待中' }}
          </el-tag>
        </div>

        <div v-if="taskState.cards[meta.code]" class="card-body">
          <section class="card-section">
            <h4>思考过程</h4>
            <p>{{ taskState.cards[meta.code]?.thinking || '-' }}</p>
          </section>

          <section class="card-section">
            <h4>依据</h4>
            <ul class="evidence-list">
              <li v-for="(item, idx) in taskState.cards[meta.code]?.evidence || []" :key="idx">
                <strong>{{ String(item.label || `依据${idx + 1}`) }}：</strong>
                <span>{{ formatEvidenceValue(item.value) }}</span>
              </li>
            </ul>
          </section>

          <section class="card-section">
            <h4>建议</h4>
            <pre>{{ formatSuggestion(taskState.cards[meta.code]?.suggestion) }}</pre>
          </section>

          <section v-if="meta.code === 'MANAGER_COORDINATOR'" class="card-section">
            <h4>为什么给出这个建议</h4>
            <p>{{ taskState.cards[meta.code]?.reasonWhy || '-' }}</p>
          </section>
        </div>

        <el-empty v-else description="等待该 Agent 输出卡片" :image-size="90" />
      </article>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  createPricingTask,
  getPricingTaskDetail,
  getPricingTaskLogs,
  getPricingTaskWebSocketUrl,
  type AgentCardContent,
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
let latestProductLoadToken = 0
let wsClient: WebSocket | null = null

const completedCount = computed(
  () => Object.values(taskState.cards).filter((item) => item !== null).length
)

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

const normalizeCard = (card?: AgentCardContent | null): AgentCardContent => {
  return {
    thinking: String(card?.thinking || ''),
    evidence: Array.isArray(card?.evidence) ? card.evidence : [],
    suggestion: card?.suggestion && typeof card.suggestion === 'object' ? card.suggestion : {},
    reasonWhy: card?.reasonWhy || null
  }
}

const applyLogSnapshot = (logs: DecisionLogItem[]) => {
  for (const log of logs) {
    const code = String(log.agentCode || '') as PricingAgentCode
    if (!code || !(code in taskState.cards)) continue
    taskState.cards[code] = normalizeCard({
      thinking: String(log.thinking || log.outputSummary || ''),
      evidence: log.evidence || [],
      suggestion: log.suggestion || {},
      reasonWhy: log.reasonWhy || null
    })
  }
}

const loadTaskLogs = async (taskId: number) => {
  const res = (await getPricingTaskLogs(taskId)) as ApiResponse<DecisionLogItem[]>
  if (res.code === 200) {
    applyLogSnapshot(Array.isArray(res.data) ? res.data : [])
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

const handleTaskStarted = (payload: PricingTaskStartedMessage) => {
  taskState.taskStatus = (payload.status || 'RUNNING') as PricingTaskStatus
}

const handleAgentCard = (payload: PricingAgentCardMessage) => {
  const code = payload.agentCode as PricingAgentCode
  if (!(code in taskState.cards)) return
  taskState.cards[code] = normalizeCard(payload.card)
}

const handleTaskCompleted = async (payload: PricingTaskCompletedMessage) => {
  taskState.taskStatus = 'COMPLETED'
  if (payload.result) {
    taskState.finalPrice = payload.result.finalPrice != null ? Number(payload.result.finalPrice) : null
    taskState.strategy = String(payload.result.strategy || '')
    taskState.finalSummary = String(payload.result.summary || '')
  }
  if (currentTaskId.value) {
    await Promise.all([loadTaskDetail(currentTaskId.value), loadTaskLogs(currentTaskId.value)])
  }
  stopWebSocket()
  ElMessage.success('任务执行完成')
}

const handleTaskFailed = async (payload: PricingTaskFailedMessage) => {
  taskState.taskStatus = 'FAILED'
  taskState.errorMessage = payload.message || '任务执行失败'
  if (currentTaskId.value) {
    await Promise.all([loadTaskDetail(currentTaskId.value), loadTaskLogs(currentTaskId.value)])
  }
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
      await Promise.all([loadTaskDetail(currentTaskId.value), loadTaskLogs(currentTaskId.value)])
    }
  }

  wsClient.onclose = async () => {
    wsClient = null
    if (taskState.taskStatus === 'RUNNING' && currentTaskId.value) {
      await Promise.all([loadTaskDetail(currentTaskId.value), loadTaskLogs(currentTaskId.value)])
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
    taskState.cards = EMPTY_CARDS()
    taskState.finalPrice = null
    taskState.strategy = ''
    taskState.finalSummary = ''
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
    await Promise.all([loadTaskDetail(currentTaskId.value), loadTaskLogs(currentTaskId.value)])
    startWebSocket(currentTaskId.value)
    ElMessage.success('任务已启动，等待Agent卡片输出')
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
  await Promise.all([loadTaskDetail(currentTaskId.value), loadTaskLogs(currentTaskId.value)])
  if (taskState.taskStatus === 'RUNNING' && !wsClient) {
    startWebSocket(currentTaskId.value)
  }
  ElMessage.success(`已刷新快照，当前已收到 ${completedCount.value}/4 张卡片`)
}

const resetTask = () => {
  stopWebSocket()
  currentTaskId.value = null
  taskState.taskStatus = 'IDLE'
  taskState.cards = EMPTY_CARDS()
  taskState.finalPrice = null
  taskState.strategy = ''
  taskState.finalSummary = ''
  taskState.errorMessage = ''
}

const formatCurrency = (value?: number | null) => {
  if (value == null || Number.isNaN(Number(value))) return '-'
  return `¥${Number(value).toFixed(2)}`
}

const formatEvidenceValue = (value: unknown) => {
  if (value == null) return '-'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  return JSON.stringify(value, null, 2)
}

const formatSuggestion = (suggestion?: Record<string, unknown>) => {
  if (!suggestion || Object.keys(suggestion).length === 0) return '-'
  return JSON.stringify(suggestion, null, 2)
}

onMounted(() => {
  loadProducts()
})

onBeforeUnmount(() => {
  stopWebSocket()
})
</script>

<style scoped>
.pricing-page {
  gap: 14px;
}

.config-panel,
.status-panel,
.agent-card {
  padding: 20px;
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

.status-grid {
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

.summary-line {
  margin-top: 10px;
  color: var(--text-2);
}

.error-alert {
  margin-top: 10px;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.card-body {
  display: grid;
  gap: 14px;
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

.evidence-list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 6px;
}

pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.6;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace;
}

@media (max-width: 1024px) {
  .status-grid,
  .card-grid {
    grid-template-columns: 1fr;
  }
}
</style>

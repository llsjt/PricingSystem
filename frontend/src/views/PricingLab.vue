<template>
  <div class="page-shell pricing-page">
    <section class="panel-card step-panel">
      <div class="section-head">
        <div class="section-title">
          <h3>任务流程</h3>
          <p>从配置、执行到报告复盘，进度始终保持可见。</p>
        </div>
      </div>

      <el-steps :active="stepBarActive" finish-status="success" align-center class="steps">
        <el-step title="配置任务" description="选择商品并确认目标" />
        <el-step title="智能决策" description="查看 Agent 协同推理" />
        <el-step title="结果报告" description="确认建议价格与依据" />
      </el-steps>
    </section>

    <div v-if="activeStep === 0" class="responsive-two">
      <section class="panel-card config-panel">
        <div class="section-head">
          <div class="section-title">
            <h3>任务配置</h3>
            <p>明确策略目标和约束条件，系统会将这些要求传递给所有 Agent。</p>
          </div>
        </div>

        <el-form :model="taskConfig" label-position="top" class="config-form">
          <el-form-item label="选择商品">
            <el-select
              v-model="taskConfig.productIds"
              multiple
              filterable
              remote
              reserve-keyword
              placeholder="输入商品名称搜索"
              :remote-method="searchProducts"
              :loading="searchLoading"
              @change="handleProductChange"
              value-key="id"
            >
              <el-option
                v-for="item in productOptions"
                :key="item.id"
                :label="item.title"
                :value="item.id"
              >
                <div class="option-row">
                  <span>{{ item.title }}</span>
                  <span class="option-id">ID {{ item.id }}</span>
                </div>
              </el-option>
              <div v-if="productOptions.length < productTotal" class="load-more">
                <el-button link type="primary" @click.stop="loadMoreProducts">加载更多</el-button>
              </div>
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
              :rows="5"
              placeholder="例如：利润率不低于 15%，降价幅度不超过 10%，最低售价不低于 69 元"
            />
            <div class="mini-note">约束会被解析成硬约束并同步给数据分析、市场情报、风险控制和经理协调。</div>
          </el-form-item>

          <div class="toolbar-actions">
            <el-button :loading="starting" type="primary" size="large" @click="startTask">启动智能决策</el-button>
          </div>
        </el-form>
      </section>

      <section class="panel-card helper-panel">
        <div class="section-head">
          <div class="section-title">
            <h3>配置提示</h3>
            <p>让系统更快收敛到可执行方案。</p>
          </div>
        </div>

        <div class="tips-list">
          <article class="tip-item">
            <strong>目标明确</strong>
            <span>利润优先时更关注利润空间，市场份额优先时更关注竞争响应。</span>
          </article>
          <article class="tip-item">
            <strong>约束可量化</strong>
            <span>建议直接写最低利润率、最大降价幅度、最低售价等硬指标。</span>
          </article>
          <article class="tip-item">
            <strong>结果可解释</strong>
            <span>执行阶段会展示每个 Agent 的思考过程、分析理由与最终建议。</span>
          </article>
        </div>

        <div class="summary-card">
          <div class="summary-title">当前选择摘要</div>
          <div class="summary-line">目标：{{ strategyGoalText }}</div>
          <div class="summary-line">商品：{{ selectedProductNames.length ? selectedProductNames.join('、') : '尚未选择' }}</div>
          <div class="summary-line">约束：{{ taskConfig.constraints || '尚未填写' }}</div>
        </div>
      </section>
    </div>

    <div v-else-if="activeStep === 1" class="responsive-two execution-layout">
      <section class="panel-card log-panel">
        <div class="section-head">
          <div class="section-title">
            <h3>Agent 协同过程</h3>
            <p>流式展示思考过程、分析理由和最终建议，历史日志会自动补全。</p>
          </div>
          <div class="chip-list">
            <el-tag v-if="socketStatus === 'connecting'" type="warning">连接中</el-tag>
            <el-tag v-else-if="socketStatus === 'connected'" type="success">实时连接</el-tag>
            <el-tag v-else type="info">日志回放</el-tag>
          </div>
        </div>

        <div ref="chatBoxRef" class="chat-stream">
          <el-empty v-if="chatMessages.length === 0" description="等待 Agent 输出内容" />
          <article
            v-for="message in orderedMessages"
            :key="buildMessageDomKey(message)"
            :class="['message-card', getAgentClass(message.agent_role), { streaming: message.streaming }]"
          >
            <div class="message-avatar">{{ getAgentAvatar(message.agent_role) }}</div>
            <div class="message-main">
              <div class="message-head">
                <strong>{{ message.agent_role }}</strong>
                <span>{{ message.timestamp }}</span>
              </div>
              <div class="message-body">
                <p v-if="message.streaming && !message.thought_content" class="typing-placeholder">
                  正在生成分析内容...
                </p>
                <p v-else v-html="formatContent(message.thought_content)"></p>
              </div>
            </div>
          </article>
        </div>
      </section>

      <div class="side-column">
        <section class="panel-card status-panel">
          <div class="section-head">
            <div class="section-title">
              <h3>执行反馈</h3>
              <p>实时反馈任务进度、状态和下一步动作。</p>
            </div>
          </div>

          <el-progress :percentage="progress" :stroke-width="12" :status="progress === 100 ? 'success' : ''" />

          <div class="status-list">
            <div class="status-item">
              <span>任务编号</span>
              <strong>{{ currentTaskId || '-' }}</strong>
            </div>
            <div class="status-item">
              <span>已接收消息</span>
              <strong>{{ chatMessages.length }}</strong>
            </div>
            <div class="status-item">
              <span>连接状态</span>
              <strong>{{ socketStatusText }}</strong>
            </div>
          </div>

          <div class="toolbar-actions full-width">
            <el-button v-if="progress === 100" type="primary" @click="viewResult">查看最终报告</el-button>
          </div>
        </section>

        <section class="panel-card status-panel">
          <div class="section-head">
            <div class="section-title">
              <h3>任务概览</h3>
              <p>帮助你快速确认本次决策上下文。</p>
            </div>
          </div>

          <div class="summary-line">目标：{{ strategyGoalText }}</div>
          <div class="summary-line">商品：{{ selectedProductNames.length ? selectedProductNames.join('、') : '-' }}</div>
          <div class="summary-line">约束：{{ taskConfig.constraints || '无' }}</div>
        </section>
      </div>
    </div>

    <div v-else class="page-shell">
      <section class="metric-grid">
        <article class="metric-card">
          <div class="metric-label">建议商品数</div>
          <div class="metric-value">{{ resultList.length }}</div>
          <div class="metric-hint">已完成智能定价输出</div>
        </article>
        <article class="metric-card">
          <div class="metric-label">平均建议价格</div>
          <div class="metric-value">￥{{ averageSuggestedPrice }}</div>
          <div class="metric-hint">便于快速评估策略区间</div>
        </article>
        <article class="metric-card">
          <div class="metric-label">预计利润变化</div>
          <div class="metric-value">{{ averageProfitChange }}</div>
          <div class="metric-hint">正值说明利润改善预期更高</div>
        </article>
      </section>

      <section class="panel-card table-card">
        <div class="section-head">
          <div class="section-title">
            <h3>结果报告</h3>
            <p>查看建议价格、利润变化和核心原因，必要时可重新配置任务。</p>
          </div>
          <div class="toolbar-actions">
            <el-button @click="resetToConfig">重新配置</el-button>
          </div>
        </div>

        <el-table :data="resultList" border stripe>
          <el-table-column prop="productId" label="商品 ID" width="100" />
          <el-table-column label="原价" min-width="140">
            <template #default="{ row }">
              <span>￥{{ Number(row.originalPrice || 0).toFixed(2) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="建议价格" min-width="140">
            <template #default="{ row }">
              <span class="price-text">￥{{ Number(row.suggestedPrice || 0).toFixed(2) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="预计利润变化" min-width="140">
            <template #default="{ row }">
              <el-tag :type="Number(row.profitChange || 0) >= 0 ? 'success' : 'danger'">
                {{ Number(row.profitChange || 0).toFixed(2) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="核心依据" min-width="360" show-overflow-tooltip>
            <template #default="{ row }">
              <span>{{ formatCoreReasons(row.coreReasons) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-tag v-if="row.adoptStatus === 'ADOPTED'" type="success">已应用</el-tag>
              <el-button
                v-else
                type="primary"
                link
                :loading="applyingResultIds.includes(Number(row.id))"
                @click="acceptPrice(row)"
              >
                应用建议
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { applyDecision, getTaskLogs, getTaskResult, startDecisionTask } from '../api/decision'
import { getProductList } from '../api/product'

interface ProductOption {
  id: number
  title: string
}

interface ChatMessage {
  agent_role: string
  thought_content: string
  timestamp: string
  product_id?: number
  step_order?: number
  streaming?: boolean
}

interface TaskLogRecord {
  id?: number
  roleName?: string
  role_name?: string
  thoughtContent?: string
  thought_content?: string
  speakOrder?: number
  speak_order?: number
  createdAt?: string
}

const activeStep = ref(0)
const starting = ref(false)
const searchLoading = ref(false)
const productOptions = ref<ProductOption[]>([])
const selectedProducts = ref<ProductOption[]>([])
const productPage = ref(1)
const productTotal = ref(0)
const currentQuery = ref('')

const taskConfig = reactive({
  productIds: [] as number[],
  strategyGoal: '',
  constraints: ''
})

const socketStatus = ref<'connecting' | 'connected' | 'disconnected'>('disconnected')
const chatMessages = ref<ChatMessage[]>([])
const chatBoxRef = ref<HTMLDivElement>()
const progress = ref(0)
const currentTaskId = ref<number | null>(null)
const resultList = ref<any[]>([])
const applyingResultIds = ref<number[]>([])

const stepBarActive = computed(() => {
  if (activeStep.value === 2) return 3
  if (activeStep.value === 1) return 2
  return 1
})

const strategyGoalText = computed(() => {
  const mapping: Record<string, string> = {
    MAX_PROFIT: '利润优先',
    CLEARANCE: '清仓促销',
    MARKET_SHARE: '市场份额优先'
  }
  if (!taskConfig.strategyGoal) return '未选择'
  return mapping[taskConfig.strategyGoal] || taskConfig.strategyGoal
})

const socketStatusText = computed(() => {
  const mapping = {
    connecting: '连接中',
    connected: '实时连接',
    disconnected: '日志回放'
  }
  return mapping[socketStatus.value]
})

const selectedProductNames = computed(() =>
  selectedProducts.value
    .filter((item) => taskConfig.productIds.includes(item.id))
    .map((item) => item.title)
)

const orderedMessages = computed(() =>
  [...chatMessages.value].sort((a, b) => {
    if ((a.product_id || 0) !== (b.product_id || 0)) {
      return (a.product_id || 0) - (b.product_id || 0)
    }
    if ((a.step_order || 0) !== (b.step_order || 0)) {
      return (a.step_order || 0) - (b.step_order || 0)
    }
    return a.timestamp.localeCompare(b.timestamp)
  })
)

const averageSuggestedPrice = computed(() => {
  if (resultList.value.length === 0) return '0.00'
  const totalPrice = resultList.value.reduce((sum, item) => sum + Number(item.suggestedPrice || 0), 0)
  return (totalPrice / resultList.value.length).toFixed(2)
})

const averageProfitChange = computed(() => {
  if (resultList.value.length === 0) return '0.00'
  const totalChange = resultList.value.reduce((sum, item) => sum + Number(item.profitChange || 0), 0)
  return (totalChange / resultList.value.length).toFixed(2)
})

const coreReasonDictionary: Array<[RegExp, string]> = [
  [/strategy target=/gi, '策略目标：'],
  [/策略目标=/g, '策略目标：'],
  [/data advice=/gi, '数据建议：'],
  [/数据建议=/g, '数据建议：'],
  [/market advice=/gi, '市场建议：'],
  [/市场建议=/g, '市场建议：'],
  [/risk advice=/gi, '风险建议：'],
  [/风险建议=/g, '风险建议：'],
  [/overall suggestion=/gi, '综合建议：'],
  [/综合建议=/g, '综合建议：'],
  [/core factors=/gi, '核心因素：'],
  [/核心因子=/g, '核心因素：'],
  [/confidence=/gi, '可信度：'],
  [/\bMAX_PROFIT\b/g, '利润优先'],
  [/\bCLEARANCE\b/g, '清仓促销'],
  [/\bMARKET_SHARE\b/g, '市场份额优先'],
  [/\bmaintain\b/g, '维持当前价格'],
  [/\bdiscount\b/g, '建议降价'],
  [/\bincrease\b/g, '建议提价'],
  [/\braise\b/g, '建议提价'],
  [/\bconservative\b/g, '保守调整'],
  [/\baggressive\b/g, '积极调整'],
  [/\blow\b/g, '低'],
  [/\bmedium\b/g, '中'],
  [/\bhigh\b/g, '高']
]

let socket: WebSocket | null = null
let logSyncTimer: number | null = null

const loadProducts = async (query: string, page: number, append = false) => {
  searchLoading.value = true
  try {
    const res: any = await getProductList({ page, size: 20, keyword: query })
    if (res.code !== 200) return

    if (append) {
      const newItems = res.data.records.filter(
        (newItem: ProductOption) => !productOptions.value.some((oldItem) => oldItem.id === newItem.id)
      )
      productOptions.value = [...productOptions.value, ...newItems]
    } else {
      productOptions.value = res.data.records
      const missingSelected = selectedProducts.value.filter(
        (selectedItem) => !productOptions.value.some((option) => option.id === selectedItem.id)
      )
      productOptions.value = [...missingSelected, ...productOptions.value]
    }

    productTotal.value = res.data.total
    productPage.value = page
    currentQuery.value = query
  } finally {
    searchLoading.value = false
  }
}

const searchProducts = (query: string) => {
  loadProducts(query, 1, false)
}

const loadMoreProducts = () => {
  if (productOptions.value.length < productTotal.value) {
    loadProducts(currentQuery.value, productPage.value + 1, true)
  }
}

const handleProductChange = (value: number[]) => {
  selectedProducts.value = productOptions.value.filter((item) => value.includes(item.id))
}

const startTask = async () => {
  if (taskConfig.productIds.length === 0) {
    ElMessage.warning('请至少选择一个商品')
    return
  }
  if (!taskConfig.strategyGoal) {
    ElMessage.warning('请选择策略目标')
    return
  }

  starting.value = true
  try {
    const res: any = await startDecisionTask(taskConfig)
    if (res.code !== 200) {
      ElMessage.error(res.message || '启动任务失败')
      return
    }

    currentTaskId.value = res.data
    activeStep.value = 1
    progress.value = 5
    resultList.value = []
    chatMessages.value = []

    connectWebSocket(res.data)
    fetchTaskLogs(res.data)
    startLogSync(res.data)
  } catch {
    ElMessage.error('启动智能决策失败')
  } finally {
    starting.value = false
  }
}

const connectWebSocket = (taskId: number) => {
  closeSocket()
  socketStatus.value = 'connecting'

  const wsBase = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'
  socket = new WebSocket(`${wsBase}/ws/decision/${taskId}`)

  socket.onopen = () => {
    socketStatus.value = 'connected'
  }

  socket.onmessage = async (event) => {
    try {
      const data = JSON.parse(event.data)

      if (data.type === 'result') {
        progress.value = 100
        await fetchTaskLogs(taskId)
        return
      }

      if (data.type === 'complete') {
        progress.value = 100
        await fetchTaskLogs(taskId)
        stopLogSync()
        return
      }

      if (data.type === 'error') {
        ElMessage.error(data.message || '任务执行异常')
        await fetchTaskLogs(taskId)
        return
      }

      if (data.type === 'market_unavailable') {
        ElMessage.warning(data.message || '无法生成竞品市场样本')
        return
      }

      if (!data.is_stream || data.agent_role === '系统') {
        return
      }

      const role = data.agent_role || '角色'
      const productId = Number(data.product_id || 0)
      const stepOrder = Number(data.step_order || 0)

      if (data.is_start) {
        upsertStreamingMessage(role, productId, stepOrder, '', data.timestamp)
        progress.value = Math.min(Math.max(progress.value, ((stepOrder || 0) / 4) * 100), 95)
        scrollToBottom()
        return
      }

      if (data.is_end) {
        markStreamingEnded(role, productId, stepOrder)
        scrollToBottom()
        return
      }

      appendStreamingChunk(role, productId, stepOrder, data.thought_content || '', data.timestamp)
      scrollToBottom()
    } catch (error) {
      console.error('WS parse error', error)
    }
  }

  socket.onerror = async () => {
    socketStatus.value = 'disconnected'
    await fetchTaskLogs(taskId)
  }

  socket.onclose = async () => {
    socketStatus.value = 'disconnected'
    await fetchTaskLogs(taskId)
  }
}

const closeSocket = () => {
  if (socket) {
    socket.close()
    socket = null
  }
}

const buildMessageDomKey = (message: ChatMessage) =>
  `${message.agent_role}|${message.product_id || 0}|${message.step_order || 0}`

const findMessageByIdentity = (role: string, productId?: number, stepOrder?: number) =>
  chatMessages.value.find(
    (message) =>
      message.agent_role === role &&
      (message.product_id || 0) === (productId || 0) &&
      (message.step_order || 0) === (stepOrder || 0)
  )

const upsertStreamingMessage = (
  role: string,
  productId: number,
  stepOrder: number,
  content: string,
  timestamp?: string
) => {
  const existing = findMessageByIdentity(role, productId, stepOrder)
  if (existing) {
    existing.thought_content = content || existing.thought_content
    existing.timestamp = timestamp || existing.timestamp
    existing.streaming = true
    return existing
  }

  const message: ChatMessage = {
    agent_role: role,
    product_id: productId,
    step_order: stepOrder,
    thought_content: content,
    timestamp: timestamp || new Date().toLocaleTimeString(),
    streaming: true
  }
  chatMessages.value.push(message)
  return message
}

const appendStreamingChunk = (
  role: string,
  productId: number,
  stepOrder: number,
  content: string,
  timestamp?: string
) => {
  const message = findMessageByIdentity(role, productId, stepOrder)
  if (message) {
    message.thought_content += content
    if (timestamp) message.timestamp = timestamp
    message.streaming = true
    return
  }

  upsertStreamingMessage(role, productId, stepOrder, content, timestamp)
}

const markStreamingEnded = (role: string, productId: number, stepOrder: number) => {
  const message = findMessageByIdentity(role, productId, stepOrder)
  if (message) {
    message.streaming = false
  }
}

const fetchTaskLogs = async (taskId: number) => {
  try {
    const res: any = await getTaskLogs(taskId)
    if (res.code !== 200 || !Array.isArray(res.data)) return
    mergeHistoricalLogs(res.data as TaskLogRecord[])
  } catch (error) {
    console.error('Fetch task logs failed', error)
  }
}

const normalizeContent = (content: string) => content.replace(/\s+/g, ' ').trim()

const parseProductIdFromContent = (content: string) => {
  const match = content.match(/^商品\s+(\d+)\s*\n/)
  return match ? Number(match[1]) : 0
}

const stripProductHeader = (content: string) => content.replace(/^商品\s+\d+\s*\n/, '')

const mergeHistoricalLogs = (logs: TaskLogRecord[]) => {
  for (const log of logs) {
    const role = log.roleName || log.role_name || '角色'
    if (role === '系统') continue

    const rawContent = log.thoughtContent || log.thought_content || ''
    const content = stripProductHeader(rawContent)
    if (!normalizeContent(content)) continue

    const productId = parseProductIdFromContent(rawContent)
    const stepOrder = Number(log.speakOrder || log.speak_order || 0)
    const timestamp = formatLogTimestamp(log.createdAt)
    const existing = findMessageByIdentity(role, productId, stepOrder)

    if (existing) {
      existing.thought_content = content
      existing.timestamp = timestamp
      existing.streaming = false
      continue
    }

    chatMessages.value.push({
      agent_role: role,
      product_id: productId,
      step_order: stepOrder,
      thought_content: content,
      timestamp,
      streaming: false
    })
  }

  if (chatMessages.value.length > 0) {
    progress.value = Math.max(progress.value, Math.min(chatMessages.value.length * 20, 95))
  }

  scrollToBottom()
}

const startLogSync = (taskId: number) => {
  stopLogSync()
  logSyncTimer = window.setInterval(() => {
    fetchTaskLogs(taskId)
  }, 800)
}

const stopLogSync = () => {
  if (logSyncTimer !== null) {
    window.clearInterval(logSyncTimer)
    logSyncTimer = null
  }
}

const formatLogTimestamp = (value?: string) => {
  if (!value) return new Date().toLocaleTimeString()
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleTimeString()
}

const scrollToBottom = () => {
  nextTick(() => {
    if (chatBoxRef.value) {
      chatBoxRef.value.scrollTop = chatBoxRef.value.scrollHeight
    }
  })
}

const getAgentClass = (role: string) => {
  if (role.includes('数据')) return 'agent-data'
  if (role.includes('市场')) return 'agent-market'
  if (role.includes('风控') || role.includes('风险')) return 'agent-risk'
  if (role.includes('经理')) return 'agent-manager'
  return 'agent-default'
}

const getAgentAvatar = (role: string) => {
  if (role.includes('数据')) return '数据'
  if (role.includes('市场')) return '市场'
  if (role.includes('风控') || role.includes('风险')) return '风控'
  if (role.includes('经理')) return '经理'
  return '角色'
}

const formatContent = (content: string) => {
  if (!content) return ''
  return content.replace(/=/g, '：').replace(/\n/g, '<br>')
}

const formatCoreReasons = (content?: string) => {
  if (!content) return '-'
  let text = content
  for (const [pattern, replacement] of coreReasonDictionary) {
    text = text.replace(pattern, replacement)
  }
  text = text.replace(/=/g, '：')
  return text
}

const viewResult = async () => {
  if (!currentTaskId.value) return

  try {
    const resultRes: any = await getTaskResult(currentTaskId.value)
    if (resultRes.code !== 200) {
      ElMessage.error(resultRes.message || '获取结果报告失败')
      return
    }

    resultList.value = (resultRes.data || []).map((item: any) => {
      return {
        ...item,
        originalPrice: Number(item?.originalPrice || 0),
        profitChange: Number(item?.profitChange || 0),
        adoptStatus: item.adoptStatus || (item.isAccepted ? 'ADOPTED' : 'PENDING')
      }
    })
    activeStep.value = 2
    stopLogSync()
  } catch {
    ElMessage.error('获取结果报告失败')
  }
}

const acceptPrice = async (row: any) => {
  const resultId = Number(row.id || 0)
  const productName = row.productTitle || row.title || `ID ${row.productId}`
  if (!resultId) {
    ElMessage.error('未找到可应用的结果记录')
    return
  }
  if (applyingResultIds.value.includes(resultId)) {
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认将商品“${productName}”的售价更新为 ${Number(row.suggestedPrice || 0).toFixed(2)} 吗？`,
      '应用价格建议',
      {
        type: 'warning',
        confirmButtonText: '确认应用',
        cancelButtonText: '取消'
      }
    )
    applyingResultIds.value.push(resultId)
    const res: any = await applyDecision(resultId)
    if (res.code === 200) {
      row.isAccepted = true
      row.adoptStatus = 'ADOPTED'
      ElMessage.success(`已应用建议价格：${row.suggestedPrice}`)
      return
    }
    ElMessage.error(res.message || '应用失败')
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('应用失败')
    }
  } finally {
    applyingResultIds.value = applyingResultIds.value.filter((id) => id !== resultId)
  }
}

const resetToConfig = () => {
  activeStep.value = 0
  progress.value = 0
}

onMounted(() => {
  loadProducts('', 1, false)
})

onUnmounted(() => {
  stopLogSync()
  closeSocket()
})
</script>

<style scoped>
.pricing-page {
  gap: 14px;
}

.step-panel,
.config-panel,
.helper-panel,
.log-panel,
.status-panel {
  padding: 22px;
}

.compact-metrics {
  margin-top: 10px;
  gap: 10px;
}

.metric-value.small {
  font-size: 22px;
}

.steps {
  padding-top: 0;
}

.step-panel {
  padding: 14px 16px;
}

.step-panel .section-title p {
  font-size: 12px;
  line-height: 1.5;
}

.step-panel .section-head {
  margin-bottom: 10px;
}

.steps :deep(.el-step__description) {
  display: none;
}

.steps :deep(.el-step__title) {
  font-size: 13px;
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

.load-more {
  padding: 8px 12px 4px;
}

.tips-list {
  display: grid;
  gap: 14px;
}

.tip-item {
  display: grid;
  gap: 6px;
  padding: 16px;
  border-radius: 10px;
  background: var(--surface-2);
  border: 1px solid var(--line-soft);
}

.tip-item strong,
.tip-item span {
  margin: 0;
}

.tip-item span {
  color: var(--text-2);
  line-height: 1.7;
}

.summary-card {
  margin-top: 18px;
  display: grid;
  gap: 10px;
  padding: 18px;
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(15, 123, 108, 0.08), rgba(255, 255, 255, 0.9));
  border: 1px solid rgba(15, 123, 108, 0.12);
}

.summary-title {
  font-weight: 700;
}

.summary-line {
  color: var(--text-2);
  line-height: 1.7;
}

.execution-layout {
  align-items: start;
}

.side-column {
  display: grid;
  gap: 18px;
}

.chat-stream {
  max-height: 72vh;
  overflow-y: auto;
  display: grid;
  gap: 14px;
  padding-right: 4px;
}

.message-card {
  display: flex;
  gap: 14px;
  padding: 16px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid var(--line-soft);
}

.message-card.streaming {
  border-color: rgba(31, 111, 235, 0.35);
  box-shadow: 0 0 0 1px rgba(31, 111, 235, 0.12) inset;
}

.message-avatar {
  width: 54px;
  height: 54px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  color: #fff;
  font-size: 14px;
  font-weight: 800;
  flex-shrink: 0;
}

.message-main {
  min-width: 0;
  flex: 1;
}

.message-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.message-head strong {
  font-size: 15px;
}

.message-head span {
  color: var(--text-3);
  font-size: 12px;
}

.message-body {
  color: var(--text-1);
  line-height: 1.8;
}

.message-body p {
  margin: 0;
}

.typing-placeholder {
  color: var(--text-2);
  font-style: italic;
}

.message-card.streaming .message-body p::after {
  content: '▍';
  margin-left: 2px;
  color: var(--brand);
  animation: cursor-blink 1s infinite;
}

@keyframes cursor-blink {
  0%,
  50% {
    opacity: 1;
  }
  50.01%,
  100% {
    opacity: 0;
  }
}

.agent-data .message-avatar {
  background: linear-gradient(145deg, #2f80ed, #2d66d1);
}

.agent-market .message-avatar {
  background: linear-gradient(145deg, #18a77b, #0f7b6c);
}

.agent-risk .message-avatar {
  background: linear-gradient(145deg, #f05d5e, #d94a4d);
}

.agent-manager .message-avatar {
  background: linear-gradient(145deg, #db9630, #bc6d1d);
}

.agent-default .message-avatar {
  background: linear-gradient(145deg, #74828c, #5f6d76);
}

.status-list {
  display: grid;
  gap: 12px;
  margin-top: 18px;
}

.status-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 10px;
  background: var(--surface-2);
}

.status-item span {
  color: var(--text-2);
}

.full-width :deep(.el-button) {
  width: 100%;
}

.price-text {
  font-weight: 700;
  color: var(--accent);
}

@media (max-width: 1200px) {
  .chat-stream {
    max-height: 60vh;
  }
}

@media (max-width: 768px) {
  .step-panel,
  .config-panel,
  .helper-panel,
  .log-panel,
  .status-panel {
    padding: 16px;
  }

  .message-card {
    padding: 14px;
  }

  .message-head {
    flex-direction: column;
  }
}
</style>

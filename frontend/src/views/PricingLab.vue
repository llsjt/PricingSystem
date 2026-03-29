<template>
  <div class="page-shell pricing-page">
    <section class="panel-card step-panel">
      <div class="section-head">
        <div class="section-title">
          <h3>任务流程</h3>
          <p>新的任务模型基于单商品单任务设计，决策过程和结果都会直接落到 Java 后端。</p>
        </div>
      </div>

      <el-steps :active="stepBarActive" finish-status="success" align-center class="steps">
        <el-step title="配置任务" />
        <el-step title="查看日志" />
        <el-step title="确认结果" />
      </el-steps>
    </section>

    <div v-if="activeStep === 0" class="responsive-two">
      <section class="panel-card config-panel">
        <div class="section-head">
          <div class="section-title">
            <h3>任务配置</h3>
            <p>每次针对单个商品创建一个定价任务，更符合新的 `pricing_task / pricing_result` 结构。</p>
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
              <el-option
                v-for="item in productOptions"
                :key="item.id"
                :label="item.productName"
                :value="item.id"
              >
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
              :rows="5"
              placeholder="例如：利润率不低于 15%，降价幅度不超过 10%，最低售价不低于 69 元"
            />
          </el-form-item>

          <div class="toolbar-actions">
            <el-button :loading="starting" type="primary" size="large" @click="startTask">启动智能决策</el-button>
          </div>
        </el-form>
      </section>

      <section class="panel-card helper-panel">
        <div class="section-head">
          <div class="section-title">
            <h3>配置摘要</h3>
            <p>开始前确认目标、商品与约束是否一致。</p>
          </div>
        </div>

        <div class="summary-card">
          <div class="summary-title">当前任务</div>
          <div class="summary-line">商品：{{ selectedProductName || '尚未选择' }}</div>
          <div class="summary-line">目标：{{ strategyGoalText }}</div>
          <div class="summary-line">约束：{{ taskConfig.constraints || '未设置' }}</div>
        </div>

        <div class="tips-list">
          <article class="tip-item">
            <strong>利润优先</strong>
            <span>系统会优先比较不同候选价格的预估利润，再决定最终售价。</span>
          </article>
          <article class="tip-item">
            <strong>清仓促销</strong>
            <span>系统会更偏向低价策略，但仍会受最低利润率和最低售价约束。</span>
          </article>
          <article class="tip-item">
            <strong>市场份额优先</strong>
            <span>系统会在风控允许范围内适当偏向更高销量的建议区间。</span>
          </article>
        </div>
      </section>
    </div>

    <div v-else-if="activeStep === 1" class="responsive-two execution-layout">
      <section class="panel-card log-panel">
        <div class="section-head">
          <div class="section-title">
            <h3>决策日志</h3>
            <p>这里展示 Java 后端生成的四个阶段日志：数据分析、市场情报、风险控制和决策经理。</p>
          </div>
        </div>

        <div class="chat-stream">
          <el-empty v-if="taskLogs.length === 0" description="暂无日志" />
          <article
            v-for="log in orderedLogs"
            :key="log.id"
            :class="['message-card', getAgentClass(log)]"
          >
            <div class="message-avatar">{{ getAgentAvatar(log) }}</div>
            <div class="message-main">
              <div class="message-head">
                <strong>{{ getAgentLabel(log) }}</strong>
                <span>{{ formatTime(log.createdAt) }}</span>
              </div>
              <div class="message-body">
                <p v-html="formatContent(log.outputSummary)"></p>
              </div>
              <div class="message-meta">
                <span>建议价：{{ formatCurrency(log.suggestedPrice) }}</span>
                <span>预估利润：{{ formatCurrency(log.predictedProfit) }}</span>
                <span>风险：{{ log.riskLevel || '-' }}</span>
              </div>
            </div>
          </article>
        </div>
      </section>

      <div class="side-column">
        <section class="panel-card status-panel">
          <div class="section-head">
            <div class="section-title">
              <h3>任务状态</h3>
              <p>任务在 Java 后端同步执行，日志和结果会一并落库。</p>
            </div>
          </div>

          <el-progress :percentage="progress" :stroke-width="12" :status="progress === 100 ? 'success' : ''" />

          <div class="status-list">
            <div class="status-item">
              <span>任务 ID</span>
              <strong>{{ currentTaskId || '-' }}</strong>
            </div>
            <div class="status-item">
              <span>日志条数</span>
              <strong>{{ taskLogs.length }}</strong>
            </div>
            <div class="status-item">
              <span>执行状态</span>
              <strong>{{ progress === 100 ? '已完成' : '处理中' }}</strong>
            </div>
          </div>

          <div class="toolbar-actions full-width">
            <el-button v-if="comparisonData.length > 0" type="primary" @click="viewResult">查看最终报告</el-button>
          </div>
        </section>

        <section class="panel-card status-panel">
          <div class="section-head">
            <div class="section-title">
              <h3>执行摘要</h3>
              <p>便于快速确认当前任务上下文。</p>
            </div>
          </div>

          <div class="summary-line">商品：{{ selectedProductName || '-' }}</div>
          <div class="summary-line">目标：{{ strategyGoalText }}</div>
          <div class="summary-line">约束：{{ taskConfig.constraints || '无' }}</div>
        </section>
      </div>
    </div>

    <div v-else class="page-shell">
      <section class="metric-grid">
        <article class="metric-card">
          <div class="metric-label">建议售价</div>
          <div class="metric-value">{{ formatCurrency(firstResult?.suggestedPrice) }}</div>
          <div class="metric-hint">最终建议价格</div>
        </article>
        <article class="metric-card">
          <div class="metric-label">预期销量</div>
          <div class="metric-value">{{ firstResult?.expectedSales || 0 }}</div>
          <div class="metric-hint">按当前策略估算的销量</div>
        </article>
        <article class="metric-card">
          <div class="metric-label">利润变化</div>
          <div class="metric-value">{{ formatSignedCurrency(firstResult?.profitChange) }}</div>
          <div class="metric-hint">相对基线利润的变化额</div>
        </article>
      </section>

      <section class="panel-card table-card">
        <div class="section-head">
          <div class="section-title">
            <h3>结果报告</h3>
            <p>确认建议价格、预期收益、风控结果和执行策略。</p>
          </div>
          <div class="toolbar-actions">
            <el-button @click="resetToConfig">重新配置</el-button>
          </div>
        </div>

        <el-table :data="comparisonData" border stripe>
          <el-table-column prop="productTitle" label="商品名称" min-width="180" show-overflow-tooltip />
          <el-table-column label="原价" width="120">
            <template #default="{ row }">{{ formatCurrency(row.originalPrice) }}</template>
          </el-table-column>
          <el-table-column label="建议价" width="120">
            <template #default="{ row }"><span class="price-text">{{ formatCurrency(row.suggestedPrice) }}</span></template>
          </el-table-column>
          <el-table-column label="预期销量" width="110">
            <template #default="{ row }">{{ row.expectedSales || 0 }}</template>
          </el-table-column>
          <el-table-column label="预期利润" width="120">
            <template #default="{ row }">{{ formatCurrency(row.expectedProfit) }}</template>
          </el-table-column>
          <el-table-column label="利润变化" width="120">
            <template #default="{ row }">
              <el-tag :type="Number(row.profitChange || 0) >= 0 ? 'success' : 'danger'">
                {{ formatSignedCurrency(row.profitChange) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="passStatus" label="风控结果" width="100" />
          <el-table-column prop="executeStrategy" label="执行策略" width="120" />
          <el-table-column prop="resultSummary" label="结果说明" min-width="320" show-overflow-tooltip />
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-tag v-if="row.appliedStatus === '已应用'" type="success">已应用</el-tag>
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
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { applyDecision, getTaskLogStreamUrl, getTaskLogs, getTaskResult, startDecisionTask } from '../api/decision'
import { getProductList } from '../api/product'

interface ProductOption {
  id: number
  productName: string
}

const activeStep = ref(0)
const starting = ref(false)
const searchLoading = ref(false)
const productOptions = ref<ProductOption[]>([])
const currentTaskId = ref<number | null>(null)
const taskLogs = ref<any[]>([])
const comparisonData = ref<any[]>([])
const applyingResultIds = ref<number[]>([])
let latestProductLoadToken = 0
let logStream: EventSource | null = null
let streamCompleted = false

const taskConfig = reactive({
  productId: undefined as number | undefined,
  strategyGoal: 'MAX_PROFIT',
  constraints: ''
})

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
  return mapping[taskConfig.strategyGoal] || taskConfig.strategyGoal
})

const selectedProductName = computed(() => {
  return productOptions.value.find((item) => item.id === taskConfig.productId)?.productName || ''
})

const orderedLogs = computed(() =>
  [...taskLogs.value].sort((a, b) => Number(a.runOrder || 0) - Number(b.runOrder || 0))
)

const firstResult = computed(() => comparisonData.value[0] || null)

const progress = computed(() => {
  if (comparisonData.value.length > 0) return 100
  if (taskLogs.value.length > 0) return 70
  if (currentTaskId.value) return 35
  return 0
})

const loadProducts = async (query = '') => {
  const loadToken = ++latestProductLoadToken
  searchLoading.value = true
  try {
    const pageSize = 100
    const allProducts: ProductOption[] = []
    let page = 1
    let pages = 1

    while (page <= pages) {
      const res: any = await getProductList({ page, size: pageSize, keyword: query })
      if (loadToken !== latestProductLoadToken) return
      if (res.code !== 200) break

      const records = Array.isArray(res.data?.records) ? res.data.records : []
      records.forEach((item: any) => {
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

const searchProducts = (query: string) => {
  loadProducts(query)
}

const fetchTaskLogs = async (taskId: number) => {
  const res: any = await getTaskLogs(taskId)
  if (res.code === 200) {
    taskLogs.value = res.data || []
  }
}

const fetchTaskResult = async (taskId: number) => {
  const res: any = await getTaskResult(taskId)
  if (res.code === 200) {
    comparisonData.value = res.data || []
  }
}

const upsertTaskLog = (logItem: any) => {
  if (!logItem) return
  const id = Number(logItem.id || 0)
  if (id <= 0) return
  const idx = taskLogs.value.findIndex((item) => Number(item?.id || 0) === id)
  if (idx >= 0) {
    taskLogs.value[idx] = logItem
    return
  }
  taskLogs.value.push(logItem)
}

const stopLogStream = () => {
  if (logStream) {
    logStream.close()
    logStream = null
  }
}

const refreshTaskSnapshot = async (taskId: number) => {
  await Promise.all([fetchTaskLogs(taskId), fetchTaskResult(taskId)])
}

const startLogStream = (taskId: number) => {
  stopLogStream()
  streamCompleted = false
  const source = new EventSource(getTaskLogStreamUrl(taskId))
  logStream = source

  source.addEventListener('log', (event: MessageEvent) => {
    try {
      const payload = JSON.parse(event.data)
      upsertTaskLog(payload)
    } catch {
      // Ignore malformed event payload and keep stream alive.
    }
  })

  source.addEventListener('result', (event: MessageEvent) => {
    try {
      const payload = JSON.parse(event.data)
      comparisonData.value = Array.isArray(payload) ? payload : []
    } catch {
      comparisonData.value = []
    }
  })

  source.addEventListener('done', async () => {
    await refreshTaskSnapshot(taskId)
    if (!streamCompleted) {
      streamCompleted = true
      ElMessage.success('任务执行完成，结果已更新')
    }
    stopLogStream()
  })

  source.addEventListener('failed', async () => {
    await refreshTaskSnapshot(taskId)
    if (!streamCompleted) {
      streamCompleted = true
      ElMessage.error('任务执行失败，请查看日志')
    }
    stopLogStream()
  })

  source.onerror = async () => {
    stopLogStream()
    if (!streamCompleted) {
      // Stream disconnected unexpectedly, fallback to one-shot refresh.
      await refreshTaskSnapshot(taskId)
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
    const res: any = await startDecisionTask({
      productIds: [taskConfig.productId],
      strategyGoal: taskConfig.strategyGoal,
      constraints: taskConfig.constraints
    })
    if (res.code !== 200) {
      ElMessage.error(res.message || '启动任务失败')
      return
    }

    currentTaskId.value = res.data
    taskLogs.value = []
    comparisonData.value = []
    activeStep.value = 1

    startLogStream(res.data)
    ElMessage.success('任务已启动，Agent 日志将实时流式更新')
  } catch {
    ElMessage.error('启动智能决策失败')
  } finally {
    starting.value = false
  }
}

const viewResult = () => {
  if (comparisonData.value.length === 0) {
    ElMessage.warning('当前任务还没有结果')
    return
  }
  activeStep.value = 2
}

const applyPrice = async (row: any) => {
  const resultId = Number(row.resultId || 0)
  if (!resultId) {
    ElMessage.error('未找到可应用的结果记录')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认将商品“${row.productTitle}”的售价更新为 ${formatCurrency(row.suggestedPrice)} 吗？`,
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
      ElMessage.success('建议价格已应用')
      if (currentTaskId.value) {
        await fetchTaskResult(currentTaskId.value)
      }
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
  stopLogStream()
  streamCompleted = false
  activeStep.value = 0
  currentTaskId.value = null
  taskLogs.value = []
  comparisonData.value = []
}

const getAgentCode = (log: any) => String(log?.agentCode || '').toUpperCase()

const getAgentLabel = (log: any) => log?.agentName || log?.agentCode || 'Agent'

const getAgentClass = (log: any) => {
  const code = getAgentCode(log)
  if (code.includes('DATA')) return 'agent-data'
  if (code.includes('MARKET')) return 'agent-market'
  if (code.includes('RISK')) return 'agent-risk'
  if (code.includes('MANAGER')) return 'agent-manager'
  if (code.includes('CREWAI')) return 'agent-manager'
  return 'agent-default'
}

const getAgentAvatar = (log: any) => {
  const code = getAgentCode(log)
  if (code.includes('DATA')) return '数据'
  if (code.includes('MARKET')) return '市场'
  if (code.includes('RISK')) return '风控'
  if (code.includes('MANAGER')) return '经理'
  if (code.includes('CREWAI')) return '协作'
  return 'Agent'
}

const formatContent = (content?: string) => (content ? String(content).replace(/\n/g, '<br>') : '')
const formatTime = (value?: string) => (value ? new Date(value).toLocaleString() : '-')
const formatCurrency = (value?: number | string | null) => `¥${Number(value || 0).toFixed(2)}`
const formatSignedCurrency = (value?: number | string | null) => {
  const numeric = Number(value || 0)
  return `${numeric >= 0 ? '+' : '-'}¥${Math.abs(numeric).toFixed(2)}`
}

onMounted(() => {
  loadProducts()
})

onBeforeUnmount(() => {
  stopLogStream()
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

.steps {
  padding-top: 0;
}

.step-panel {
  padding: 14px 16px;
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

.summary-card {
  margin-bottom: 18px;
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

.message-body {
  color: var(--text-1);
  line-height: 1.8;
}

.message-body p {
  margin: 0;
}

.message-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 10px;
  color: var(--text-3);
  font-size: 12px;
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

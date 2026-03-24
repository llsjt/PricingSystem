<template>
  <div class="page-shell archive-page">
    <section class="panel-card archive-hero">
      <div class="section-title">
        <h2>决策档案</h2>
        <p>集中查看智能定价任务、执行结论和协同日志，支持筛选、复盘、应用与驳回。</p>
      </div>
      <div class="metric-grid compact-metrics">
        <article class="metric-card">
          <div class="metric-label">任务总数</div>
          <div class="metric-value">{{ total }}</div>
          <div class="metric-hint">当前筛选范围内的任务数量</div>
        </article>
        <article class="metric-card">
          <div class="metric-label">已完成</div>
          <div class="metric-value">{{ completedCount }}</div>
          <div class="metric-hint">可查看报告并导出明细</div>
        </article>
        <article class="metric-card">
          <div class="metric-label">执行中</div>
          <div class="metric-value">{{ runningCount }}</div>
          <div class="metric-hint">任务仍在等待 Agent 输出</div>
        </article>
      </div>
    </section>

    <section class="panel-card filter-panel">
      <div class="section-head">
        <div class="section-title">
          <h3>任务筛选</h3>
          <p>按状态、目标策略和时间范围快速定位任务。</p>
        </div>
      </div>

      <div class="toolbar-row filter-grid">
        <el-select v-model="queryParams.status" clearable placeholder="任务状态">
          <el-option
            v-for="item in statusOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>

        <el-select v-model="queryParams.strategyType" clearable placeholder="策略目标">
          <el-option
            v-for="item in strategyOptions"
            :key="item.value"
            :label="item.label"
            :value="item.value"
          />
        </el-select>

        <el-date-picker
          v-model="dateRange"
          type="datetimerange"
          range-separator="至"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          value-format="YYYY-MM-DD HH:mm:ss"
          @change="handleDateChange"
        />

        <div class="toolbar-actions">
          <el-button type="primary" @click="handleSearch">查询任务</el-button>
          <el-button @click="resetFilters">重置条件</el-button>
        </div>
      </div>
    </section>

    <section class="panel-card table-card">
      <div class="section-head">
        <div class="section-title">
          <h3>任务列表</h3>
          <p>支持排序和分页，点击任务即可查看详细报告与 Agent 协同记录。</p>
        </div>
      </div>

      <el-table
        v-loading="loading"
        :data="tasks"
        border
        stripe
        @sort-change="handleSortChange"
      >
        <el-table-column prop="id" label="任务 ID" width="92" />
        <el-table-column prop="taskNo" label="任务编号" min-width="220" show-overflow-tooltip />
        <el-table-column prop="productNames" label="涉及商品" min-width="240" show-overflow-tooltip />
        <el-table-column prop="strategyType" label="策略目标" width="140">
          <template #default="{ row }">
            <el-tag effect="plain">{{ strategyMap[row.strategyType] || row.strategyType }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusTypeMap[row.status]">{{ statusMap[row.status] || row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="180" sortable="custom">
          <template #default="{ row }">
            {{ formatDateTime(row.createdAt) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" fixed="right" width="110">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewDetails(row)">查看详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-footer">
        <el-pagination
          v-model:current-page="queryParams.page"
          v-model:page-size="queryParams.size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="fetchTasks"
          @current-change="fetchTasks"
        />
      </div>
    </section>

    <el-drawer
      v-model="drawerVisible"
      :size="drawerSize"
      :destroy-on-close="true"
      class="archive-drawer"
      title="任务详情"
    >
      <div v-if="currentTask" class="drawer-meta">
        <div class="drawer-meta-item">
          <span>任务编号</span>
          <strong>{{ currentTask.taskNo }}</strong>
        </div>
        <div class="drawer-meta-item">
          <span>创建时间</span>
          <strong>{{ formatDateTime(currentTask.createdAt) }}</strong>
        </div>
        <div class="drawer-meta-item">
          <span>策略目标</span>
          <strong>{{ strategyMap[currentTask.strategyType] || currentTask.strategyType }}</strong>
        </div>
        <div class="drawer-meta-item">
          <span>任务状态</span>
          <strong>{{ statusMap[currentTask.status] || currentTask.status }}</strong>
        </div>
      </div>

      <el-tabs v-model="activeTab" class="detail-tabs">
        <el-tab-pane label="结果报告" name="comparison">
          <div class="drawer-actions">
            <el-button
              type="primary"
              plain
              :disabled="!currentTask || currentTask.status !== 'COMPLETED'"
              @click="exportReport"
            >
              导出报告
            </el-button>
          </div>

          <div v-loading="detailLoading" class="report-layout">
            <section class="metric-grid compact-metrics">
              <article class="metric-card">
                <div class="metric-label">建议商品数</div>
                <div class="metric-value">{{ comparisonData.length }}</div>
                <div class="metric-hint">参与本次价格建议的商品数量</div>
              </article>
              <article class="metric-card">
                <div class="metric-label">平均折扣率</div>
                <div class="metric-value">{{ averageDiscountRate }}</div>
                <div class="metric-hint">综合结果的平均价格调整幅度</div>
              </article>
              <article class="metric-card">
                <div class="metric-label">平均利润变化</div>
                <div class="metric-value">{{ averageProfitDelta }}</div>
                <div class="metric-hint">用于快速评估策略收益预期</div>
              </article>
            </section>

            <section class="panel-card embedded-panel">
              <el-table :data="comparisonData" border stripe>
                <el-table-column prop="productTitle" label="商品名称" min-width="180" show-overflow-tooltip />
                <el-table-column label="原价" width="120">
                  <template #default="{ row }">
                    {{ formatCurrency(row.originalPrice) }}
                  </template>
                </el-table-column>
                <el-table-column label="建议价" width="120">
                  <template #default="{ row }">
                    {{ formatCurrency(row.suggestedPrice) }}
                  </template>
                </el-table-column>
                <el-table-column label="利润变化" min-width="140">
                  <template #default="{ row }">
                    <span :class="Number(row.profitChange || 0) >= 0 ? 'up' : 'down'">
                      {{ formatCurrency(Number(row.profitChange || 0)) }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column label="折扣率" width="110">
                  <template #default="{ row }">
                    {{ formatPercent(row.discountRate) }}
                  </template>
                </el-table-column>
                <el-table-column label="采纳状态" width="120">
                  <template #default="{ row }">
                    <el-tag v-if="row.adoptStatus === 'ADOPTED'" type="success">已应用</el-tag>
                    <el-tag v-else-if="row.adoptStatus === 'REJECTED'" type="danger">已驳回</el-tag>
                    <el-tag v-else type="info">待处理</el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="操作" fixed="right" width="150">
                  <template #default="{ row }">
                    <div v-if="!row.adoptStatus || row.adoptStatus === 'PENDING'" class="inline-actions">
                      <el-button link type="primary" @click="applyPrice(row)">应用</el-button>
                      <el-button link type="danger" @click="openRejectDialog(row)">驳回</el-button>
                    </div>
                    <span v-else-if="row.adoptStatus === 'REJECTED'">{{ row.rejectReason || '已驳回' }}</span>
                    <span v-else>已应用</span>
                  </template>
                </el-table-column>
              </el-table>
            </section>

            <section class="panel-card embedded-panel">
              <div class="section-head">
                <div class="section-title">
                  <h3>价格对比</h3>
                  <p>直观对比原始价格和建议价格，辅助判断调整区间。</p>
                </div>
              </div>
              <div ref="chartRef" class="comparison-chart"></div>
            </section>
          </div>
        </el-tab-pane>

        <el-tab-pane label="协同日志" name="logs">
          <div class="logs-panel">
            <article v-for="log in agentLogs" :key="log.id" class="log-card">
              <div class="log-head">
                <strong>{{ log.roleName || log.agentRole || 'Agent' }}</strong>
                <span>{{ formatDateTime(log.createdAt) }}</span>
              </div>
              <div class="log-body" v-html="formatContent(log.thoughtContent)"></div>
            </article>
            <el-empty v-if="agentLogs.length === 0" description="暂无协同日志" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-drawer>

    <el-dialog v-model="rejectDialogVisible" title="驳回建议" width="420px">
      <el-form label-position="top">
        <el-form-item label="驳回原因">
          <el-input
            v-model="rejectReason"
            type="textarea"
            :rows="4"
            placeholder="请输入驳回该价格建议的原因"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="submitReject">确认驳回</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import request from '../api/request'

const dateRange = ref<string[]>([])
const loading = ref(false)
const tasks = ref<any[]>([])
const total = ref(0)

const drawerVisible = ref(false)
const activeTab = ref('comparison')
const currentTask = ref<any>(null)
const detailLoading = ref(false)
const comparisonData = ref<any[]>([])
const originalResults = ref<any[]>([])
const agentLogs = ref<any[]>([])

const rejectDialogVisible = ref(false)
const rejectReason = ref('')
const currentRejectRow = ref<any>(null)

const chartRef = ref<HTMLElement | null>(null)
const viewportWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1440)
let chartInstance: echarts.ECharts | null = null

const queryParams = reactive({
  page: 1,
  size: 10,
  status: '',
  strategyType: '',
  startTime: '',
  endTime: '',
  sortOrder: 'desc'
})

const strategyMap: Record<string, string> = {
  CLEARANCE: '清仓促销',
  MAX_PROFIT: '利润优先',
  MARKET_SHARE: '市场份额优先',
  销量最大化: '清仓促销',
  清仓大甩卖: '清仓促销',
  利润最大化: '利润优先',
  市场份额优先: '市场份额优先'
}

const statusMap: Record<string, string> = {
  PENDING: '等待中',
  RUNNING: '执行中',
  COMPLETED: '已完成',
  FAILED: '失败'
}

const statusTypeMap: Record<string, 'info' | 'warning' | 'success' | 'danger'> = {
  PENDING: 'info',
  RUNNING: 'warning',
  COMPLETED: 'success',
  FAILED: 'danger'
}

const statusOptions = [
  { label: '执行中', value: 'RUNNING' },
  { label: '已完成', value: 'COMPLETED' },
  { label: '失败', value: 'FAILED' }
]

const strategyOptions = [
  { label: '利润优先', value: 'MAX_PROFIT' },
  { label: '清仓促销', value: 'CLEARANCE' },
  { label: '市场份额优先', value: 'MARKET_SHARE' }
]

const completedCount = ref(0)
const runningCount = ref(0)
const drawerSize = computed(() => (viewportWidth.value < 900 ? '100%' : '78%'))

const averageDiscountRate = computed(() => {
  if (!comparisonData.value.length) return '--'
  const totalRate = comparisonData.value.reduce((sum, item) => sum + Number(item.discountRate || 0), 0)
  return `${((totalRate / comparisonData.value.length) * 100).toFixed(1)}%`
})

const averageProfitDelta = computed(() => {
  if (!comparisonData.value.length) return '--'
  const delta = comparisonData.value.reduce((sum, item) => sum + Number(item.profitChange || 0), 0)
  return formatCurrency(delta / comparisonData.value.length)
})

const formatDateTime = (dateStr?: string) => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  if (Number.isNaN(date.getTime())) return dateStr
  const year = date.getFullYear()
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')
  const hour = `${date.getHours()}`.padStart(2, '0')
  const minute = `${date.getMinutes()}`.padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}`
}

const formatCurrency = (value: number | string) => `¥${Number(value || 0).toFixed(2)}`

const formatPercent = (value: number | string) => `${(Number(value || 0) * 100).toFixed(0)}%`

const formatContent = (text?: string) => (text ? text.replace(/=/g, '：').replace(/\n/g, '<br>') : '')

const handleSearch = () => {
  queryParams.page = 1
  fetchTasks()
}

const resetFilters = () => {
  queryParams.page = 1
  queryParams.status = ''
  queryParams.strategyType = ''
  queryParams.startTime = ''
  queryParams.endTime = ''
  queryParams.sortOrder = 'desc'
  dateRange.value = []
  fetchTasks()
}

const handleDateChange = (value?: string[]) => {
  if (value && value.length === 2) {
    queryParams.startTime = value[0]
    queryParams.endTime = value[1]
  } else {
    queryParams.startTime = ''
    queryParams.endTime = ''
  }
}

const handleSortChange = ({ prop, order }: { prop: string; order: string | null }) => {
  if (prop !== 'createdAt') return
  queryParams.sortOrder = order === 'ascending' ? 'asc' : 'desc'
  fetchTasks()
}

const fetchTasks = async () => {
  loading.value = true
  try {
    const res: any = await request.get('/decision/tasks', { params: queryParams })
    if (res.code === 200) {
      tasks.value = res.data.records || []
      total.value = res.data.total || 0
      await fetchTaskStats()
      return
    }
    ElMessage.error(res.message || '获取任务列表失败')
  } catch {
    ElMessage.error('获取任务列表失败')
  } finally {
    loading.value = false
  }
}

const fetchTaskStats = async () => {
  try {
    const params = {
      strategyType: queryParams.strategyType,
      startTime: queryParams.startTime,
      endTime: queryParams.endTime
    }
    const res: any = await request.get('/decision/tasks/stats', { params })
    if (res.code === 200) {
      completedCount.value = Number(res.data?.completed || 0)
      runningCount.value = Number(res.data?.running || 0)
    }
  } catch {
    completedCount.value = tasks.value.filter((item) => item.status === 'COMPLETED').length
    runningCount.value = tasks.value.filter((item) => item.status === 'RUNNING').length
  }
}

const viewDetails = async (row: any) => {
  currentTask.value = row
  drawerVisible.value = true
  activeTab.value = 'comparison'
  await Promise.all([fetchComparison(), fetchLogs()])
}

const fetchComparison = async () => {
  if (!currentTask.value) return
  detailLoading.value = true
  try {
    const [comparisonRes, resultRes] = await Promise.all([
      request.get(`/decision/comparison/${currentTask.value.id}`),
      request.get(`/decision/result/${currentTask.value.id}`)
    ])

    if (comparisonRes.code === 200) {
      comparisonData.value = comparisonRes.data || []
      await nextTick()
      renderChart()
    } else {
      ElMessage.error(comparisonRes.message || '获取结果报告失败')
    }

    if (resultRes.code === 200) {
      originalResults.value = resultRes.data || []
    }
  } catch {
    ElMessage.error('获取结果报告失败')
  } finally {
    detailLoading.value = false
  }
}

const fetchLogs = async () => {
  if (!currentTask.value) return
  try {
    const res: any = await request.get(`/decision/logs/${currentTask.value.id}`)
    if (res.code === 200) {
      agentLogs.value = res.data || []
    }
  } catch {
    agentLogs.value = []
  }
}

const getResultId = (productId: number) => {
  const result = originalResults.value.find((item) => Number(item.productId) === Number(productId))
  return result ? result.id : null
}

const applyPrice = async (row: any) => {
  const resultId = Number(row.resultId || getResultId(row.productId))
  if (!resultId) {
    ElMessage.error('未找到对应结果记录')
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

    const res: any = await request.post(`/decision/apply/${resultId}`)
    if (res.code === 200) {
      ElMessage.success('价格建议已应用')
      await fetchComparison()
      return
    }
    ElMessage.error(res.message || '应用失败')
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('应用失败')
    }
  }
}

const openRejectDialog = (row: any) => {
  currentRejectRow.value = row
  rejectReason.value = ''
  rejectDialogVisible.value = true
}

const submitReject = async () => {
  if (!currentRejectRow.value) return

  const resultId = Number(currentRejectRow.value.resultId || getResultId(currentRejectRow.value.productId))
  if (!resultId) {
    ElMessage.error('未找到对应结果记录')
    return
  }

  try {
    const res: any = await request.post(`/decision/reject/${resultId}`, { reason: rejectReason.value })
    if (res.code === 200) {
      ElMessage.success('价格建议已驳回')
      rejectDialogVisible.value = false
      await fetchComparison()
      return
    }
    ElMessage.error(res.message || '驳回失败')
  } catch {
    ElMessage.error('驳回失败')
  }
}

const exportReport = () => {
  if (!currentTask.value) return
  window.open(`/api/decision/export/${currentTask.value.id}`, '_blank')
}

const renderChart = () => {
  if (!chartRef.value || !comparisonData.value.length) return

  if (chartInstance) {
    chartInstance.dispose()
  }

  chartInstance = echarts.init(chartRef.value)
  chartInstance.setOption({
    color: ['#1f6feb', '#f59e0b'],
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    },
    legend: {
      top: 0,
      data: ['原价', '建议价']
    },
    grid: {
      top: 48,
      left: 12,
      right: 24,
      bottom: 12,
      containLabel: true
    },
    xAxis: {
      type: 'value'
    },
    yAxis: {
      type: 'category',
      data: comparisonData.value.map((item) => item.productTitle),
      axisLabel: {
        width: 120,
        overflow: 'truncate'
      }
    },
    series: [
      {
        name: '原价',
        type: 'bar',
        barMaxWidth: 16,
        data: comparisonData.value.map((item) => Number(item.originalPrice || 0))
      },
      {
        name: '建议价',
        type: 'bar',
        barMaxWidth: 16,
        data: comparisonData.value.map((item) => Number(item.suggestedPrice || 0))
      }
    ]
  })
}

const handleResize = () => {
  viewportWidth.value = window.innerWidth
  if (chartInstance) {
    chartInstance.resize()
  }
}

onMounted(() => {
  fetchTasks()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (chartInstance) {
    chartInstance.dispose()
  }
})
</script>

<style scoped>
.archive-page {
  gap: 14px;
}

.compact-metrics {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.archive-hero {
  padding: 14px 16px;
}

.archive-hero .section-title {
  gap: 4px;
  margin-bottom: 10px;
}

.archive-hero .section-title p {
  font-size: 13px;
  line-height: 1.45;
}

.archive-hero .compact-metrics {
  gap: 10px;
}

.archive-hero .metric-card {
  padding: 14px 16px;
}

.archive-hero .metric-value {
  margin-top: 6px;
  font-size: 34px;
}

.archive-hero .metric-hint {
  display: none;
}

.filter-panel {
  padding: 12px 14px;
}

.filter-panel .section-head {
  margin-bottom: 8px;
}

.filter-panel .section-title p {
  display: none;
}

.filter-grid {
  display: grid;
  grid-template-columns: 180px 200px minmax(280px, 1fr) auto;
  align-items: center;
  gap: 10px;
}

.filter-grid .toolbar-actions {
  justify-content: flex-end;
  flex-wrap: nowrap;
}

.filter-panel :deep(.el-input__wrapper),
.filter-panel :deep(.el-date-editor.el-input__wrapper),
.filter-panel :deep(.el-select__wrapper) {
  min-height: 36px;
}

.table-footer {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

.drawer-meta {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.drawer-meta-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
  border-radius: 10px;
  background: var(--panel-muted);
  color: var(--text-secondary);
}

.drawer-meta-item strong {
  color: var(--text-primary);
}

.drawer-actions {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}

.report-layout {
  display: grid;
  gap: 18px;
}

.embedded-panel {
  padding: 18px;
  border: 1px solid var(--border-soft);
  box-shadow: none;
}

.comparison-chart {
  width: 100%;
  height: 360px;
}

.logs-panel {
  display: grid;
  gap: 14px;
}

.log-card {
  padding: 18px 20px;
  border-radius: 10px;
  border: 1px solid var(--border-soft);
  background: linear-gradient(180deg, rgba(247, 250, 255, 0.96), #ffffff);
}

.log-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  color: var(--text-secondary);
}

.log-body {
  color: var(--text-primary);
  line-height: 1.8;
}

.inline-actions {
  display: flex;
  gap: 6px;
}

.up {
  color: #15803d;
  font-weight: 600;
}

.down {
  color: #b91c1c;
  font-weight: 600;
}

@media (max-width: 1200px) {
  .filter-grid,
  .drawer-meta,
  .compact-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filter-grid .toolbar-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 768px) {
  .filter-grid,
  .drawer-meta,
  .compact-metrics {
    grid-template-columns: 1fr;
  }

  .drawer-actions {
    justify-content: stretch;
  }

  .drawer-actions :deep(.el-button) {
    width: 100%;
  }
}
</style>

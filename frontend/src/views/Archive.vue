<template>
  <div class="page-shell archive-page">
    <section class="panel-card archive-hero">
      <div class="section-title">
        <h2>决策档案</h2>
        <p>统一查看新的定价任务、执行结果和协同日志，页面完全基于 `pricing_task / pricing_result / agent_run_log` 数据结构。</p>
      </div>
      <div class="metric-grid compact-metrics">
        <article class="metric-card">
          <div class="metric-label">任务总数</div>
          <div class="metric-value">{{ stats.total }}</div>
          <div class="metric-hint">按当前时间范围统计</div>
        </article>
        <article class="metric-card">
          <div class="metric-label">已完成</div>
          <div class="metric-value">{{ stats.completed }}</div>
          <div class="metric-hint">可查看决策结果并导出报告</div>
        </article>
        <article class="metric-card">
          <div class="metric-label">执行中</div>
          <div class="metric-value">{{ stats.running }}</div>
          <div class="metric-hint">任务仍在处理</div>
        </article>
        <article class="metric-card">
          <div class="metric-label">失败</div>
          <div class="metric-value">{{ stats.failed }}</div>
          <div class="metric-hint">需要排查数据或约束条件</div>
        </article>
      </div>
    </section>

    <section class="panel-card filter-panel">
      <div class="section-head">
        <div class="section-title">
          <h3>任务筛选</h3>
          <p>按状态和时间范围查询任务记录。</p>
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
          <p>点击任务进入详情，查看结果报告、执行策略和 Agent 协同日志。</p>
        </div>
      </div>

      <el-table
        v-loading="loading"
        :data="tasks"
        border
        stripe
        @sort-change="handleSortChange"
      >
        <el-table-column prop="taskCode" label="任务编号" min-width="220" show-overflow-tooltip />
        <el-table-column prop="productTitle" label="商品名称" min-width="220" show-overflow-tooltip />
        <el-table-column label="当前售价" width="120">
          <template #default="{ row }">{{ formatCurrency(row.currentPrice) }}</template>
        </el-table-column>
        <el-table-column label="最终建议价" width="120">
          <template #default="{ row }">{{ formatCurrency(row.finalPrice) }}</template>
        </el-table-column>
        <el-table-column prop="executeStrategy" label="执行策略" width="140" show-overflow-tooltip />
        <el-table-column prop="taskStatus" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusTypeMap[row.taskStatus] || 'info'">
              {{ statusMap[row.taskStatus] || row.taskStatus || '-' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="180" sortable="custom">
          <template #default="{ row }">{{ formatDateTime(row.createdAt) }}</template>
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
          <strong>{{ currentTask.taskCode }}</strong>
        </div>
        <div class="drawer-meta-item">
          <span>商品名称</span>
          <strong>{{ currentTask.productTitle || '-' }}</strong>
        </div>
        <div class="drawer-meta-item">
          <span>建议区间</span>
          <strong>{{ formatRange(currentTask.suggestedMinPrice, currentTask.suggestedMaxPrice) }}</strong>
        </div>
        <div class="drawer-meta-item">
          <span>任务状态</span>
          <strong>{{ statusMap[currentTask.taskStatus] || currentTask.taskStatus }}</strong>
        </div>
      </div>

      <el-tabs v-model="activeTab" class="detail-tabs">
        <el-tab-pane label="结果报告" name="comparison">
          <div class="drawer-actions">
            <el-button
              type="primary"
              plain
              :disabled="!currentTask || currentTask.taskStatus !== 'COMPLETED'"
              @click="exportReport"
            >
              导出报告
            </el-button>
          </div>

          <div v-loading="detailLoading" class="report-layout">
            <section class="metric-grid compact-metrics">
              <article class="metric-card">
                <div class="metric-label">建议售价</div>
                <div class="metric-value">{{ formatCurrency(summaryRow?.suggestedPrice) }}</div>
                <div class="metric-hint">结果表中的最终价格</div>
              </article>
              <article class="metric-card">
                <div class="metric-label">预期销量</div>
                <div class="metric-value">{{ summaryRow?.expectedSales || 0 }}</div>
                <div class="metric-hint">按当前策略估算</div>
              </article>
              <article class="metric-card">
                <div class="metric-label">预期利润</div>
                <div class="metric-value">{{ formatCurrency(summaryRow?.expectedProfit) }}</div>
                <div class="metric-hint">基于建议售价测算</div>
              </article>
              <article class="metric-card">
                <div class="metric-label">利润变化</div>
                <div class="metric-value">{{ formatSignedCurrency(summaryRow?.profitChange) }}</div>
                <div class="metric-hint">相对基线利润的变化</div>
              </article>
            </section>

            <section class="panel-card embedded-panel">
              <el-table :data="comparisonData" border stripe>
                <el-table-column prop="productTitle" label="商品名称" min-width="180" show-overflow-tooltip />
                <el-table-column label="原价" width="120">
                  <template #default="{ row }">{{ formatCurrency(row.originalPrice) }}</template>
                </el-table-column>
                <el-table-column label="建议价" width="120">
                  <template #default="{ row }">
                    <span class="price-text">{{ formatCurrency(row.suggestedPrice) }}</span>
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
                    <el-tag :type="Number(row.profitChange || 0) >= 0 ? 'success' : 'danger'">
                      {{ formatSignedCurrency(row.profitChange) }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="passStatus" label="风控结果" width="110" />
                <el-table-column prop="executeStrategy" label="执行策略" width="120" />
                <el-table-column label="应用状态" width="110">
                  <template #default="{ row }">
                    <el-tag :type="row.appliedStatus === '已应用' ? 'success' : 'info'">
                      {{ row.appliedStatus || '未应用' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="resultSummary" label="结果说明" min-width="320" show-overflow-tooltip />
                <el-table-column label="操作" width="120" fixed="right">
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

            <section class="panel-card embedded-panel">
              <div class="section-head">
                <div class="section-title">
                  <h3>价格对比</h3>
                  <p>对比任务原价与最终建议价。</p>
                </div>
              </div>
              <div v-if="comparisonData.length > 0" ref="chartRef" class="comparison-chart"></div>
              <el-empty v-else description="暂无结果数据" />
            </section>
          </div>
        </el-tab-pane>

        <el-tab-pane label="协同日志" name="logs">
          <div class="logs-panel">
            <article v-for="log in orderedLogs" :key="log.id" class="log-card">
              <div class="log-head">
                <div class="log-title">
                  <strong>{{ getLogAgentName(log) }}</strong>
                  <el-tag size="small" :type="isSuccessStatus(log.runStatus) ? 'success' : 'warning'">
                    {{ getRunStatusText(log.runStatus) }}
                  </el-tag>
                </div>
                <span>{{ formatDateTime(log.createdAt) }}</span>
              </div>
              <div class="log-content">
                <section class="log-section">
                  <h4>思考过程</h4>
                  <p>{{ getLogThinking(log) }}</p>
                </section>
                <section class="log-section">
                  <h4>依据</h4>
                  <ul class="info-list">
                    <li v-for="(line, idx) in getLogEvidenceLines(log)" :key="`e-${log.id}-${idx}`">{{ line }}</li>
                  </ul>
                </section>
                <section class="log-section">
                  <h4>建议</h4>
                  <ul class="info-list">
                    <li v-for="(line, idx) in getLogSuggestionLines(log)" :key="`s-${log.id}-${idx}`">{{ line }}</li>
                  </ul>
                </section>
                <section v-if="getLogReason(log)" class="log-section">
                  <h4>为什么给出这个建议</h4>
                  <p>{{ getLogReason(log) }}</p>
                </section>
              </div>
              <div class="log-meta">
                <span>建议价：{{ formatCurrency(log.suggestedPrice) }}</span>
                <span>预估利润：{{ formatCurrency(log.predictedProfit) }}</span>
                <span>置信度：{{ formatPercent(log.confidenceScore) }}</span>
                <span>风险等级：{{ toNaturalChinese(log.riskLevel) }}</span>
                <span>人工复核：{{ log.needManualReview ? '需要' : '否' }}</span>
              </div>
            </article>
            <el-empty v-if="orderedLogs.length === 0" description="暂无协同日志" />
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import {
  applyDecision,
  getTaskComparison,
  getTaskList,
  getTaskLogs,
  getTaskStats,
  type DecisionComparisonItem,
  type DecisionLogItem,
  type PricingAgentCode,
  type DecisionTaskItem,
  type DecisionTaskStats
} from '../api/decision'

const loading = ref(false)
const detailLoading = ref(false)
const drawerVisible = ref(false)
const activeTab = ref('comparison')
const total = ref(0)
const tasks = ref<DecisionTaskItem[]>([])
const comparisonData = ref<DecisionComparisonItem[]>([])
const agentLogs = ref<DecisionLogItem[]>([])
const currentTask = ref<DecisionTaskItem | null>(null)
const dateRange = ref<string[]>([])
const applyingResultIds = ref<number[]>([])
const stats = ref<DecisionTaskStats>({
  total: 0,
  completed: 0,
  running: 0,
  failed: 0
})

const chartRef = ref<HTMLElement | null>(null)
const viewportWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1440)
let chartInstance: echarts.ECharts | null = null

const queryParams = reactive({
  page: 1,
  size: 10,
  status: '',
  startTime: '',
  endTime: '',
  sortOrder: 'desc' as 'asc' | 'desc'
})

const statusMap: Record<string, string> = {
  PENDING: '待执行',
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

const drawerSize = computed(() => (viewportWidth.value < 900 ? '100%' : '78%'))
const summaryRow = computed(() => comparisonData.value[0] || null)
const agentOrderByCode: Record<PricingAgentCode, number> = {
  DATA_ANALYSIS: 1,
  MARKET_INTEL: 2,
  RISK_CONTROL: 3,
  MANAGER_COORDINATOR: 4
}
const agentNameByCode: Record<PricingAgentCode, string> = {
  DATA_ANALYSIS: '数据分析Agent',
  MARKET_INTEL: '市场情报Agent',
  RISK_CONTROL: '风险控制Agent',
  MANAGER_COORDINATOR: '经理协调Agent'
}

const normalizeAgentCode = (code?: string | null): PricingAgentCode | null => {
  const normalized = String(code || '') as PricingAgentCode
  return normalized in agentOrderByCode ? normalized : null
}

const resolveLogOrder = (log: DecisionLogItem) => {
  const displayOrder = Number(log.displayOrder || 0)
  if (displayOrder >= 1 && displayOrder <= 4) return displayOrder
  const runOrder = Number(log.runOrder || 0)
  if (runOrder >= 1 && runOrder <= 4) return runOrder
  const code = normalizeAgentCode(log.agentCode)
  return code ? agentOrderByCode[code] : 99
}

const isCrewAiLog = (log: DecisionLogItem) => {
  const role = String(log.agentName || log.agentCode || log.roleName || '')
  return role.toUpperCase().includes('CREWAI') || role.includes('协作引擎')
}

const orderedLogs = computed(() =>
  [...agentLogs.value]
    .filter((log) => !isCrewAiLog(log))
    .sort((a, b) => {
      const orderDiff = resolveLogOrder(a) - resolveLogOrder(b)
      if (orderDiff !== 0) return orderDiff
      return Number(a.id || 0) - Number(b.id || 0)
    })
)

const getLogAgentName = (log: DecisionLogItem) => {
  if (log.agentName) return log.agentName
  const code = normalizeAgentCode(log.agentCode)
  if (code) return agentNameByCode[code]
  return log.agentCode || log.roleName || 'Agent'
}

const textValueMap: Record<string, string> = {
  MAX_PROFIT: '利润优先',
  CLEARANCE: '清仓促销',
  MARKET_SHARE: '市场份额优先',
  AUTO_EXECUTE: '自动执行',
  MANUAL_REVIEW: '人工审核',
  LOW: '低风险',
  MEDIUM: '中风险',
  HIGH: '高风险',
  SUCCESS: '成功',
  RUNNING: '执行中',
  COMPLETED: '已完成',
  FAILED: '失败',
  PENDING: '待执行'
}

const toNaturalChinese = (value: unknown): string => {
  const text = String(value ?? '').trim()
  if (!text) return '-'
  const upper = text.toUpperCase()
  return textValueMap[upper] || text
}

const isSuccessStatus = (status?: string | null) => {
  const normalized = String(status || '').trim().toUpperCase()
  return normalized === 'SUCCESS' || normalized === '成功'
}

const getRunStatusText = (status?: string | null) => {
  if (!status) return '-'
  return toNaturalChinese(status)
}

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

const formatCurrency = (value?: number | string | null) => `￥${Number(value || 0).toFixed(2)}`
const formatPercent = (value?: number | string | null) => `${(Number(value || 0) * 100).toFixed(0)}%`
const formatSignedCurrency = (value?: number | string | null) => {
  const numeric = Number(value || 0)
  return `${numeric >= 0 ? '+' : '-'}￥${Math.abs(numeric).toFixed(2)}`
}
const formatRange = (min?: number | null, max?: number | null) => `${formatCurrency(min)} - ${formatCurrency(max)}`

const toNumber = (value: unknown): number | null => {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

const formatBoolean = (value: boolean) => (value ? '是' : '否')

const formatPrimitive = (key: string, value: unknown): string => {
  if (value == null) return '-'
  if (typeof value === 'boolean') return formatBoolean(value)

  const numeric = toNumber(value)
  if (numeric != null) {
    const lowered = key.toLowerCase()
    if (lowered.includes('price') || lowered.includes('profit') || lowered.includes('amount')) {
      return formatCurrency(numeric)
    }
    if (lowered.includes('rate')) {
      return `${(numeric * 100).toFixed(2)}%`
    }
    return String(numeric)
  }
  return toNaturalChinese(value)
}

const formatObjectLine = (value: Record<string, unknown>): string => {
  if ('competitorName' in value) {
    const name = String(value.competitorName || '竞品')
    const platform = String(value.sourcePlatform || '')
    const shopType = String(value.shopType || '')
    const header = `${name}${platform ? `（${platform}${shopType ? `/${shopType}` : ''}）` : ''}`

    const parts: string[] = [header]
    if (value.price != null) parts.push(`价格${formatPrimitive('price', value.price)}`)
    if (value.originalPrice != null) parts.push(`原价${formatPrimitive('originalPrice', value.originalPrice)}`)
    if (value.salesVolumeHint != null) parts.push(`销量提示：${toNaturalChinese(value.salesVolumeHint)}`)
    if (value.promotionTag != null) parts.push(`促销：${toNaturalChinese(value.promotionTag)}`)
    return parts.join('，')
  }

  const keyMap: Record<string, string> = {
    competitorName: '竞品',
    sourcePlatform: '平台',
    shopType: '店铺类型',
    promotionTag: '促销信息',
    salesVolumeHint: '销量提示',
    marketScore: '市场评分',
    riskLevel: '风险等级'
  }

  return Object.entries(value)
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => `${keyMap[k] || k}：${formatPrimitive(k, v)}`)
    .join('，')
}

const formatEvidenceValue = (label: unknown, value: unknown): string => {
  if (value == null) return '-'
  if (Array.isArray(value)) {
    if (value.length === 0) return '暂无数据'
    const lines = value.map((item) => {
      if (item && typeof item === 'object') {
        return formatObjectLine(item as Record<string, unknown>)
      }
      return toNaturalChinese(item)
    })
    const joined = lines.join('；')
    if (String(label || '').includes('竞品摘要')) {
      return `共 ${value.length} 条：${joined}`
    }
    return joined
  }
  if (value && typeof value === 'object') {
    return formatObjectLine(value as Record<string, unknown>)
  }
  return toNaturalChinese(value)
}

const getSuggestionLines = (code: PricingAgentCode | null, suggestion?: Record<string, unknown>) => {
  if (!suggestion || Object.keys(suggestion).length === 0) return ['暂无建议内容']

  const lines: string[] = []
  const priceRange = suggestion.priceRange
  if (priceRange && typeof priceRange === 'object') {
    const range = priceRange as Record<string, unknown>
    const min = toNumber(range.min)
    const max = toNumber(range.max)
    if (min != null && max != null) {
      lines.push(`建议价格区间：${formatCurrency(min)} ~ ${formatCurrency(max)}`)
    }
  }

  if (code === 'DATA_ANALYSIS') {
    const recommendedPrice = toNumber(suggestion.recommendedPrice)
    if (recommendedPrice != null) lines.push(`建议定价：${formatCurrency(recommendedPrice)}`)
    const expectedSales = toNumber(suggestion.expectedSales)
    if (expectedSales != null) lines.push(`预期销量：${expectedSales}`)
    const expectedProfit = toNumber(suggestion.expectedProfit)
    if (expectedProfit != null) lines.push(`预期利润：${formatCurrency(expectedProfit)}`)
    const expectedProfitRate = toNumber(suggestion.expectedProfitRate)
    if (expectedProfitRate != null) lines.push(`预期利润率：${(expectedProfitRate * 100).toFixed(2)}%`)
  }

  if (code === 'MARKET_INTEL') {
    const recommendedPrice = toNumber(suggestion.recommendedPrice)
    if (recommendedPrice != null) lines.push(`建议定价：${formatCurrency(recommendedPrice)}`)
    const marketScore = toNumber(suggestion.marketScore)
    if (marketScore != null) lines.push(`市场接受度评分：${marketScore.toFixed(1)}`)
  }

  if (code === 'RISK_CONTROL') {
    const recommendedPrice = toNumber(suggestion.recommendedPrice)
    if (recommendedPrice != null) lines.push(`风控建议价：${formatCurrency(recommendedPrice)}`)
    if (typeof suggestion.pass === 'boolean') lines.push(`是否自动通过：${formatBoolean(suggestion.pass)}`)
    if (suggestion.riskLevel != null) lines.push(`风险等级：${toNaturalChinese(suggestion.riskLevel)}`)
    if (suggestion.action != null) {
      lines.push(`建议动作：${toNaturalChinese(suggestion.action)}`)
    }
  }

  if (code === 'MANAGER_COORDINATOR') {
    const finalPrice = toNumber(suggestion.finalPrice)
    if (finalPrice != null) lines.push(`最终建议价：${formatCurrency(finalPrice)}`)
    const expectedSales = toNumber(suggestion.expectedSales)
    if (expectedSales != null) lines.push(`预期销量：${expectedSales}`)
    const expectedProfit = toNumber(suggestion.expectedProfit)
    if (expectedProfit != null) lines.push(`预期利润：${formatCurrency(expectedProfit)}`)
    if (suggestion.strategy != null) lines.push(`执行策略：${toNaturalChinese(suggestion.strategy)}`)
  }

  if (suggestion.summary != null) {
    lines.push(`建议说明：${toNaturalChinese(suggestion.summary)}`)
  }

  if (lines.length > 0) return lines

  return Object.entries(suggestion)
    .filter(([, value]) => value !== null && value !== undefined)
    .map(([key, value]) => `${key}：${formatPrimitive(key, value)}`)
}

const getLogThinking = (log: DecisionLogItem) => {
  return String(log.thinking || log.outputSummary || log.thoughtContent || '-')
}

const getLogEvidenceLines = (log: DecisionLogItem) => {
  const evidence = Array.isArray(log.evidence) ? log.evidence : []
  if (evidence.length === 0) return ['暂无依据内容']
  return evidence.map((item, idx) => {
    const label = item?.label ?? `依据${idx + 1}`
    return `${String(label)}：${formatEvidenceValue(label, item?.value)}`
  })
}

const getLogSuggestionLines = (log: DecisionLogItem) => {
  const suggestion = log.suggestion && typeof log.suggestion === 'object' ? log.suggestion : {}
  return getSuggestionLines(normalizeAgentCode(log.agentCode), suggestion)
}

const getLogReason = (log: DecisionLogItem) => {
  return String(log.reasonWhy || '').trim()
}

const handleSearch = () => {
  queryParams.page = 1
  fetchTasks()
}

const resetFilters = () => {
  queryParams.page = 1
  queryParams.status = ''
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
    return
  }
  queryParams.startTime = ''
  queryParams.endTime = ''
}

const handleSortChange = ({ prop, order }: { prop: string; order: string | null }) => {
  if (prop !== 'createdAt') return
  queryParams.sortOrder = order === 'ascending' ? 'asc' : 'desc'
  fetchTasks()
}

const fetchTasks = async () => {
  loading.value = true
  try {
    const res: any = await getTaskList({
      page: queryParams.page,
      size: queryParams.size,
      status: queryParams.status || undefined,
      startTime: queryParams.startTime || undefined,
      endTime: queryParams.endTime || undefined,
      sortOrder: queryParams.sortOrder
    })
    if (res.code !== 200) {
      ElMessage.error(res.message || '获取任务列表失败')
      return
    }
    tasks.value = res.data?.records || []
    total.value = Number(res.data?.total || 0)
    await fetchStats()
  } catch {
    ElMessage.error('获取任务列表失败')
  } finally {
    loading.value = false
  }
}

const fetchStats = async () => {
  try {
    const res: any = await getTaskStats({
      startTime: queryParams.startTime || undefined,
      endTime: queryParams.endTime || undefined
    })
    if (res.code === 200) {
      stats.value = {
        total: Number(res.data?.total || 0),
        completed: Number(res.data?.completed || 0),
        running: Number(res.data?.running || 0),
        failed: Number(res.data?.failed || 0)
      }
      return
    }
  } catch {
  }

  stats.value = {
    total: total.value,
    completed: tasks.value.filter((item) => item.taskStatus === 'COMPLETED').length,
    running: tasks.value.filter((item) => item.taskStatus === 'RUNNING').length,
    failed: tasks.value.filter((item) => item.taskStatus === 'FAILED').length
  }
}

const viewDetails = async (row: DecisionTaskItem) => {
  currentTask.value = row
  drawerVisible.value = true
  activeTab.value = 'comparison'
  await Promise.all([fetchComparison(), fetchLogs()])
}

const fetchComparison = async () => {
  if (!currentTask.value) return
  detailLoading.value = true
  try {
    const res: any = await getTaskComparison(currentTask.value.id)
    if (res.code !== 200) {
      ElMessage.error(res.message || '获取结果报告失败')
      return
    }
    comparisonData.value = res.data || []
    await nextTick()
    renderChart()
  } catch {
    ElMessage.error('获取结果报告失败')
  } finally {
    detailLoading.value = false
  }
}

const fetchLogs = async () => {
  if (!currentTask.value) return
  try {
    const res: any = await getTaskLogs(currentTask.value.id)
    if (res.code === 200) {
      agentLogs.value = res.data || []
      return
    }
  } catch {
  }
  agentLogs.value = []
}

const applyPrice = async (row: DecisionComparisonItem) => {
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
    if (res.code !== 200) {
      ElMessage.error(res.message || '应用失败')
      return
    }

    ElMessage.success('价格建议已应用')
    await fetchComparison()
    await fetchTasks()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('应用失败')
    }
  } finally {
    applyingResultIds.value = applyingResultIds.value.filter((id) => id !== resultId)
  }
}

const exportReport = () => {
  if (!currentTask.value) return
  window.open(`/api/decision/export/${currentTask.value.id}`, '_blank')
}

const renderChart = () => {
  if (!chartRef.value) return

  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }

  if (comparisonData.value.length === 0) return

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
        width: 140,
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

watch(drawerVisible, (visible) => {
  if (visible) return
  currentTask.value = null
  comparisonData.value = []
  agentLogs.value = []
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

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
  grid-template-columns: repeat(4, minmax(0, 1fr));
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

.filter-panel {
  padding: 12px 14px;
}

.filter-panel .section-head {
  margin-bottom: 8px;
}

.filter-grid {
  display: grid;
  grid-template-columns: 180px minmax(320px, 1fr) auto;
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

.log-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.log-content {
  display: grid;
  gap: 10px;
}

.log-section {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--border-soft);
  background: var(--panel-muted);
}

.log-section h4 {
  margin: 0 0 8px;
  font-size: 13px;
}

.log-section p {
  margin: 0;
  color: var(--text-primary);
  line-height: 1.7;
}

.info-list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 6px;
  color: var(--text-primary);
  line-height: 1.7;
}

.log-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 10px;
  color: var(--text-3);
  font-size: 12px;
}

.price-text {
  font-weight: 700;
  color: var(--accent);
}

@media (max-width: 1200px) {
  .compact-metrics,
  .drawer-meta {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filter-grid .toolbar-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 768px) {
  .compact-metrics,
  .drawer-meta,
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .drawer-actions {
    justify-content: stretch;
  }

  .drawer-actions :deep(.el-button) {
    width: 100%;
  }

  .log-head {
    flex-direction: column;
  }
}
</style>

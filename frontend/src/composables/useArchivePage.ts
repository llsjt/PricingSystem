import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  applyDecision,
  getPricingTaskDetail,
  getTaskComparison,
  getTaskList,
  getTaskLogs,
  getTaskStats,
  type DecisionComparisonItem,
  type DecisionLogItem,
  type DecisionTaskItem,
  type DecisionTaskStats,
  type PricingTaskDetail,
  type PricingAgentCode
} from '../api/decision'
import { useEChart } from './useEChart'
import { useViewport } from './useViewport'
import {
  AGENT_ORDER_BY_CODE,
  createApplyDecisionConfirmMessage,
  formatPriceRange,
  getLogAgentName,
  getLogEvidenceLines,
  getLogReason,
  getLogSuggestionLines,
  getLogThinking,
  getRunStatusText,
  isSuccessStatus,
  normalizeAgentCode,
  toNaturalChinese
} from '../utils/decisionDisplay'
import { resolveRequestErrorMessage } from '../utils/error'
import { formatCurrency, formatDateTime, formatPercent, formatSignedCurrency } from '../utils/formatters'

const STATUS_MAP: Record<string, string> = {
  QUEUED: '待执行',
  RETRYING: '重试中',
  MANUAL_REVIEW: '人工审核',
  CANCELLED: '已取消',
  PENDING: '待执行',
  RUNNING: '执行中',
  COMPLETED: '已完成',
  FAILED: '失败'
}

const STATUS_TYPE_MAP: Record<string, 'info' | 'warning' | 'success' | 'danger'> = {
  QUEUED: 'info',
  RETRYING: 'warning',
  MANUAL_REVIEW: 'warning',
  CANCELLED: 'info',
  PENDING: 'info',
  RUNNING: 'warning',
  COMPLETED: 'success',
  FAILED: 'danger'
}

const STATUS_OPTIONS = [
  { label: '待执行', value: 'QUEUED' },
  { label: '执行中', value: 'RUNNING' },
  { label: '重试中', value: 'RETRYING' },
  { label: '人工审核', value: 'MANUAL_REVIEW' },
  { label: '已取消', value: 'CANCELLED' },
  { label: '已完成', value: 'COMPLETED' },
  { label: '失败', value: 'FAILED' }
]

const buildComparisonChartOption = (rows: DecisionComparisonItem[]) => ({
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
    data: rows.map((item) => item.productTitle),
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
      data: rows.map((item) => Number(item.originalPrice || 0))
    },
    {
      name: '建议价',
      type: 'bar',
      barMaxWidth: 16,
      data: rows.map((item) => Number(item.suggestedPrice || 0))
    }
  ]
})

export const useArchivePage = () => {
  const route = useRoute()
  const { width } = useViewport()
  const { chartRef, disposeChart, resizeChart, setChartOption } = useEChart()

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
  const openedRouteTaskId = ref<number | null>(null)
  const stats = ref<DecisionTaskStats>({
    total: 0,
    completed: 0,
    running: 0,
    failed: 0
  })

  const queryParams = reactive({
    page: 1,
    size: 10,
    status: '',
    startTime: '',
    endTime: '',
    sortOrder: 'desc' as 'asc' | 'desc'
  })

  const drawerSize = computed(() => (width.value < 900 ? '100%' : '78%'))
  const summaryRow = computed(() => comparisonData.value[0] || null)

  const resolveLogOrder = (log: DecisionLogItem) => {
    const displayOrder = Number(log.displayOrder || 0)
    if (displayOrder >= 1 && displayOrder <= 4) return displayOrder
    const runOrder = Number(log.runOrder || 0)
    if (runOrder >= 1 && runOrder <= 4) return runOrder
    const code = normalizeAgentCode(log.agentCode)
    return code ? AGENT_ORDER_BY_CODE[code] : 99
  }

  const isCrewAiLog = (log: DecisionLogItem) => {
    const role = String(log.agentName || log.agentCode || log.roleName || '')
    return role.toUpperCase().includes('CREWAI') || role.includes('协作引擎')
  }

  const orderedLogs = computed(() =>
    [...agentLogs.value]
      .filter((log) => !isCrewAiLog(log))
      .filter((log) => log.stage !== 'running')
      .sort((left, right) => {
        const orderDiff = resolveLogOrder(left) - resolveLogOrder(right)
        if (orderDiff !== 0) return orderDiff
        return Number(left.id || 0) - Number(right.id || 0)
      })
  )

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
      completed: tasks.value.filter((item) => ['COMPLETED', 'MANUAL_REVIEW'].includes(item.taskStatus)).length,
      running: tasks.value.filter((item) => ['QUEUED', 'RUNNING', 'RETRYING'].includes(item.taskStatus)).length,
      failed: tasks.value.filter((item) => ['FAILED', 'CANCELLED'].includes(item.taskStatus)).length
    }
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
    } catch (error) {
      ElMessage.error(await resolveRequestErrorMessage(error, '获取任务列表失败'))
    } finally {
      loading.value = false
    }
  }

  const renderChart = () => {
    if (comparisonData.value.length === 0) {
      disposeChart()
      return
    }

    setChartOption(buildComparisonChartOption(comparisonData.value))
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
    } catch (error) {
      ElMessage.error(await resolveRequestErrorMessage(error, '获取结果报告失败'))
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

  const viewDetails = async (row: DecisionTaskItem) => {
    currentTask.value = row
    drawerVisible.value = true
    activeTab.value = 'comparison'
    await Promise.all([fetchComparison(), fetchLogs()])
  }

  const routeTaskId = () => {
    const raw = Array.isArray(route.query.taskId) ? route.query.taskId[0] : route.query.taskId
    const id = Number(raw)
    return Number.isInteger(id) && id > 0 ? id : null
  }

  const toDecisionTaskItem = (detail: PricingTaskDetail): DecisionTaskItem => ({
    id: Number(detail.taskId),
    taskCode: `TASK-${detail.taskId}`,
    productId: Number(detail.productId || 0),
    productTitle: String(detail.productTitle || '-'),
    currentPrice: Number(detail.currentPrice || 0),
    suggestedMinPrice: detail.suggestedMinPrice,
    suggestedMaxPrice: detail.suggestedMaxPrice,
    finalPrice: detail.finalPrice,
    taskStatus: String(detail.taskStatus || ''),
    executeStrategy: detail.strategy,
    createdAt: String(detail.createdAt || '')
  })

  const loadTaskItemById = async (taskId: number) => {
    const existing = tasks.value.find((item) => Number(item.id) === taskId)
    if (existing) return existing
    const res: any = await getPricingTaskDetail(taskId)
    if (res.code !== 200 || !res.data) {
      ElMessage.error(res.message || '未找到对应的决策档案')
      return null
    }
    return toDecisionTaskItem(res.data)
  }

  const openTaskFromRoute = async () => {
    const taskId = routeTaskId()
    if (!taskId) return
    if (drawerVisible.value && openedRouteTaskId.value === taskId) return
    const task = await loadTaskItemById(taskId)
    if (!task) return
    openedRouteTaskId.value = taskId
    await viewDetails(task)
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

  const applyPrice = async (row: DecisionComparisonItem) => {
    const resultId = Number(row.resultId || 0)
    if (!resultId) {
      ElMessage.error('未找到可应用的结果记录')
      return
    }

    try {
      await ElMessageBox.confirm(createApplyDecisionConfirmMessage(row.productTitle, row.suggestedPrice), '应用价格建议', {
        type: 'warning',
        confirmButtonText: '确认应用',
        cancelButtonText: '取消'
      })

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
        ElMessage.error(await resolveRequestErrorMessage(error, '应用失败'))
      }
    } finally {
      applyingResultIds.value = applyingResultIds.value.filter((id) => id !== resultId)
    }
  }

  const exportReport = () => {
    if (!currentTask.value) return
    window.open(`/api/decision/export/${currentTask.value.id}`, '_blank')
  }

  watch(drawerVisible, (visible) => {
    if (visible) {
      return
    }

    currentTask.value = null
    comparisonData.value = []
    agentLogs.value = []
    disposeChart()
  })

  watch(width, () => {
    resizeChart()
  })

  onMounted(async () => {
    await fetchTasks()
    await openTaskFromRoute()
  })

  watch(() => route.query.taskId, () => {
    void openTaskFromRoute()
  })

  return {
    activeTab,
    agentLogs,
    applyingResultIds,
    chartRef,
    comparisonData,
    currentTask,
    dateRange,
    detailLoading,
    drawerSize,
    drawerVisible,
    exportReport,
    fetchTasks,
    formatCurrency,
    formatDateTime,
    formatPercent,
    formatRange: formatPriceRange,
    formatSignedCurrency,
    getLogAgentName,
    getLogEvidenceLines,
    getLogReason,
    getLogSuggestionLines,
    getLogThinking,
    getRunStatusText,
    handleDateChange,
    handleSearch,
    handleSortChange,
    isSuccessStatus,
    loading,
    orderedLogs,
    queryParams,
    resetFilters,
    stats,
    statusMap: STATUS_MAP,
    statusOptions: STATUS_OPTIONS,
    statusTypeMap: STATUS_TYPE_MAP,
    summaryRow,
    tasks,
    toNaturalChinese,
    total,
    viewDetails,
    applyPrice
  }
}

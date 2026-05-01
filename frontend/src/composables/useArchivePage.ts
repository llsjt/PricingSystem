/**
 * 决策档案页组合式逻辑，集中管理列表查询、详情抽屉、图表和结果应用。
 */

import { computed, nextTick, onActivated, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  applyDecision,
  batchDeleteDecisionTasks,
  deleteDecisionTask,
  getPricingTaskDetail,
  getTaskComparison,
  getTaskList,
  getTaskLogs,
  getTaskStats,
  retryPricingTask,
  type DecisionComparisonItem,
  type DecisionLogItem,
  type DecisionTaskItem,
  type DecisionTaskStats,
  type PricingTaskDetail,
  type PricingAgentCode
} from '../api/decision'
import { getRecentPricingBatches, type PricingBatchDetail } from '../api/pricingBatch'
import { useEChart } from './useEChart'
import { useViewport } from './useViewport'
import {
  AGENT_ORDER_BY_CODE,
  createApplyDecisionConfirmMessage,
  formatPriceRange,
  getLogAgentCode,
  getLogAgentName,
  getLogEvidenceLines,
  getManagerArbitrationBlock,
  getLogReason,
  getLogSuggestionHighlightLabel,
  getLogSuggestionHighlightPrice,
  getLogSuggestionLines,
  getLogThinking,
  getRunStatusType,
  getRunStatusText,
  isSuccessStatus,
  normalizeAgentCode,
  toNaturalChinese
} from '../utils/decisionDisplay'
import { normalizeAgentOpinion, type NormalizedAgentOpinion } from '../utils/agentOpinion'
import { resolveRequestErrorMessage } from '../utils/error'
import { getFailureSummary } from '../utils/failureSummary'
import { filterLatestAgentRunRound } from '../utils/agentTimeline'
import { formatCurrency, formatDateTime, formatPercent, formatSignedCurrency } from '../utils/formatters'
import { PRICING_GOAL_LABELS, PRICING_STATUS_LABELS, PRICING_STATUS_TAG_TYPES } from '../utils/pricingTaskOptions'

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

const ACTIVE_TASK_STATUSES = new Set(['PENDING', 'QUEUED', 'RUNNING', 'RETRYING'])

const ARCHIVE_AGENT_MARK: Record<PricingAgentCode, string> = {
  DATA_ANALYSIS: '数',
  MARKET_INTEL: '市',
  RISK_CONTROL: '控',
  MANAGER_COORDINATOR: '裁'
}

const ARCHIVE_AGENT_ROLE_LABEL: Record<PricingAgentCode, string> = {
  DATA_ANALYSIS: '数据测算',
  MARKET_INTEL: '市场校准',
  RISK_CONTROL: '风险约束',
  MANAGER_COORDINATOR: '分歧裁决'
}

const trimText = (value: unknown) => {
  const text = String(value ?? '').trim()
  return text || null
}

const dedupeLines = (lines: string[]) => [...new Set(lines.filter((line) => Boolean(trimText(line))))]

const formatConfidenceText = (value: number | null) => {
  if (value == null) return null
  const percent = value > 1 ? value : value * 100
  const digits = percent >= 10 ? 0 : 1
  return `${percent.toFixed(digits)}%`
}

const getArchiveHighlightLabel = (code: PricingAgentCode | null) => {
  if (code === 'MANAGER_COORDINATOR') return '最终建议价'
  if (code === 'RISK_CONTROL') return '风控建议价'
  return '建议定价'
}

const buildOpinionSuggestionLines = (code: PricingAgentCode | null, opinion: NormalizedAgentOpinion) => {
  const lines: string[] = []
  if (opinion.recommendedPrice != null) {
    lines.push(`${getArchiveHighlightLabel(code)}：${formatCurrency(opinion.recommendedPrice)}`)
  }
  if (opinion.minPrice != null && opinion.maxPrice != null) {
    lines.push(`建议区间：${formatCurrency(opinion.minPrice)} ~ ${formatCurrency(opinion.maxPrice)}`)
  }
  if (opinion.safeFloorPrice != null) {
    lines.push(`安全底价：${formatCurrency(opinion.safeFloorPrice)}`)
  }
  if (opinion.expectedSales != null) {
    lines.push(`预期销量：${opinion.expectedSales}`)
  }
  if (opinion.expectedProfit != null) {
    lines.push(`预期利润：${formatCurrency(opinion.expectedProfit)}`)
  }
  if (opinion.confidence != null) {
    lines.push(`置信度：${formatConfidenceText(opinion.confidence)}`)
  }
  if (opinion.riskLevel) {
    lines.push(`风险等级：${toNaturalChinese(opinion.riskLevel)}`)
  }
  if (opinion.summary) {
    lines.push(`意见摘要：${opinion.summary}`)
  }
  return dedupeLines(lines)
}

const buildArchiveArbitrationBlock = (opinion: NormalizedAgentOpinion | null, log: DecisionLogItem) => {
  if (!opinion?.arbitration) {
    return getManagerArbitrationBlock(log)
  }

  const arbitration = opinion.arbitration
  const disagreementLines: string[] = []
  const decisionLines: string[] = []
  if (arbitration.consensusScoreText) disagreementLines.push(`共识度：${arbitration.consensusScoreText}`)
  if (arbitration.disagreementSummary) disagreementLines.push(`分歧摘要：${arbitration.disagreementSummary}`)
  arbitration.disagreementPoints.forEach((line, index) => {
    disagreementLines.push(`分歧点 ${index + 1}：${line}`)
  })
  if (arbitration.decisionSummary) decisionLines.push(`裁决结论：${arbitration.decisionSummary}`)
  if (arbitration.decisionReason) decisionLines.push(`裁决理由：${arbitration.decisionReason}`)
  arbitration.acceptedOpinions.forEach((line, index) => {
    decisionLines.push(`采纳意见 ${index + 1}：${line}`)
  })
  arbitration.rejectedOpinions.forEach((line, index) => {
    decisionLines.push(`未采纳意见 ${index + 1}：${line}`)
  })
  if (arbitration.selectedAgentLabel) decisionLines.push(`采纳方案：${arbitration.selectedAgentLabel}`)
  if (arbitration.selectedPriceText) decisionLines.push(`采纳价格：${arbitration.selectedPriceText}`)
  if (arbitration.selectedStrategy) decisionLines.push(`采纳策略：${arbitration.selectedStrategy}`)

  return {
    consensusScoreText: arbitration.consensusScoreText,
    consensusScorePercent: arbitration.consensusScorePercent,
    disagreementSummary: arbitration.disagreementSummary,
    disagreementPoints: arbitration.disagreementPoints,
    decisionSummary: arbitration.decisionSummary,
    decisionReason: arbitration.decisionReason,
    acceptedOpinions: arbitration.acceptedOpinions,
    rejectedOpinions: arbitration.rejectedOpinions,
    selectedAgent: arbitration.selectedAgentLabel,
    selectedPrice: arbitration.selectedPriceText,
    selectedStrategy: arbitration.selectedStrategy,
    disagreementLines,
    decisionLines
  }
}

const getEvidencePreview = (lines: string[], summary: string | null, reason: string | null) => {
  const preferred = trimText(summary) || trimText(lines[0]) || trimText(reason)
  return preferred || '-'
}

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
  const router = useRouter()
  const { width } = useViewport()
  const { chartRef, disposeChart, resizeChart, setChartOption } = useEChart()

  const loading = ref(false)
  const batchLoading = ref(false)
  const detailLoading = ref(false)
  const drawerVisible = ref(false)
  const activeTab = ref('comparison')
  const total = ref(0)
  const recentBatchTotal = ref(0)
  const tasks = ref<DecisionTaskItem[]>([])
  const recentBatches = ref<PricingBatchDetail[]>([])
  const comparisonData = ref<DecisionComparisonItem[]>([])
  const agentLogs = ref<DecisionLogItem[]>([])
  const currentTask = ref<DecisionTaskItem | null>(null)
  const dateRange = ref<string[]>([])
  const applyingResultIds = ref<number[]>([])
  const deletingTaskIds = ref<number[]>([])
  const retryingTaskIds = ref<number[]>([])
  const selectedTaskIds = ref<number[]>([])
  const taskTableRef = ref<any>(null)
  const openedRouteTaskId = ref<number | null>(null)
  let hasSkippedInitialActivation = false
  let syncingTaskSelection = false
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
  const batchQueryParams = reactive({
    page: 1,
    size: 5
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

  const isFailedLog = (log: DecisionLogItem) => String(log.stage || '').trim().toLowerCase() === 'failed'
    || String(log.runStatus || '').trim().toLowerCase() === 'failed'

  const getLogFailureSummary = (log: DecisionLogItem) => getFailureSummary(log, '任务执行失败')

  const orderedLogCards = computed(() =>
    orderedLogs.value.map((log) => {
      const agentCode = getLogAgentCode(log)
      const opinion = normalizeAgentOpinion(log)
      const evidenceLines = opinion?.evidenceLines.length ? opinion.evidenceLines : getLogEvidenceLines(log)
      const suggestionLines = opinion ? buildOpinionSuggestionLines(agentCode, opinion) : []
      const suggestionHighlightPrice = opinion?.arbitration?.selectedPrice ?? opinion?.recommendedPrice ?? getLogSuggestionHighlightPrice(log)
      return {
        log,
        opinion,
        agentCode,
        agentMark: agentCode ? ARCHIVE_AGENT_MARK[agentCode] : '智',
        roleLabel: agentCode ? ARCHIVE_AGENT_ROLE_LABEL[agentCode] : '协同记录',
        agentName: getLogAgentName(log),
        runStatusType: getRunStatusType(log.runStatus),
        runStatusText: getRunStatusText(log.runStatus),
        failureSummary: getLogFailureSummary(log),
        thinking: getLogThinking(log),
        evidenceLines,
        suggestionHighlightLabel: getArchiveHighlightLabel(agentCode),
        suggestionHighlightPrice,
        suggestionLines: suggestionLines.length ? suggestionLines : getLogSuggestionLines(log),
        reason: getLogReason(log),
        arbitration: buildArchiveArbitrationBlock(opinion, log)
      }
    })
  )

  const archiveEvidenceBoard = computed(() => {
    const cards = orderedLogCards.value
    if (!cards.length) return null

    const matrixRows = cards.map((card) => {
      const evidenceCount = card.evidenceLines.filter((line) => trimText(line) && line !== '暂无依据内容').length
      const confidenceText = formatConfidenceText(card.opinion?.confidence ?? null)
      const riskText = trimText(card.opinion?.riskLevel ? toNaturalChinese(card.opinion.riskLevel) : card.log.riskLevel ? toNaturalChinese(card.log.riskLevel) : '')
      const confidenceSummary = [confidenceText ? `置信 ${confidenceText}` : null, riskText ? `风险 ${riskText}` : null]
        .filter((item): item is string => Boolean(item))
        .join(' / ') || card.runStatusText

      return {
        key: `${card.agentCode || 'archive'}-${card.log.id}`,
        agentName: card.agentName,
        roleLabel: card.roleLabel,
        agentMark: card.agentMark,
        priceText: card.suggestionHighlightPrice != null ? formatCurrency(card.suggestionHighlightPrice) : '-',
        confidenceText: confidenceSummary,
        evidenceCount,
        evidenceText: getEvidencePreview(card.evidenceLines, card.opinion?.summary || null, card.reason || null),
        stateText: card.arbitration?.decisionSummary ? '已裁决' : isFailedLog(card.log) ? '执行失败' : card.runStatusText,
        stateType: card.arbitration?.decisionSummary ? 'success' : card.runStatusType
      }
    })

    const latestCard = [...cards].reverse().find((card) => !isFailedLog(card.log)) || cards[0]
    const managerCard = cards.find((card) => card.agentCode === 'MANAGER_COORDINATOR' && !isFailedLog(card.log)) || latestCard
    const totalEvidenceCount = matrixRows.reduce((sum, row) => sum + row.evidenceCount, 0)
    const failedCount = cards.filter((card) => isFailedLog(card.log)).length
    const overviewItems = [
      {
        label: '最终采纳价',
        value: managerCard?.arbitration?.selectedPrice
          || (managerCard?.suggestionHighlightPrice != null ? formatCurrency(managerCard.suggestionHighlightPrice) : '-')
      },
      {
        label: '主导席位',
        value: managerCard?.arbitration?.selectedAgent || managerCard?.agentName || '-'
      },
      {
        label: '证据条目',
        value: `${totalEvidenceCount} 条`
      },
      {
        label: '异常席位',
        value: `${failedCount} 个`
      }
    ]

    if (managerCard?.arbitration?.consensusScoreText) {
      overviewItems.splice(2, 0, {
        label: '共识度',
        value: managerCard.arbitration.consensusScoreText
      })
    }

    return {
      overviewItems,
      decisionSummary: managerCard?.arbitration?.decisionSummary || managerCard?.opinion?.summary || null,
      decisionReason: managerCard?.arbitration?.decisionReason || managerCard?.reason || null,
      selectedStrategy: managerCard?.arbitration?.selectedStrategy || null,
      matrixRows
    }
  })

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
      await syncTaskTableSelection()
      await fetchStats()
    } catch (error) {
      ElMessage.error(await resolveRequestErrorMessage(error, '获取任务列表失败'))
    } finally {
      loading.value = false
    }
  }

  const normalizeTaskStatus = (status?: string | null) => String(status || '').trim().toUpperCase()

  const canDeleteTask = (row: DecisionTaskItem) => !ACTIVE_TASK_STATUSES.has(normalizeTaskStatus(row.taskStatus))

  const isTaskDeleting = (taskId: number) => deletingTaskIds.value.includes(Number(taskId))

  const canRetryTask = (row?: Pick<DecisionTaskItem, 'taskStatus'> | null) => normalizeTaskStatus(row?.taskStatus) === 'FAILED'

  const isTaskRetrying = (taskId: number) => retryingTaskIds.value.includes(Number(taskId))

  const getTaskId = (row: Pick<DecisionTaskItem, 'id'>) => {
    const id = Number(row.id)
    return Number.isFinite(id) && id > 0 ? id : null
  }

  const syncTaskTableSelection = async () => {
    syncingTaskSelection = true
    try {
      await nextTick()
      const table = taskTableRef.value
      if (!table) return

      const selectedSet = new Set(selectedTaskIds.value)
      table.clearSelection()
      tasks.value.forEach((row) => {
        const id = getTaskId(row)
        if (id != null && selectedSet.has(id) && canDeleteTask(row)) {
          table.toggleRowSelection(row, true)
        }
      })
      await nextTick()
    } finally {
      syncingTaskSelection = false
    }
  }

  const handleTaskSelectionChange = (selection: DecisionTaskItem[]) => {
    if (syncingTaskSelection) return

    const selectedSet = new Set(selectedTaskIds.value)
    const currentPageIds = tasks.value.map(getTaskId).filter((id): id is number => id != null)

    currentPageIds.forEach((id) => selectedSet.delete(id))
    selection.forEach((item) => {
      const id = getTaskId(item)
      if (id != null && canDeleteTask(item)) {
        selectedSet.add(id)
      }
    })

    selectedTaskIds.value = Array.from(selectedSet)
  }

  const clearTaskSelection = () => {
    selectedTaskIds.value = []
    taskTableRef.value?.clearSelection?.()
  }

  const normalizePageAfterDelete = (deletedCount: number) => {
    const remaining = Math.max(total.value - deletedCount, 0)
    const maxPage = Math.max(Math.ceil(remaining / queryParams.size), 1)
    if (queryParams.page > maxPage) {
      queryParams.page = maxPage
    }
  }

  const closeDrawerIfCurrentTaskDeleted = (ids: number[]) => {
    if (!currentTask.value || !ids.includes(Number(currentTask.value.id))) return
    drawerVisible.value = false
  }

  const markTasksDeleting = (ids: number[]) => {
    deletingTaskIds.value = Array.from(new Set([...deletingTaskIds.value, ...ids]))
  }

  const unmarkTasksDeleting = (ids: number[]) => {
    const deletedSet = new Set(ids)
    deletingTaskIds.value = deletingTaskIds.value.filter((id) => !deletedSet.has(id))
  }

  const confirmDeleteTasks = async (count: number) => {
    await ElMessageBox.confirm(
      `确定删除已选择的 ${count} 个决策档案吗？相关结果报告与协同日志将一并删除，此操作不可恢复。`,
      '删除决策档案',
      {
        type: 'warning',
        confirmButtonText: '确认删除',
        cancelButtonText: '取消'
      }
    )
  }

  const handleDeleteTask = async (row: DecisionTaskItem) => {
    if (!canDeleteTask(row)) {
      ElMessage.warning('执行中的决策任务不能删除，请先取消或等待结束')
      return
    }

    const taskId = Number(row.id)
    if (!taskId) return

    try {
      await confirmDeleteTasks(1)
      markTasksDeleting([taskId])
      const res: any = await deleteDecisionTask(taskId)
      if (res.code !== 200) {
        ElMessage.error(res.message || '删除失败')
        return
      }

      ElMessage.success('决策档案已删除')
      selectedTaskIds.value = selectedTaskIds.value.filter((id) => id !== taskId)
      closeDrawerIfCurrentTaskDeleted([taskId])
      normalizePageAfterDelete(1)
      await fetchTasks()
    } catch (error: any) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error(await resolveRequestErrorMessage(error, '删除失败'))
      }
    } finally {
      unmarkTasksDeleting([taskId])
    }
  }

  const handleRetryTask = async (row: DecisionTaskItem) => {
    if (!canRetryTask(row)) {
      ElMessage.warning('只有失败的决策任务可以重试')
      return
    }

    const taskId = Number(row.id)
    if (!taskId) return

    try {
      await ElMessageBox.confirm('确认重新执行该决策任务吗？', '重试决策任务', {
        type: 'warning',
        confirmButtonText: '确认重试',
        cancelButtonText: '取消'
      })

      retryingTaskIds.value = Array.from(new Set([...retryingTaskIds.value, taskId]))
      const res: any = await retryPricingTask(taskId)
      if (res.code !== 200) {
        ElMessage.error(res.message || '重试失败')
        return
      }

      ElMessage.success('任务已重新提交')
      if (currentTask.value && Number(currentTask.value.id) === taskId) {
        currentTask.value = { ...currentTask.value, taskStatus: 'RETRYING' }
        comparisonData.value = []
        agentLogs.value = []
        disposeChart()
      }
      await Promise.all([fetchTasks(), fetchRecentBatches()])
    } catch (error: any) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error(await resolveRequestErrorMessage(error, '重试失败'))
      }
    } finally {
      retryingTaskIds.value = retryingTaskIds.value.filter((id) => id !== taskId)
    }
  }

  const handleBatchDeleteTasks = async () => {
    const ids = Array.from(new Set(selectedTaskIds.value))
    selectedTaskIds.value = ids
    if (ids.length === 0) {
      ElMessage.warning('请先选择要删除的决策档案')
      return
    }

    const selectedCurrentRows = tasks.value.filter((item) => ids.includes(Number(item.id)))
    if (selectedCurrentRows.some((item) => !canDeleteTask(item))) {
      ElMessage.warning('已选择的档案中包含执行中的任务，请先取消或等待结束')
      return
    }

    try {
      await confirmDeleteTasks(ids.length)
      markTasksDeleting(ids)
      const res: any = await batchDeleteDecisionTasks(selectedTaskIds.value)
      if (res.code !== 200) {
        ElMessage.error(res.message || '批量删除失败')
        return
      }

      ElMessage.success('决策档案已批量删除')
      closeDrawerIfCurrentTaskDeleted(ids)
      clearTaskSelection()
      normalizePageAfterDelete(ids.length)
      await fetchTasks()
    } catch (error: any) {
      if (error !== 'cancel' && error !== 'close') {
        ElMessage.error(await resolveRequestErrorMessage(error, '批量删除失败'))
      }
    } finally {
      unmarkTasksDeleting(ids)
    }
  }

  const fetchRecentBatches = async () => {
    batchLoading.value = true
    try {
      const res: any = await getRecentPricingBatches({
        page: batchQueryParams.page,
        size: batchQueryParams.size
      })
      if (res.code !== 200) {
        ElMessage.error(res.message || '获取批量定价批次失败')
        return
      }

      recentBatches.value = res.data?.records || []
      recentBatchTotal.value = Number(res.data?.total || 0)
    } catch (error) {
      ElMessage.error(await resolveRequestErrorMessage(error, '获取批量定价批次失败'))
    } finally {
      batchLoading.value = false
    }
  }

  const handleBatchSizeChange = () => {
    batchQueryParams.page = 1
    void fetchRecentBatches()
  }

  const handleBatchPageChange = () => {
    void fetchRecentBatches()
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
        agentLogs.value = filterLatestAgentRunRound(res.data || [])
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

  const openBatchDetail = async (row: PricingBatchDetail) => {
    const batchId = Number(row.batchId || 0)
    if (!batchId) return
    await router.push(`/archive/batches/${batchId}`)
  }

  const batchStatusText = (status?: string | null) => PRICING_STATUS_LABELS[String(status || '').trim().toUpperCase()] || status || '-'
  const batchStatusTagType = (status?: string | null) => PRICING_STATUS_TAG_TYPES[String(status || '').trim().toUpperCase()] || 'info'
  const batchGoalLabel = (goal?: string | null) => PRICING_GOAL_LABELS[String(goal || '').trim()] || goal || '-'
  const batchProgressText = (row: PricingBatchDetail) => {
    const totalCount = Number(row.totalCount || 0)
    const terminalCount = Number(row.completedCount || 0)
      + Number(row.manualReviewCount || 0)
      + Number(row.failedCount || 0)
      + Number(row.cancelledCount || 0)
    return `${terminalCount} / ${totalCount}`
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
    await Promise.all([fetchTasks(), fetchRecentBatches()])
    await openTaskFromRoute()
  })

  onActivated(() => {
    if (!hasSkippedInitialActivation) {
      hasSkippedInitialActivation = true
      return
    }
    void Promise.all([fetchTasks(), fetchRecentBatches()])
  })

  watch(() => route.query.taskId, () => {
    void openTaskFromRoute()
  })

  return {
    activeTab,
    agentLogs,
    applyingResultIds,
    archiveEvidenceBoard,
    batchGoalLabel,
    batchLoading,
    batchProgressText,
    batchQueryParams,
    batchStatusTagType,
    batchStatusText,
    canDeleteTask,
    canRetryTask,
    chartRef,
    clearTaskSelection,
    comparisonData,
    currentTask,
    dateRange,
    detailLoading,
    drawerSize,
    drawerVisible,
    exportReport,
    fetchRecentBatches,
    fetchTasks,
    formatCurrency,
    formatDateTime,
    formatPercent,
    formatRange: formatPriceRange,
    formatSignedCurrency,
    getLogFailureSummary,
    getLogAgentName,
    getLogEvidenceLines,
    getLogReason,
    getLogSuggestionHighlightLabel,
    getLogSuggestionHighlightPrice,
    getLogSuggestionLines,
    getLogThinking,
    getRunStatusType,
    getRunStatusText,
    handleBatchPageChange,
    handleBatchSizeChange,
    handleBatchDeleteTasks,
    handleDateChange,
    handleDeleteTask,
    handleRetryTask,
    handleSearch,
    handleSortChange,
    handleTaskSelectionChange,
    isSuccessStatus,
    isFailedLog,
    isTaskDeleting,
    isTaskRetrying,
    loading,
    openBatchDetail,
    orderedLogs,
    orderedLogCards,
    queryParams,
    recentBatches,
    recentBatchTotal,
    resetFilters,
    retryingTaskIds,
    selectedTaskIds,
    stats,
    statusMap: STATUS_MAP,
    statusOptions: STATUS_OPTIONS,
    statusTypeMap: STATUS_TYPE_MAP,
    summaryRow,
    taskTableRef,
    tasks,
    toNaturalChinese,
    total,
    viewDetails,
    applyPrice
  }
}

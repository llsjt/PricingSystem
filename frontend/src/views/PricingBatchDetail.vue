<template>
  <div class="page-shell batch-page">
    <section class="panel-card batch-hero">
      <div class="section-head">
        <div class="section-title">
          <h2>批量定价进度</h2>
          <p>批次号 {{ detail?.batchCode || '-' }}，策略目标 {{ goalLabel }}。</p>
        </div>
        <div class="toolbar-actions">
          <el-button @click="loadBatch">刷新</el-button>
          <el-button v-if="canCancelBatch" type="warning" plain :loading="cancelling" @click="handleCancelBatch">
            取消批次
          </el-button>
        </div>
      </div>

      <div class="meta-strip">
        <article class="meta-card">
          <span>批次状态</span>
          <strong>
            <el-tag :type="statusTagType(detail?.batchStatus)">{{ statusText(detail?.batchStatus) }}</el-tag>
          </strong>
        </article>
        <article class="meta-card">
          <span>商品总数</span>
          <strong>{{ detail?.totalCount || 0 }}</strong>
        </article>
        <article class="meta-card">
          <span>执行中</span>
          <strong>{{ detail?.runningCount || 0 }}</strong>
        </article>
        <article class="meta-card">
          <span>人工审核</span>
          <strong>{{ detail?.manualReviewCount || 0 }}</strong>
        </article>
        <article class="meta-card">
          <span>失败/创建失败</span>
          <strong>{{ detail?.failedCount || 0 }}</strong>
        </article>
      </div>
    </section>

    <section class="panel-card filter-panel">
      <div class="filter-head">
        <h3>批次明细</h3>
        <span>创建时间 {{ formatDateTime(detail?.createdAt) }}</span>
      </div>
      <div class="filter-grid">
        <el-select v-model="query.status" clearable placeholder="状态筛选">
          <el-option label="全部状态" value="" />
          <el-option v-for="item in statusOptions" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <div class="toolbar-actions">
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </div>
      </div>
    </section>

    <section class="panel-card table-card">
      <el-table v-loading="loading" :data="rows" border stripe :resizable="false">
        <el-table-column prop="itemOrder" label="#" width="70" />
        <el-table-column prop="productTitle" label="商品名称" min-width="220" show-overflow-tooltip />
        <el-table-column label="当前售价" width="120">
          <template #default="{ row }">{{ formatCurrency(row.currentPrice) }}</template>
        </el-table-column>
        <el-table-column label="建议价" width="120">
          <template #default="{ row }">{{ formatCurrency(row.finalPrice) }}</template>
        </el-table-column>
        <el-table-column prop="expectedSales" label="预期销量" width="110" />
        <el-table-column label="预期利润" width="120">
          <template #default="{ row }">{{ formatCurrency(row.expectedProfit) }}</template>
        </el-table-column>
        <el-table-column prop="executeStrategy" label="执行策略" width="120" show-overflow-tooltip />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.displayStatus)">{{ statusText(row.displayStatus) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="错误信息" width="130">
          <template #default="{ row }">
            <el-button
              v-if="hasErrorMessage(row)"
              link
              type="danger"
              class="error-link"
              @click="showErrorDetail(row)"
            >
              查看错误
            </el-button>
            <span v-else>无</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" fixed="right" width="140">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button v-if="row.taskId" link type="primary" @click="openTaskArchive(row.taskId!)">任务详情</el-button>
              <el-button
                v-if="canApply(row)"
                link
                type="success"
                :loading="applyingIds.includes(Number(row.resultId || 0))"
                @click="applyRow(row)"
              >
                {{ applyActionText(row) }}
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="table-footer">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadItems"
          @current-change="loadItems"
        />
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onDeactivated, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { applyDecision } from '../api/decision'
import {
  cancelPricingBatch,
  getPricingBatchDetail,
  getPricingBatchItems,
  type PricingBatchDetail,
  type PricingBatchItem
} from '../api/pricingBatch'
import { resolveRequestErrorMessage } from '../utils/error'
import { formatCurrency, formatDateTime } from '../utils/formatters'
import {
  PRICING_BATCH_STATUS_OPTIONS,
  PRICING_GOAL_LABELS,
  PRICING_STATUS_LABELS,
  PRICING_STATUS_TAG_TYPES
} from '../utils/pricingTaskOptions'

interface ApiResponse<T> {
  code: number
  data: T
  message?: string
}

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const cancelling = ref(false)
const detail = ref<PricingBatchDetail | null>(null)
const rows = ref<PricingBatchItem[]>([])
const total = ref(0)
const applyingIds = ref<number[]>([])

const query = reactive({
  page: 1,
  size: 10,
  status: ''
})

let pollTimer: ReturnType<typeof setInterval> | null = null
const isViewActive = ref(false)

const batchId = computed(() => Number(route.params.batchId || 0))
const isBatchDetailRouteActive = computed(() => isViewActive.value && route.name === 'PricingBatchDetail')
const hasValidBatchId = computed(() => Number.isInteger(batchId.value) && batchId.value > 0)
const goalLabel = computed(() => {
  const value = String(detail.value?.strategyGoal || '')
  return PRICING_GOAL_LABELS[value] || value || '-'
})
const statusOptions = PRICING_BATCH_STATUS_OPTIONS
const canCancelBatch = computed(() => {
  if (!detail.value) return false
  return detail.value.batchStatus === 'RUNNING' && Number(detail.value.runningCount || 0) > 0
})

const statusText = (status?: string | null) => PRICING_STATUS_LABELS[String(status || '').trim().toUpperCase()] || status || '-'
const statusTagType = (status?: string | null) => PRICING_STATUS_TAG_TYPES[String(status || '').trim().toUpperCase()] || 'info'
const shouldPollBatch = (value?: PricingBatchDetail | null) =>
  Number(value?.runningCount || 0) > 0 || Number(value?.manualReviewCount || 0) > 0

const stopPolling = () => {
  if (!pollTimer) return
  clearInterval(pollTimer)
  pollTimer = null
}

const startPolling = () => {
  stopPolling()
  if (!isBatchDetailRouteActive.value || !shouldPollBatch(detail.value)) return
  pollTimer = setInterval(async () => {
    if (!isBatchDetailRouteActive.value) {
      stopPolling()
      return
    }
    await loadBatch(false)
    if (!shouldPollBatch(detail.value)) {
      stopPolling()
    }
  }, 2000)
}

const loadDetail = async () => {
  const res = await getPricingBatchDetail(batchId.value) as ApiResponse<PricingBatchDetail>
  if (res.code !== 200 || !res.data) {
    throw new Error(res.message || '加载批次详情失败')
  }
  detail.value = res.data
}

const loadItems = async () => {
  const res = await getPricingBatchItems(batchId.value, {
    page: query.page,
    size: query.size,
    status: query.status || undefined
  }) as ApiResponse<{ records: PricingBatchItem[]; total: number }>
  if (res.code !== 200 || !res.data) {
    throw new Error(res.message || '加载批次明细失败')
  }
  rows.value = res.data.records || []
  total.value = Number(res.data.total || 0)
}

const loadBatch = async (showLoading = true) => {
  if (!isBatchDetailRouteActive.value) {
    stopPolling()
    return
  }
  if (!hasValidBatchId.value) {
    stopPolling()
    ElMessage.error('批次编号无效')
    await router.replace('/archive')
    return
  }
  if (showLoading) loading.value = true
  try {
    await Promise.all([loadDetail(), loadItems()])
    startPolling()
  } catch (error) {
    ElMessage.error(await resolveRequestErrorMessage(error, '加载批次详情失败'))
  } finally {
    if (showLoading) loading.value = false
  }
}

const handleSearch = () => {
  query.page = 1
  void loadItems()
}

const resetFilters = () => {
  query.page = 1
  query.status = ''
  void loadItems()
}

const openTaskArchive = async (taskId: number) => {
  await router.push({
    path: '/archive',
    query: { taskId: String(taskId) }
  })
}

const canApply = (row: PricingBatchItem) =>
  Boolean(row.resultId && row.appliedStatus !== '已应用' && ['MANUAL_REVIEW', 'COMPLETED'].includes(String(row.displayStatus || '').toUpperCase()))

const applyActionText = (row: PricingBatchItem) =>
  String(row.displayStatus || '').toUpperCase() === 'MANUAL_REVIEW' ? '通过并应用' : '应用建议'

const hasErrorMessage = (row: PricingBatchItem) => Boolean(String(row.errorMessage || '').trim())

const showErrorDetail = (row: PricingBatchItem) => {
  const message = String(row.errorMessage || '').trim()
  if (!message) return
  ElMessageBox.alert(message, `错误详情 - ${String(row.productTitle || '-')}`, {
    confirmButtonText: '关闭',
    customClass: 'batch-error-dialog'
  })
}

const applyRow = async (row: PricingBatchItem) => {
  const resultId = Number(row.resultId || 0)
  if (!resultId) {
    ElMessage.error('未找到可应用的结果记录')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认将商品“${String(row.productTitle || '-')}”的售价更新为 ${formatCurrency(row.finalPrice)} 吗？`,
      '应用价格建议',
      {
        type: 'warning',
        confirmButtonText: '确认应用',
        cancelButtonText: '取消'
      }
    )
    applyingIds.value.push(resultId)
    const res: any = await applyDecision(resultId)
    if (res.code !== 200) {
      ElMessage.error(res.message || '应用失败')
      return
    }
    ElMessage.success('价格建议已应用')
    await loadBatch(false)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(await resolveRequestErrorMessage(error, '应用失败'))
    }
  } finally {
    applyingIds.value = applyingIds.value.filter((id) => id !== resultId)
  }
}

const handleCancelBatch = async () => {
  if (!canCancelBatch.value) return
  try {
    await ElMessageBox.confirm('确认取消当前批次中仍可取消的子任务吗？', '取消批次', {
      type: 'warning',
      confirmButtonText: '确认取消',
      cancelButtonText: '继续执行'
    })
    cancelling.value = true
    const res = await cancelPricingBatch(batchId.value) as ApiResponse<{ cancelledCount: number; skippedCount: number }>
    if (res.code !== 200 || !res.data) {
      ElMessage.error(res.message || '取消批次失败')
      return
    }
    ElMessage.warning(`已取消 ${Number(res.data.cancelledCount || 0)} 个子任务，跳过 ${Number(res.data.skippedCount || 0)} 个`)
    await loadBatch(false)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(await resolveRequestErrorMessage(error, '取消批次失败'))
    }
  } finally {
    cancelling.value = false
  }
}

onActivated(() => {
  isViewActive.value = true
  void loadBatch()
})

onDeactivated(() => {
  isViewActive.value = false
  stopPolling()
})

onBeforeUnmount(() => {
  isViewActive.value = false
  stopPolling()
})
</script>

<style scoped>
.batch-page {
  gap: 16px;
}

.batch-hero {
  padding: 14px 16px;
}

.meta-strip {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.meta-card {
  display: grid;
  gap: 8px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(31, 46, 77, 0.06);
  background: var(--surface-2);
}

.meta-card span {
  color: var(--text-3);
  font-size: 13px;
}

.meta-card strong {
  color: var(--text-1);
  font-size: 24px;
  line-height: 1.1;
}

.filter-panel {
  padding: 12px 14px;
}

.filter-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.filter-head h3 {
  margin: 0;
  font-size: 22px;
}

.filter-head span {
  color: var(--text-3);
  font-size: 13px;
}

.filter-grid {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.filter-grid :deep(.el-select) {
  width: 220px;
}

.table-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  min-width: 0;
}

.table-actions :deep(.el-button) {
  min-height: 22px;
  margin-left: 0;
  padding: 0;
}

.error-link {
  padding: 0;
}

:deep(.batch-error-dialog .el-message-box__message) {
  max-height: 360px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
}

.table-footer {
  display: flex;
  justify-content: center;
  margin-top: 14px;
}

@media (max-width: 1100px) {
  .meta-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .meta-strip,
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .filter-grid {
    display: grid;
  }

  .filter-grid :deep(.el-select) {
    width: 100%;
  }

  .filter-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

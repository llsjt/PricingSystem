<template>
  <div class="page-shell archive-page">
    <section class="panel-card archive-hero">
      <div class="section-title">
        <h2>决策档案</h2>
      </div>
      <div class="summary-strip">
        <article class="summary-item">
          <span>任务总数</span>
          <strong>{{ stats.total }}</strong>
        </article>
        <article class="summary-item">
          <span>已完成</span>
          <strong>{{ stats.completed }}</strong>
        </article>
        <article class="summary-item">
          <span>执行中</span>
          <strong>{{ stats.running }}</strong>
        </article>
        <article class="summary-item">
          <span>失败</span>
          <strong>{{ stats.failed }}</strong>
        </article>
      </div>
    </section>

    <section class="panel-card batch-archive-panel">
      <div class="section-head">
        <div class="section-title">
          <h3>批量定价批次</h3>
          <p>最近创建的批量定价进度，关闭标签后可从这里重新打开。</p>
        </div>
        <div class="toolbar-actions">
          <span class="batch-total">共 {{ recentBatchTotal }} 个批次</span>
          <el-button @click="fetchRecentBatches">刷新批次</el-button>
        </div>
      </div>

      <el-table
        v-loading="batchLoading"
        :data="recentBatches"
        border
        stripe
        :resizable="false"
      >
        <el-table-column prop="batchCode" label="批次号" min-width="220" show-overflow-tooltip />
        <el-table-column label="策略目标" width="130">
          <template #default="{ row }">{{ batchGoalLabel(row.strategyGoal) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="batchStatusTagType(row.batchStatus)">
              {{ batchStatusText(row.batchStatus) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="120">
          <template #default="{ row }">{{ batchProgressText(row) }}</template>
        </el-table-column>
        <el-table-column label="执行中" width="90">
          <template #default="{ row }">{{ row.runningCount || 0 }}</template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.createdAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" fixed="right" width="120">
          <template #default="{ row }">
            <el-button link type="primary" @click="openBatchDetail(row)">打开进度</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="recentBatchTotal > batchQueryParams.size" class="table-footer batch-pagination">
        <el-pagination
          v-model:current-page="batchQueryParams.page"
          v-model:page-size="batchQueryParams.size"
          :total="recentBatchTotal"
          :page-sizes="[5, 10, 20]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleBatchSizeChange"
          @current-change="handleBatchPageChange"
        />
      </div>
    </section>

    <section class="panel-card filter-panel">
      <div class="filter-head">
        <h3>任务筛选</h3>
        <span>当前共 {{ total }} 条任务</span>
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
        </div>
      </div>

      <el-table
        v-loading="loading"
        :data="tasks"
        border
        stripe
        :resizable="false"
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
              <el-table :data="comparisonData" border stripe :resizable="false">
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
                  <el-tag size="small" :type="getRunStatusType(log.runStatus)">
                    {{ getRunStatusText(log.runStatus) }}
                  </el-tag>
                </div>
                <span>{{ formatDateTime(log.createdAt) }}</span>
              </div>
              <section v-if="isFailedLog(log)" class="failed-log-card">
                <div class="failed-log-title">执行失败</div>
                <p class="failed-log-message">{{ getLogFailureSummary(log) }}</p>
              </section>
              <div v-else class="log-content">
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
                  <div v-if="getLogSuggestionHighlightPrice(log) != null" class="result-strip">
                    <span class="price-label">{{ getLogSuggestionHighlightLabel(log) }}</span>
                    <span class="price-value">
                      <span class="price-unit">¥</span>
                      <CountUp :value="getLogSuggestionHighlightPrice(log)" :duration="700" />
                    </span>
                  </div>
                  <ul class="info-list">
                    <li v-for="(line, idx) in getLogSuggestionLines(log)" :key="`s-${log.id}-${idx}`">{{ line }}</li>
                  </ul>
                </section>
                <section v-if="getLogReason(log)" class="log-section">
                  <h4>为什么给出这个建议</h4>
                  <p>{{ getLogReason(log) }}</p>
                </section>
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
// 决策档案页：整合任务筛选、批次追踪、详情抽屉、图表与结果应用入口。

import CountUp from '../components/CountUp.vue'
import { useArchivePage } from '../composables/useArchivePage'

const {
  activeTab,
  applyingResultIds,
  applyPrice,
  batchGoalLabel,
  batchLoading,
  batchProgressText,
  batchQueryParams,
  batchStatusTagType,
  batchStatusText,
  chartRef,
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
  formatRange,
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
  handleDateChange,
  handleSearch,
  handleSortChange,
  isFailedLog,
  loading,
  openBatchDetail,
  orderedLogs,
  queryParams,
  recentBatches,
  recentBatchTotal,
  resetFilters,
  stats,
  statusMap,
  statusOptions,
  statusTypeMap,
  summaryRow,
  tasks,
  toNaturalChinese,
  total,
  viewDetails
} = useArchivePage()
</script>

<style scoped>
.archive-page {
  gap: 16px;
}

.archive-hero {
  padding: 12px 14px;
}

.archive-hero .section-title {
  margin-bottom: 10px;
}

.batch-archive-panel {
  padding: 12px 14px;
}

.batch-archive-panel .section-head {
  margin-bottom: 12px;
}

.batch-archive-panel .section-title p {
  margin: 4px 0 0;
  color: var(--text-3);
  font-size: 13px;
}

.batch-total {
  color: var(--text-3);
  font-size: 13px;
}

.filter-panel {
  padding: 10px 12px;
}

.summary-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 14px;
  border-radius: 12px;
  border: 1px solid rgba(31, 46, 77, 0.06);
  background: var(--surface-2);
}

.summary-item span {
  color: var(--text-2);
  font-size: 13px;
}

.summary-item strong {
  color: var(--text-1);
  font-size: 24px;
  line-height: 1;
  font-weight: 700;
}

.filter-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.filter-head h3 {
  margin: 0;
  font-size: 24px;
}

.filter-head span {
  color: var(--text-3);
  font-size: 12px;
}

.filter-grid {
  display: grid;
  grid-template-columns: 180px minmax(320px, 1fr) auto;
  align-items: center;
  gap: 12px;
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
  margin-top: 14px;
}

.drawer-meta {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.drawer-meta-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(31, 46, 77, 0.06);
  background: var(--surface-2);
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
  padding: 0;
  border: 0;
  background: transparent;
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
  padding: 16px 18px;
  border-radius: 14px;
  border: 1px solid rgba(31, 46, 77, 0.06);
  background: var(--surface-2);
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

.failed-log-card {
  display: grid;
  gap: 8px;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid rgba(239, 68, 68, 0.18);
  background: #fef2f2;
}

.failed-log-title {
  font-size: 14px;
  font-weight: 700;
  color: #b42318;
}

.failed-log-message {
  margin: 0;
  line-height: 1.7;
  color: #7a271a;
}

.log-section {
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(31, 46, 77, 0.06);
  background: #ffffff;
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

.result-strip {
  margin: 0 0 12px;
  padding: 12px 14px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #dbeafe;
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
}

.price-label {
  font-size: 14px;
  color: var(--text-2);
  font-weight: 600;
}

.price-value {
  font-size: 26px;
  font-weight: 800;
  color: #1f6feb;
  letter-spacing: 0;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.price-unit {
  font-size: 17px;
  font-weight: 600;
  opacity: 0.7;
  margin-right: 3px;
}

.price-text {
  font-weight: 700;
  color: var(--accent);
}

@media (max-width: 1200px) {
  .summary-strip,
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
  .summary-strip,
  .drawer-meta,
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .summary-item strong {
    font-size: 20px;
  }

  .filter-head {
    flex-direction: column;
    align-items: flex-start;
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

  .result-strip {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
}
</style>

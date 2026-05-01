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
        <div class="toolbar-actions">
          <el-tag v-if="selectedTaskIds.length > 0" type="success">已选择 {{ selectedTaskIds.length }} 条</el-tag>
          <el-button link type="danger" :disabled="selectedTaskIds.length === 0" @click="clearTaskSelection">
            清空选择
          </el-button>
          <el-button type="danger" :disabled="selectedTaskIds.length === 0" @click="handleBatchDeleteTasks">
            批量删除
          </el-button>
        </div>
      </div>

      <el-table
        ref="taskTableRef"
        v-loading="loading"
        :data="tasks"
        row-key="id"
        border
        stripe
        :resizable="false"
        @selection-change="handleTaskSelectionChange"
        @sort-change="handleSortChange"
      >
        <el-table-column type="selection" width="46" :reserve-selection="true" :selectable="canDeleteTask" />
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
        <el-table-column label="操作" fixed="right" width="210">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewDetails(row)">查看详情</el-button>
            <el-button
              v-if="canRetryTask(row)"
              link
              type="warning"
              :loading="isTaskRetrying(Number(row.id))"
              @click="handleRetryTask(row)"
            >
              重试
            </el-button>
            <el-button
              link
              type="danger"
              :disabled="!canDeleteTask(row)"
              :loading="isTaskDeleting(Number(row.id))"
              @click="handleDeleteTask(row)"
            >
              删除
            </el-button>
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
            <el-button
              v-if="canRetryTask(currentTask)"
              type="warning"
              plain
              :loading="currentTask ? isTaskRetrying(Number(currentTask.id)) : false"
              @click="currentTask && handleRetryTask(currentTask)"
            >
              重试任务
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
          <section v-if="archiveEvidenceBoard" class="panel-card embedded-panel archive-evidence-board">
            <div class="section-head archive-evidence-head">
              <div class="section-title">
                <span class="archive-evidence-kicker">Decision Evidence</span>
                <h3>决策证据板</h3>
                <p>{{ archiveEvidenceBoard.decisionSummary || '汇总四个席位的证据、处理状态与最终裁决。' }}</p>
              </div>
            </div>
            <div class="archive-evidence-overview">
              <article v-for="item in archiveEvidenceBoard.overviewItems" :key="item.label" class="archive-evidence-metric">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </article>
            </div>
            <div
              v-if="archiveEvidenceBoard.decisionSummary || archiveEvidenceBoard.decisionReason || archiveEvidenceBoard.selectedStrategy"
              class="archive-evidence-summary"
            >
              <article v-if="archiveEvidenceBoard.decisionSummary" class="archive-evidence-summary-item">
                <span>裁决结论</span>
                <p>{{ archiveEvidenceBoard.decisionSummary }}</p>
              </article>
              <article v-if="archiveEvidenceBoard.decisionReason" class="archive-evidence-summary-item">
                <span>裁决理由</span>
                <p>{{ archiveEvidenceBoard.decisionReason }}</p>
              </article>
              <article v-if="archiveEvidenceBoard.selectedStrategy" class="archive-evidence-summary-item">
                <span>采纳策略</span>
                <p>{{ archiveEvidenceBoard.selectedStrategy }}</p>
              </article>
            </div>
            <div class="archive-evidence-matrix archive-matrix-grid">
              <div class="archive-evidence-matrix-head archive-matrix-grid">
                <span>席位</span>
                <span>建议价</span>
                <span>置信度/风险</span>
                <span>证据摘要</span>
                <span>处理状态</span>
              </div>
              <div
                v-for="row in archiveEvidenceBoard.matrixRows"
                :key="row.key"
                class="archive-evidence-matrix-row archive-matrix-grid"
              >
                <div class="archive-evidence-seat">
                  <span class="archive-evidence-mark">{{ row.agentMark }}</span>
                  <div>
                    <strong>{{ row.agentName }}</strong>
                    <span>{{ row.roleLabel }}</span>
                  </div>
                </div>
                <span class="archive-evidence-price">{{ row.priceText }}</span>
                <span class="archive-evidence-copy">{{ row.confidenceText }}</span>
                <span class="archive-evidence-copy">{{ row.evidenceText }}</span>
                <span class="archive-evidence-state">
                  <el-tag size="small" :type="row.stateType">{{ row.stateText }}</el-tag>
                </span>
              </div>
            </div>
          </section>
          <div class="logs-panel archive-agent-timeline">
            <article
              v-for="card in orderedLogCards"
              :key="card.log.id"
              class="log-card archive-agent-card"
              :class="card.agentCode ? `archive-agent-${card.agentCode.toLowerCase().replace('_', '-')}` : ''"
            >
              <div class="archive-agent-rail">
                <span class="archive-agent-avatar">{{ card.agentMark }}</span>
              </div>

              <div class="archive-agent-body">
                <div class="log-head archive-agent-head">
                  <div class="log-title archive-agent-title">
                    <div>
                      <strong>{{ card.agentName }}</strong>
                      <span>{{ card.roleLabel }}</span>
                    </div>
                    <el-tag size="small" :type="card.runStatusType">
                      {{ card.runStatusText }}
                    </el-tag>
                  </div>
                  <time>{{ formatDateTime(card.log.createdAt) }}</time>
                </div>

                <section v-if="isFailedLog(card.log)" class="failed-log-card">
                  <div class="failed-log-title">执行失败</div>
                  <p class="failed-log-message">{{ card.failureSummary }}</p>
                </section>

                <template v-else>
                  <div class="log-content archive-agent-output-grid">
                    <section class="log-section archive-thinking-block">
                      <h4>思考过程</h4>
                      <p>{{ card.thinking }}</p>
                    </section>

                    <section class="log-section">
                      <h4>依据</h4>
                      <ul class="info-list archive-evidence-list">
                        <li v-for="(line, idx) in card.evidenceLines" :key="`e-${card.log.id}-${idx}`">{{ line }}</li>
                      </ul>
                    </section>

                    <section class="log-section archive-suggestion-block">
                      <h4>建议</h4>
                      <div v-if="card.suggestionHighlightPrice != null" class="result-strip archive-suggestion-highlight">
                        <span class="price-label">{{ card.suggestionHighlightLabel }}</span>
                        <span class="price-value">
                          <span class="price-unit">¥</span>
                          <CountUp :value="card.suggestionHighlightPrice" :duration="700" />
                        </span>
                      </div>
                      <ul class="info-list archive-suggestion-list">
                        <li v-for="(line, idx) in card.suggestionLines" :key="`s-${card.log.id}-${idx}`">{{ line }}</li>
                      </ul>
                    </section>

                    <section v-if="card.reason" class="log-section archive-reason-block">
                      <h4>建议原因</h4>
                      <p>{{ card.reason }}</p>
                    </section>
                  </div>

                  <section v-if="card.arbitration" class="archive-arbitration-panel">
                    <div class="archive-arbitration-head">
                      <div>
                        <span class="archive-arbitration-kicker">经理裁决</span>
                        <h4>分歧与裁决</h4>
                      </div>
                      <div v-if="card.arbitration.consensusScoreText" class="consensus-meter">
                        <span>共识度</span>
                        <strong>{{ card.arbitration.consensusScoreText }}</strong>
                        <div
                          class="consensus-track"
                          role="progressbar"
                          aria-valuemin="0"
                          aria-valuemax="100"
                          :aria-valuenow="card.arbitration.consensusScorePercent || 0"
                        >
                          <span :style="{ width: `${card.arbitration.consensusScorePercent || 0}%` }"></span>
                        </div>
                      </div>
                    </div>

                    <div v-if="card.arbitration.decisionSummary || card.arbitration.decisionReason" class="archive-arbitration-summary-grid">
                      <div v-if="card.arbitration.decisionSummary" class="archive-arbitration-summary-item">
                        <span>裁决结论</span>
                        <p>{{ card.arbitration.decisionSummary }}</p>
                      </div>
                      <div v-if="card.arbitration.decisionReason" class="archive-arbitration-summary-item">
                        <span>裁决理由</span>
                        <p>{{ card.arbitration.decisionReason }}</p>
                      </div>
                    </div>

                    <div class="archive-arbitration-detail-grid">
                      <div v-if="card.arbitration.disagreementSummary || card.arbitration.disagreementPoints.length" class="archive-arbitration-block">
                        <div class="archive-block-title">
                          <span></span>
                          <strong>分歧焦点</strong>
                        </div>
                        <p v-if="card.arbitration.disagreementSummary" class="archive-muted">{{ card.arbitration.disagreementSummary }}</p>
                        <ul v-if="card.arbitration.disagreementPoints.length" class="archive-number-list">
                          <li v-for="(line, idx) in card.arbitration.disagreementPoints" :key="`d-${card.log.id}-${idx}`">
                            <span>{{ idx + 1 }}</span>
                            <p>{{ line }}</p>
                          </li>
                        </ul>
                      </div>

                      <div v-if="card.arbitration.acceptedOpinions.length || card.arbitration.rejectedOpinions.length" class="archive-arbitration-block">
                        <div class="archive-block-title">
                          <span></span>
                          <strong>意见处理</strong>
                        </div>
                        <div v-if="card.arbitration.acceptedOpinions.length" class="archive-opinion-group">
                          <span class="archive-opinion-label is-accepted">已采纳</span>
                          <ul class="archive-number-list">
                            <li v-for="(line, idx) in card.arbitration.acceptedOpinions" :key="`a-${card.log.id}-${idx}`">
                              <span>{{ idx + 1 }}</span>
                              <p>{{ line }}</p>
                            </li>
                          </ul>
                        </div>
                        <div v-if="card.arbitration.rejectedOpinions.length" class="archive-opinion-group">
                          <span class="archive-opinion-label is-rejected">未采纳</span>
                          <ul class="archive-number-list">
                            <li v-for="(line, idx) in card.arbitration.rejectedOpinions" :key="`r-${card.log.id}-${idx}`">
                              <span>{{ idx + 1 }}</span>
                              <p>{{ line }}</p>
                            </li>
                          </ul>
                        </div>
                      </div>
                    </div>

                    <div v-if="card.arbitration.selectedAgent || card.arbitration.selectedPrice || card.arbitration.selectedStrategy" class="archive-final-decision-strip">
                      <div v-if="card.arbitration.selectedAgent">
                        <span>采纳方案</span>
                        <strong>{{ card.arbitration.selectedAgent }}</strong>
                      </div>
                      <div v-if="card.arbitration.selectedPrice" class="archive-final-price">
                        <span>采纳价格</span>
                        <strong>{{ card.arbitration.selectedPrice }}</strong>
                      </div>
                      <div v-if="card.arbitration.selectedStrategy">
                        <span>采纳策略</span>
                        <strong>{{ card.arbitration.selectedStrategy }}</strong>
                      </div>
                    </div>
                  </section>
                </template>
              </div>
            </article>
            <el-empty v-if="orderedLogCards.length === 0" description="暂无协同日志" />
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
  handleBatchDeleteTasks,
  handleBatchPageChange,
  handleBatchSizeChange,
  handleDateChange,
  handleDeleteTask,
  handleRetryTask,
  handleSearch,
  handleSortChange,
  handleTaskSelectionChange,
  isFailedLog,
  isTaskDeleting,
  isTaskRetrying,
  loading,
  openBatchDetail,
  orderedLogCards,
  queryParams,
  recentBatches,
  recentBatchTotal,
  resetFilters,
  selectedTaskIds,
  stats,
  statusMap,
  statusOptions,
  statusTypeMap,
  summaryRow,
  taskTableRef,
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

.archive-evidence-board {
  display: grid;
  gap: 14px;
}

.archive-evidence-overview {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.archive-evidence-metric {
  display: grid;
  gap: 6px;
  padding: 14px;
  border: 1px solid #dbe5f0;
  border-radius: 10px;
  background: #f8fafc;
}

.archive-evidence-metric span {
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
}

.archive-evidence-metric strong {
  font-size: 20px;
  line-height: 1.2;
  color: #0f172a;
}

.archive-evidence-reason {
  margin: 0;
  color: #475569;
  line-height: 1.8;
}

.archive-evidence-matrix {
  display: grid;
  gap: 10px;
}

.archive-evidence-matrix-head,
.archive-evidence-matrix-row {
  display: grid;
  grid-template-columns: minmax(160px, 1.1fr) minmax(88px, 0.7fr) minmax(110px, 0.9fr) minmax(220px, 1.7fr) minmax(88px, 0.7fr);
  gap: 12px;
  align-items: start;
}

.archive-evidence-matrix-head {
  padding: 0 4px;
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
}

.archive-evidence-matrix-row {
  padding: 12px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  font-size: 13px;
  line-height: 1.6;
  color: #334155;
}

.archive-evidence-seat {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
}

.archive-evidence-seat strong {
  display: block;
  color: #0f172a;
  line-height: 1.4;
}

.archive-evidence-seat span {
  display: block;
  color: #64748b;
  line-height: 1.5;
}

.archive-evidence-mark {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  border: 1px solid #dbeafe;
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 700;
}

.archive-evidence-strategy {
  display: flex;
  gap: 10px;
  align-items: baseline;
  color: #475569;
}

.archive-evidence-strategy strong {
  color: #0f172a;
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
  gap: 16px;
}

.archive-agent-timeline {
  position: relative;
}

.log-card {
  padding: 0;
  border-radius: 12px;
  border: 1px solid #dbe6f4;
  background: #f8fbff;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.archive-agent-card {
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr);
  gap: 14px;
  padding: 14px 16px 16px 14px;
}

.archive-agent-card,
.archive-agent-card * {
  box-sizing: border-box;
}

.archive-agent-rail {
  display: flex;
  justify-content: center;
  align-items: flex-start;
}

.archive-agent-avatar {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 14px;
  line-height: 1;
  font-weight: 800;
  flex-shrink: 0;
}

.archive-agent-body {
  min-width: 0;
}

.log-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  color: var(--text-secondary);
}

.archive-agent-head {
  align-items: flex-start;
  padding-bottom: 12px;
  border-bottom: 1px solid #e2e8f0;
}

.log-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.archive-agent-title {
  align-items: flex-start;
  min-width: 0;
}

.archive-agent-title > div {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.archive-agent-title strong {
  color: #1e293b;
  font-size: 16px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.archive-agent-title span {
  width: fit-content;
  padding: 2px 8px;
  border-radius: 8px;
  border: 1px solid #dbeafe;
  background: #f8fafc;
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
  font-weight: 600;
}

.archive-agent-head time {
  color: #64748b;
  font-size: 13px;
  white-space: nowrap;
}

.log-content {
  display: grid;
  gap: 10px;
}

.archive-agent-output-grid {
  grid-template-columns: 1fr;
  align-items: start;
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
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #ffffff;
  min-width: 0;
}

.log-section h4 {
  margin: 0 0 8px;
  font-size: 13px;
}

.log-section p {
  margin: 0;
  color: var(--text-primary);
  line-height: 1.7;
  overflow-wrap: anywhere;
}

.archive-thinking-block,
.archive-reason-block {
  grid-column: 1 / -1;
}

.info-list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 6px;
  color: var(--text-primary);
  line-height: 1.7;
  overflow-wrap: anywhere;
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

.archive-suggestion-highlight {
  background: #eff6ff;
  border-color: #bfdbfe;
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

.archive-arbitration-panel {
  display: grid;
  gap: 12px;
  margin-top: 12px;
  padding: 14px;
  border-radius: 12px;
  border: 1px solid #bfdbfe;
  background: #eef6ff;
  min-width: 0;
}

.archive-arbitration-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.archive-arbitration-kicker {
  display: inline-flex;
  width: fit-content;
  margin-bottom: 6px;
  padding: 2px 8px;
  border-radius: 8px;
  color: #1d4ed8;
  background: #dbeafe;
  font-size: 12px;
  line-height: 1.5;
  font-weight: 700;
}

.archive-arbitration-head h4 {
  margin: 0;
  color: #0f172a;
  font-size: 18px;
  line-height: 1.3;
}

.consensus-meter {
  width: 220px;
  min-width: 180px;
  display: grid;
  grid-template-columns: auto auto;
  gap: 6px 10px;
  align-items: center;
  color: #475569;
  font-size: 13px;
}

.consensus-meter strong {
  justify-self: end;
  color: #1d4ed8;
  font-size: 15px;
}

.consensus-track {
  grid-column: 1 / -1;
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: #dbeafe;
}

.consensus-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #2563eb;
}

.archive-arbitration-summary-grid,
.archive-arbitration-detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  min-width: 0;
}

.archive-arbitration-summary-item,
.archive-arbitration-block {
  min-width: 0;
  padding: 12px 14px;
  border-radius: 8px;
  border: 1px solid #dbe6f4;
  background: #ffffff;
}

.archive-arbitration-summary-item span,
.archive-final-decision-strip span {
  display: block;
  margin-bottom: 6px;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.archive-arbitration-summary-item p,
.archive-muted,
.archive-number-list p {
  margin: 0;
  color: #334155;
  line-height: 1.7;
  overflow-wrap: anywhere;
}

.archive-block-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.archive-block-title span {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #2563eb;
}

.archive-block-title strong {
  color: #1e293b;
  font-size: 14px;
}

.archive-muted {
  margin-bottom: 10px;
}

.archive-number-list {
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
  list-style: none;
}

.archive-number-list li {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 8px;
  align-items: start;
}

.archive-number-list li > span {
  width: 24px;
  height: 24px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
}

.archive-opinion-group {
  display: grid;
  gap: 8px;
}

.archive-opinion-group + .archive-opinion-group {
  margin-top: 12px;
}

.archive-opinion-label {
  width: fit-content;
  padding: 2px 8px;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.5;
  font-weight: 700;
}

.archive-opinion-label.is-accepted {
  color: #047857;
  background: #d1fae5;
}

.archive-opinion-label.is-rejected {
  color: #b45309;
  background: #fef3c7;
}

.archive-final-decision-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.archive-final-decision-strip > div {
  min-width: 0;
  padding: 12px 14px;
  border-radius: 8px;
  border: 1px solid #dbe6f4;
  background: #ffffff;
}

.archive-final-decision-strip strong {
  display: block;
  color: #1e293b;
  font-size: 15px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.archive-final-price strong {
  color: #1f6feb;
  font-size: 22px;
  font-variant-numeric: tabular-nums;
}

@media (max-width: 1200px) {
  .summary-strip,
  .drawer-meta,
  .archive-evidence-overview {
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
  .filter-grid,
  .archive-evidence-overview,
  .archive-agent-output-grid,
  .archive-arbitration-summary-grid,
  .archive-arbitration-detail-grid,
  .archive-final-decision-strip {
    grid-template-columns: 1fr;
  }

  .archive-evidence-matrix-head {
    display: none;
  }

  .archive-evidence-matrix-row {
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

  .archive-agent-card {
    grid-template-columns: 30px minmax(0, 1fr);
    gap: 10px;
    padding: 12px;
  }

  .archive-agent-avatar {
    width: 30px;
    height: 30px;
  }

  .archive-arbitration-head {
    flex-direction: column;
  }

  .consensus-meter {
    width: 100%;
    min-width: 0;
  }

  .result-strip {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
}
</style>

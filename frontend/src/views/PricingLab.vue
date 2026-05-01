<template>
  <div class="pricing-page">
    <el-alert
      v-if="!hasLlmConfig"
      title="请先配置大模型 API 密钥"
      type="warning"
      show-icon
      :closable="false"
      class="llm-alert"
    >
      <template #default>
        使用智能定价功能需要配置您自己的大模型 API 密钥。
        <router-link to="/models" class="alert-link">前往模型管理配置</router-link>
      </template>
    </el-alert>
    <section class="panel-card workflow-card">
      <div class="section-head workflow-head">
        <div class="workflow-copy">
          <h2>任务流程</h2>
          <p>配置任务、智能决策、结果报告。</p>
        </div>
      </div>
      <el-steps :active="stepBarActive" finish-status="success" align-center>
        <el-step title="配置任务" />
        <el-step title="智能决策" />
        <el-step title="结果报告" />
      </el-steps>
    </section>

    <section v-if="activeStep === 0" class="panel-card">
      <div class="section-head"><div><h2>任务配置</h2><p>选择平台、店铺、商品并设置目标。</p></div></div>
      <el-form label-position="top" class="config-grid">
        <el-form-item label="平台">
          <el-select v-model="taskConfig.platform" clearable placeholder="请选择平台" @change="onPlatformChange">
            <el-option v-for="platform in platformOptions" :key="platform" :label="platform" :value="platform" />
          </el-select>
        </el-form-item>
        <el-form-item label="店铺">
          <el-select v-model="taskConfig.shopId" clearable placeholder="请选择店铺" :disabled="!taskConfig.platform" @change="onShopChange">
            <el-option v-for="shop in availableShops" :key="shop.id" :label="shop.shopName" :value="shop.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="商品">
          <el-select v-model="taskConfig.productId" filterable remote reserve-keyword :disabled="!canSearchProducts" :remote-method="searchProducts" :loading="searchLoading" :placeholder="productPlaceholder">
            <el-option v-for="product in productOptions" :key="product.id" :label="product.productName" :value="product.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="策略目标" class="full-span">
          <el-radio-group v-model="taskConfig.strategyGoal">
            <el-radio v-for="goal in goalOptions" :key="goal.label" :label="goal.label" border>{{ goal.name }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="约束条件" class="full-span">
          <div class="constraint-panel">
            <div class="constraint-intro">
              <strong>定价硬约束</strong>
              <span>未填写的售价区间和降价幅度不会参与限制。</span>
            </div>
            <div class="constraint-grid">
              <div class="constraint-field">
                <span class="constraint-label">最低利润率</span>
                <div class="constraint-control">
                  <el-input-number v-model="constraintForm.minProfitRatePercent" :min="0.01" :max="99.99" :step="1" :precision="2" controls-position="right" />
                  <span class="constraint-unit">%</span>
                </div>
              </div>
              <div class="constraint-field">
                <span class="constraint-label">最低售价</span>
                <div class="constraint-control">
                  <el-input-number v-model="constraintForm.minPrice" :min="0.01" :step="1" :precision="2" controls-position="right" placeholder="不限制" />
                  <span class="constraint-unit">元</span>
                </div>
              </div>
              <div class="constraint-field">
                <span class="constraint-label">最高售价</span>
                <div class="constraint-control">
                  <el-input-number v-model="constraintForm.maxPrice" :min="0.01" :step="1" :precision="2" controls-position="right" placeholder="不限制" />
                  <span class="constraint-unit">元</span>
                </div>
              </div>
              <div class="constraint-field">
                <span class="constraint-label">最大降价幅度</span>
                <div class="constraint-control">
                  <el-input-number v-model="constraintForm.maxDiscountRatePercent" :min="0.01" :max="100" :step="1" :precision="2" controls-position="right" placeholder="不限制" />
                  <span class="constraint-unit">%</span>
                </div>
              </div>
            </div>
          </div>
        </el-form-item>
      </el-form>
      <div class="toolbar"><el-button type="primary" :loading="starting" :disabled="!hasLlmConfig" @click="startTask">启动任务</el-button></div>
    </section>

    <section v-else-if="activeStep === 1" class="panel-card decision-chat-panel">
      <div class="section-head decision-chat-head">
        <div class="decision-chat-title">
          <span class="decision-chat-kicker">AI 决策流</span>
          <h2>多智能体决策</h2>
          <p>三路分析会并行呈现，经理在汇总后给出最终建议。</p>
        </div>
        <div class="toolbar decision-toolbar">
          <el-button v-if="canCancelTask" @click="cancelTask">取消任务</el-button>
          <el-button v-if="canReconfigureTask" @click="resetTask">重新配置任务</el-button>
          <el-button v-if="taskId" @click="refreshSnapshot">刷新进度</el-button>
          <el-button v-if="canSkipReveal" @click="skipRevealAnimation">跳过动画</el-button>
          <el-button type="primary" :disabled="!canViewReport" @click="activeStep = 2">查看结果报告</el-button>
        </div>
      </div>
      <div class="decision-overview-grid">
        <article class="decision-overview-card">
          <span class="decision-overview-label">当前阶段</span>
          <strong>{{ decisionOverview.primaryStatusText }}</strong>
        </article>
        <article class="decision-overview-card">
          <span class="decision-overview-label">并行分析</span>
          <strong>{{ decisionOverview.analysisStatusText }}</strong>
        </article>
        <article class="decision-overview-card">
          <span class="decision-overview-label">经理仲裁</span>
          <strong>{{ decisionOverview.managerStatusText }}</strong>
        </article>
        <article class="decision-overview-card">
          <span class="decision-overview-label">{{ decisionOverview.finalPriceLabel }}</span>
          <strong v-if="decisionOverview.finalPrice != null"><span class="price-unit">¥</span><CountUp :value="decisionOverview.finalPrice" :duration="700" /></strong>
          <strong v-else>-</strong>
        </article>
      </div>
      <section class="opinion-matrix-panel">
        <div class="opinion-matrix-head">
          <div>
            <h3>意见矩阵</h3>
            <p>四个席位的价格判断、证据摘要与处理状态会在这里统一对齐。</p>
          </div>
        </div>
        <div class="opinion-grid opinion-grid-head">
          <span>席位</span>
          <span>建议价</span>
          <span>置信度/风险</span>
          <span>证据摘要</span>
          <span>处理状态</span>
        </div>
        <div v-for="row in opinionMatrixRows" :key="row.code" class="opinion-grid opinion-grid-row" :class="`is-${row.stage}`">
          <div class="opinion-seat">
            <strong>{{ row.name }}</strong>
            <span>{{ row.role }}</span>
          </div>
          <span class="opinion-cell opinion-price-cell">{{ row.priceText }}</span>
          <span class="opinion-cell">{{ row.confidenceText }}</span>
          <span class="opinion-cell opinion-evidence-cell">{{ row.evidenceText }}</span>
          <span class="opinion-cell">
            <span class="matrix-state-chip" :class="`is-${row.stage}`">{{ row.stateText }}</span>
          </span>
        </div>
      </section>
      <div class="decision-lane-stack">
        <section v-for="section in decisionSections" :key="section.key" class="decision-lane" :class="section.panelClass">
          <div class="decision-lane-head">
            <div>
              <h3>{{ section.title }}</h3>
              <p>{{ section.description }}</p>
            </div>
          </div>
          <div class="decision-lane-grid" :class="section.gridClass">
            <article v-for="agent in section.agents" :key="agent.code" class="agent-box" :class="{ 'is-streaming': isCardRunning(agent.code) || shouldAnimate(agent.code) }">
              <div class="agent-avatar" aria-hidden="true">{{ agentIcon[agent.code] }}</div>
              <div class="agent-message">
                <div class="agent-head">
                  <div class="agent-identity">
                    <div class="agent-title">
                      <h3>{{ agent.order }}. {{ agent.name }}</h3>
                      <span class="agent-role">{{ agentRoleLabel[agent.code] }}</span>
                    </div>
                  </div>
                  <el-tag size="small" :type="getAgentStatusType(agent.code)">
                    {{ getAgentStatusText(agent.code) }}
                  </el-tag>
                </div>
                <template v-if="isCardCompleted(agent.code)">
                  <h4>分析摘要</h4>
                  <TypewriterText v-if="shouldAnimate(agent.code)" :text="state.cards[agent.code]?.thinking || '-'" :speed="typewriterSpeed" class="thinking" @done="markThinkingDone(agent.code)" />
                  <p v-else class="thinking">{{ state.cards[agent.code]?.thinking || '-' }}</p>
                  <div v-if="canShowEvidence(agent.code)" class="agent-section-head">
                    <h4>依据</h4>
                    <el-button
                      v-if="canToggleEvidenceLines(agent.code)"
                      link
                      type="primary"
                      size="small"
                      class="agent-section-toggle"
                      @click="toggleAgentSection(agent.code, 'evidence')"
                    >
                      {{ getSectionToggleText(agent.code, 'evidence', evidenceLines(agent.code).length) }}
                    </el-button>
                  </div>
                  <ul v-if="canShowEvidence(agent.code)" class="evidence-list">
                    <li v-for="(line, index) in visibleEvidenceLines(agent.code)" :key="`${agent.code}-e-${index}`" :class="{ 'fade-in-item': shouldAnimate(agent.code) }" :style="{ '--i': index }">
                      <TypewriterText v-if="isActiveEvidenceLine(agent.code, index)" :text="line" :speed="typewriterSpeed" @done="markEvidenceLineDone(agent.code)" />
                      <span v-else>{{ line }}</span>
                    </li>
                  </ul>
                  <div v-if="canShowSuggestion(agent.code)" class="agent-section-head">
                    <h4>建议</h4>
                    <el-button
                      v-if="canToggleSuggestionLines(agent.code)"
                      link
                      type="primary"
                      size="small"
                      class="agent-section-toggle"
                      @click="toggleAgentSection(agent.code, 'suggestion')"
                    >
                      {{ getSectionToggleText(agent.code, 'suggestion', suggestionLines(agent.code).length) }}
                    </el-button>
                  </div>
                  <div v-if="canShowSuggestion(agent.code) && getHighlightPrice(agent.code) != null" class="result-strip">
                    <span class="price-label">{{ getHighlightLabel(agent.code) }}</span>
                    <span class="price-value"><span class="price-unit">¥</span><CountUp :value="getHighlightPrice(agent.code)" :duration="700" /></span>
                  </div>
                  <ul v-if="canShowSuggestion(agent.code)" class="suggestion-list">
                    <li v-for="(line, index) in visibleSuggestionLines(agent.code)" :key="`${agent.code}-s-${index}`" :class="{ 'fade-in-item': shouldAnimate(agent.code) }" :style="{ '--i': index }">
                      <TypewriterText v-if="isActiveSuggestionLine(agent.code, index)" :text="line" :speed="typewriterSpeed" @done="markSuggestionLineDone(agent.code)" />
                      <span v-else>{{ line }}</span>
                    </li>
                  </ul>
                  <template v-if="canShowReason(agent.code) && agent.code === managerAgent.code && state.cards[agent.code]?.reasonWhy">
                    <h4>为什么给出这个建议</h4>
                    <TypewriterText v-if="isActiveReason(agent.code)" :text="state.cards[agent.code]?.reasonWhy || ''" :speed="typewriterSpeed" @done="markReasonDone(agent.code)" />
                    <p v-else>{{ state.cards[agent.code]?.reasonWhy }}</p>
                  </template>
                  <section v-if="canShowManagerArbitration(agent.code)" class="disagreement-and-arbitration">
                    <div class="arbitration-head">
                      <div>
                        <span class="arbitration-kicker">经理裁决</span>
                        <h4>分歧与裁决</h4>
                      </div>
                      <div v-if="getManagerArbitration(agent.code)?.consensusScoreText" class="consensus-meter">
                        <div class="consensus-meter-copy">
                          <span>共识度</span>
                          <strong>{{ getManagerArbitration(agent.code)?.consensusScoreText }}</strong>
                        </div>
                        <div class="consensus-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" :aria-valuenow="getManagerArbitration(agent.code)?.consensusScorePercent || 0">
                          <span :style="{ width: `${getManagerArbitration(agent.code)?.consensusScorePercent || 0}%` }"></span>
                        </div>
                      </div>
                    </div>
                    <div v-if="getManagerArbitration(agent.code)?.decisionSummary || getManagerArbitration(agent.code)?.decisionReason" class="arbitration-summary-grid">
                      <div v-if="getManagerArbitration(agent.code)?.decisionSummary" class="arbitration-summary-item">
                        <span>裁决结论</span>
                        <p>{{ getManagerArbitration(agent.code)?.decisionSummary }}</p>
                      </div>
                      <div v-if="getManagerArbitration(agent.code)?.decisionReason" class="arbitration-summary-item">
                        <span>裁决理由</span>
                        <p>{{ getManagerArbitration(agent.code)?.decisionReason }}</p>
                      </div>
                    </div>
                    <div class="arbitration-detail-grid">
                      <div v-if="getManagerArbitration(agent.code)?.disagreementSummary || getManagerArbitration(agent.code)?.disagreementPoints.length" class="arbitration-panel">
                        <div class="arbitration-panel-head">
                          <span class="arbitration-dot disagreement-dot"></span>
                          <h5>分歧焦点</h5>
                        </div>
                        <p v-if="getManagerArbitration(agent.code)?.disagreementSummary" class="arbitration-muted">{{ getManagerArbitration(agent.code)?.disagreementSummary }}</p>
                        <ul v-if="getManagerArbitration(agent.code)?.disagreementPoints.length" class="arbitration-list">
                          <li v-for="(line, index) in getManagerArbitration(agent.code)?.disagreementPoints || []" :key="`${agent.code}-a-d-${index}`">
                            <span class="arbitration-index">{{ index + 1 }}</span>
                            <span>{{ line }}</span>
                          </li>
                        </ul>
                      </div>
                      <div v-if="getManagerArbitration(agent.code)?.acceptedOpinions.length || getManagerArbitration(agent.code)?.rejectedOpinions.length" class="arbitration-panel">
                        <div class="arbitration-panel-head">
                          <span class="arbitration-dot decision-dot"></span>
                          <h5>意见处理</h5>
                        </div>
                        <div v-if="getManagerArbitration(agent.code)?.acceptedOpinions.length" class="opinion-group">
                          <span class="opinion-label accepted-label">已采纳</span>
                          <ul class="arbitration-list">
                            <li v-for="(line, index) in getManagerArbitration(agent.code)?.acceptedOpinions || []" :key="`${agent.code}-a-a-${index}`">
                              <span class="arbitration-index">{{ index + 1 }}</span>
                              <span>{{ line }}</span>
                            </li>
                          </ul>
                        </div>
                        <div v-if="getManagerArbitration(agent.code)?.rejectedOpinions.length" class="opinion-group">
                          <span class="opinion-label rejected-label">未采纳</span>
                          <ul class="arbitration-list">
                            <li v-for="(line, index) in getManagerArbitration(agent.code)?.rejectedOpinions || []" :key="`${agent.code}-a-j-${index}`">
                              <span class="arbitration-index">{{ index + 1 }}</span>
                              <span>{{ line }}</span>
                            </li>
                          </ul>
                        </div>
                      </div>
                    </div>
                    <div v-if="getManagerArbitration(agent.code)?.selectedAgent || getManagerArbitration(agent.code)?.selectedPrice || getManagerArbitration(agent.code)?.selectedStrategy" class="arbitration-decision-strip">
                      <div v-if="getManagerArbitration(agent.code)?.selectedAgent" class="decision-chip">
                        <span>采纳方案</span>
                        <strong>{{ getManagerArbitration(agent.code)?.selectedAgent }}</strong>
                      </div>
                      <div v-if="getManagerArbitration(agent.code)?.selectedPrice" class="decision-chip decision-chip-price">
                        <span>采纳价格</span>
                        <strong>{{ getManagerArbitration(agent.code)?.selectedPrice }}</strong>
                      </div>
                      <div v-if="getManagerArbitration(agent.code)?.selectedStrategy" class="decision-chip">
                        <span>采纳策略</span>
                        <strong>{{ getManagerArbitration(agent.code)?.selectedStrategy }}</strong>
                      </div>
                    </div>
                  </section>
                </template>
                <section v-else-if="isCardFailed(agent.code)" class="failed-card">
                  <div class="failed-card-title">执行失败</div>
                  <p class="failed-card-message">{{ getAgentFailureSummary(agent.code) }}</p>
                </section>
                <div v-else-if="isCardRunning(agent.code)" class="waiting running-pulse"><span class="pulse-dot"></span> 正在分析中...</div>
                <div v-else class="waiting">{{ getWaitingText(agent.code) }}</div>
              </div>
            </article>
          </div>
        </section>
      </div>
    </section>

    <section v-else class="report-page">
      <div class="metric-grid">
        <div class="metric-card metric-card-primary"><span>最终价格</span><strong><span class="price-unit">¥</span><CountUp :value="state.finalPrice" :duration="800" /></strong></div>
        <div class="metric-card metric-card-secondary"><span>预期销量</span><strong><CountUp v-if="expectedSales != null" :value="expectedSales" :decimals="0" :duration="700" /><template v-else>-</template></strong></div>
        <div class="metric-card metric-card-secondary"><span>预期利润</span><strong><span class="price-unit">¥</span><CountUp :value="expectedProfit" :duration="800" /></strong></div>
        <div class="metric-card metric-card-accent"><span>执行策略</span><strong>{{ strategyText || '-' }}</strong></div>
      </div>
      <section class="panel-card report-panel">
        <div class="section-head report-head">
          <div class="report-copy"><h2>结果报告</h2><p>{{ reportSummary || '最终建议由 4 个智能体的分析结果综合得出。' }}</p></div>
          <div class="toolbar report-toolbar"><el-button @click="activeStep = 1">查看智能决策过程</el-button><el-button type="primary" @click="resetTask">重新配置任务</el-button></div>
        </div>
        <el-table :data="comparisonData" border stripe class="report-table">
          <el-table-column prop="productTitle" label="商品名称" min-width="180" show-overflow-tooltip />
          <el-table-column label="原价" width="120"><template #default="{ row }">{{ currency(row.originalPrice) }}</template></el-table-column>
          <el-table-column label="建议价" width="120"><template #default="{ row }">{{ currency(row.suggestedPrice) }}</template></el-table-column>
          <el-table-column prop="expectedSales" label="预期销量" width="110" />
          <el-table-column label="预期利润" width="120"><template #default="{ row }">{{ currency(row.expectedProfit) }}</template></el-table-column>
          <el-table-column label="利润变化" width="120"><template #default="{ row }"><el-tag :type="Number(row.profitChange || 0) >= 0 ? 'success' : 'danger'">{{ signedCurrency(row.profitChange) }}</el-tag></template></el-table-column>
          <el-table-column prop="passStatus" label="风控结果" width="110" />
          <el-table-column prop="executeStrategy" label="执行策略" width="120" />
          <el-table-column prop="appliedStatus" label="应用状态" width="110" />
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.appliedStatus !== '已应用'" type="primary" link :loading="applyingIds.includes(Number(row.resultId))" @click="applyPrice(row)">应用建议</el-button>
              <el-tag v-else type="success">已应用</el-tag>
            </template>
          </el-table-column>
        </el-table>
      </section>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onActivated, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { applyDecision, cancelPricingTask, createPricingTask, getPricingTaskSnapshot, getPricingTaskStreamUrl, type AgentCardContent, type DecisionComparisonItem, type DecisionLogItem, type PricingAgentCode, type PricingTaskSnapshot, type PricingTaskStatus, type PricingTaskStreamMessage } from '../api/decision'
import { getProductList } from '../api/product'
import { getLlmConfig } from '../api/llmConfig'
import { useShopStore } from '../stores/shop'
import { getAuthToken } from '../utils/authSession'
import { extractManagerArbitrationFields, normalizeAgentOpinion, type NormalizedAgentOpinion } from '../utils/agentOpinion'
import { sanitizeErrorMessage } from '../utils/error'
import { getFailureSummary } from '../utils/failureSummary'
import { hasConfiguredLlmApiKey } from '../utils/llmConfigResponse'
import { clearRevealQueue, createRevealQueueState, finishReveal, isActiveReveal, queueRevealCardRequest } from '../utils/agentRevealQueue'
import { formatEvidenceValue, getManagerArbitrationBlock, getSuggestionLines, normalizeAgentCode, toNaturalChinese } from '../utils/decisionDisplay'
import { createDefaultPricingConstraintForm, serializePricingConstraints, validatePricingConstraintForm } from '../utils/pricingConstraints'
import { ANALYSIS_AGENT_CODES, buildDecisionStatusOverview, MANAGER_AGENT_CODE } from '../utils/pricingDecisionView'
import { buildSnapshotAgentCards } from '../utils/pricingLabSnapshot'
import { PRICING_GOAL_OPTIONS } from '../utils/pricingTaskOptions'
import { shouldKeepRevealEnabledAfterRefresh } from '../utils/revealRefresh'
import TypewriterText from '../components/TypewriterText.vue'
import CountUp from '../components/CountUp.vue'

interface ApiResponse<T> { code: number; data: T; message?: string }
interface ProductOption { id: number; productName: string }
type AgentStage = 'running' | 'completed' | 'failed'
type AgentRevealStage = 'thinking' | 'evidence' | 'suggestion' | 'reason' | 'done'
type AgentDetailSection = 'evidence' | 'suggestion'
interface RevealLineCounts { evidence: number; suggestion: number }
type InternalAgentCardContent = AgentCardContent & { __stage?: AgentStage; opinion?: NormalizedAgentOpinion | null }
interface PendingRevealCard { card: AgentCardContent | null; stage: AgentStage }
interface SnapshotLoadOptions { applyLogs?: boolean; mergeLogs?: boolean }

const agents = [{ code: 'DATA_ANALYSIS', name: '数据分析智能体', order: 1 }, { code: 'MARKET_INTEL', name: '市场情报智能体', order: 2 }, { code: 'RISK_CONTROL', name: '风险控制智能体', order: 3 }, { code: 'MANAGER_COORDINATOR', name: '经理协调智能体', order: 4 }] as const
const agentRevealOrder = agents.map((agent) => agent.code) as PricingAgentCode[]
const analysisAgentCodeSet = new Set<PricingAgentCode>(ANALYSIS_AGENT_CODES as readonly PricingAgentCode[])
const goalOptions = PRICING_GOAL_OPTIONS
const emptyCards = () => ({ DATA_ANALYSIS: null, MARKET_INTEL: null, RISK_CONTROL: null, MANAGER_COORDINATOR: null }) as Record<PricingAgentCode, InternalAgentCardContent | null>
const COMPACT_AGENT_LINE_LIMIT = 2
const typewriterSpeed = 24

const shopStore = useShopStore()
const route = useRoute()
const router = useRouter()
// 任务配置、约束表单与页面主状态集中放在这里，便于启动任务、刷新快照和结果页共用。
const taskConfig = reactive({ platform: '', shopId: undefined as number | undefined, productId: undefined as number | undefined, strategyGoal: undefined as typeof goalOptions[number]['label'] | undefined })
const constraintForm = reactive(createDefaultPricingConstraintForm())
const state = reactive({ taskStatus: 'IDLE' as PricingTaskStatus, cards: emptyCards(), finalPrice: null as number | null, strategy: '', finalSummary: '', errorMessage: '' })
const productOptions = ref<ProductOption[]>([])
const searchLoading = ref(false)
const starting = ref(false)
const activeStep = ref(0)
const taskId = ref<number | null>(null)
const comparisonData = ref<DecisionComparisonItem[]>([])
const archiveReportSummary = ref('')
const applyingIds = ref<number[]>([])
const hasLlmConfig = ref(false)
const hasSyncedLlmConfigOnce = ref(false)
const currentRunAttempt = ref<number | null>(null)
let aborter: AbortController | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null
let loadToken = 0
let snapshotLoadToken = 0
let routePrefillToken = 0
const liveRevealEnabled = ref(false)
const streamArrivedCards = reactive(new Set<PricingAgentCode>())
const revealQueue = reactive(createRevealQueueState<PricingAgentCode>())
const pendingRevealCards = reactive({} as Partial<Record<PricingAgentCode, PendingRevealCard>>)
const revealStages = reactive({} as Partial<Record<PricingAgentCode, AgentRevealStage>>)
const revealLineCounts = reactive({} as Partial<Record<PricingAgentCode, RevealLineCounts>>)
const expandedAgentSections = reactive({} as Partial<Record<PricingAgentCode, Partial<Record<AgentDetailSection, boolean>>>>)

const normalizeReplayMeta = (card?: AgentCardContent | null) => ({
  replayed: card?.replayed === true ? true : undefined,
  sourceLogId: card?.sourceLogId,
  sourceExecutionId: card?.sourceExecutionId,
  sourceRunAttempt: card?.sourceRunAttempt
})
const normalizeCard = (card?: AgentCardContent | null, stage: AgentStage = 'completed'): InternalAgentCardContent => ({
  thinking: String(card?.thinking || ''),
  evidence: Array.isArray(card?.evidence) ? card.evidence : [],
  suggestion: card?.suggestion && typeof card.suggestion === 'object' ? card.suggestion : {},
  agentOpinion: card?.agentOpinion || null,
  reasonWhy: card?.reasonWhy || null,
  opinion: normalizeAgentOpinion(card),
  ...normalizeReplayMeta(card),
  ...extractManagerArbitrationFields(card),
  __stage: stage
})
const runningCard = (): InternalAgentCardContent => ({ thinking: '', evidence: [], suggestion: {}, agentOpinion: null, reasonWhy: null, opinion: null, ...extractManagerArbitrationFields(null), __stage: 'running' })
const failedCard = (card?: AgentCardContent | null): InternalAgentCardContent => normalizeCard(card, 'failed')
const isCardRunning = (code: PricingAgentCode) => state.cards[code]?.__stage === 'running'
const isCardFailed = (code: PricingAgentCode) => state.cards[code]?.__stage === 'failed'
const isCardCompleted = (code: PricingAgentCode) => state.cards[code]?.__stage === 'completed'
const isCardDone = (code: PricingAgentCode) => isCardCompleted(code) || isCardFailed(code)
const getAgentFailureSummary = (code: PricingAgentCode) => getFailureSummary(state.cards[code], '任务执行失败')
const shouldAnimate = (code: PricingAgentCode) => analysisAgentCodeSet.has(code)
  ? streamArrivedCards.has(code)
  : streamArrivedCards.has(code) && isActiveReveal(revealQueue, code)
const canShowEvidence = (code: PricingAgentCode) => !shouldAnimate(code) || revealStages[code] === 'evidence' || revealStages[code] === 'suggestion' || revealStages[code] === 'reason' || revealStages[code] === 'done'
const canShowSuggestion = (code: PricingAgentCode) => !shouldAnimate(code) || revealStages[code] === 'suggestion' || revealStages[code] === 'reason' || revealStages[code] === 'done'
const canShowReason = (code: PricingAgentCode) => !shouldAnimate(code) || revealStages[code] === 'reason' || revealStages[code] === 'done'
const completedCardCount = computed(() => agents.filter((agent) => isCardCompleted(agent.code)).length)
const opinionStatusLabelMap: Record<string, string> = {
  PROPOSED: '已提出',
  ACCEPTED: '已采纳',
  REJECTED: '未采纳',
  MERGED: '已合并',
  BLOCKED: '已阻断'
}

const platformOptions = computed(() => Array.from(new Set(shopStore.shops.map((shop) => String(shop.platform || '').trim()).filter(Boolean))))
const availableShops = computed(() => shopStore.shops.filter((shop) => shop.platform === taskConfig.platform))
const canSearchProducts = computed(() => Boolean(taskConfig.platform && taskConfig.shopId))
const productPlaceholder = computed(() => !taskConfig.platform ? '请先选择平台' : !taskConfig.shopId ? '请先选择店铺' : '输入商品名称搜索')
const canCancelTask = computed(() => Boolean(taskId.value && ['QUEUED', 'RUNNING', 'RETRYING'].includes(state.taskStatus)))
const canReconfigureTask = computed(() => state.taskStatus === 'CANCELLED')
const canViewReport = computed(() => ['COMPLETED', 'MANUAL_REVIEW'].includes(state.taskStatus) || completedCardCount.value === agents.length)
const canSkipReveal = computed(() => Boolean(taskId.value && activeStep.value === 1 && (liveRevealEnabled.value || hasRevealInProgress())))
const stepBarActive = computed(() => activeStep.value === 2 ? 3 : activeStep.value === 1 ? 2 : 1)
const statusLabel = computed(() => ({ IDLE: '未开始', PENDING: '待执行', QUEUED: '待执行', RUNNING: '执行中', RETRYING: '重试中', MANUAL_REVIEW: '人工审核', COMPLETED: '已完成', FAILED: '失败', CANCELLED: '已取消' }[state.taskStatus] || state.taskStatus))
const managerSuggestion = computed<Record<string, unknown>>(() => state.cards.MANAGER_COORDINATOR?.suggestion && typeof state.cards.MANAGER_COORDINATOR.suggestion === 'object' ? state.cards.MANAGER_COORDINATOR.suggestion : {})
const expectedSales = computed(() => numberOf(managerSuggestion.value.expectedSales))
const expectedProfit = computed(() => numberOf(managerSuggestion.value.expectedProfit))
const strategyText = computed(() => state.strategy || String(managerSuggestion.value.strategy || ''))
const reportSummary = computed(() => archiveReportSummary.value.trim() || state.finalSummary || String(managerSuggestion.value.summary || ''))
const decisionOverview = computed(() => buildDecisionStatusOverview(state.cards, state.finalPrice))
const getAgentDisplayStatus = (code: PricingAgentCode) => {
  if (code === MANAGER_AGENT_CODE && decisionOverview.value.isTimelineInconsistent && isCardCompleted(code)) {
    return { stage: 'running', text: '等待快照对齐', tagType: 'warning' }
  }
  if (isCardFailed(code)) return { stage: 'failed', text: '失败', tagType: 'danger' }
  if (isCardCompleted(code)) return { stage: 'completed', text: '已完成', tagType: 'success' }
  if (isCardRunning(code)) return { stage: 'running', text: '分析中', tagType: 'warning' }
  return { stage: 'idle', text: '等待中', tagType: 'info' }
}
const getAgentStatusText = (code: PricingAgentCode) => getAgentDisplayStatus(code).text
const getAgentStatusType = (code: PricingAgentCode) => getAgentDisplayStatus(code).tagType
const opinionMatrixRows = computed(() => agents.map((agent) => {
  const card = state.cards[agent.code]
  const opinion = card?.opinion || null
  const displayStatus = getAgentDisplayStatus(agent.code)
  const isManagerTimelineInconsistent = agent.code === MANAGER_AGENT_CODE && decisionOverview.value.isTimelineInconsistent
  const price = opinion?.recommendedPrice
  const confidenceText = opinion?.confidence != null
    ? `${(opinion.confidence * 100).toFixed(0)}%`
    : opinion?.riskLevel
      ? toNaturalChinese(opinion.riskLevel)
      : '-'
  const evidenceText = opinion?.evidenceLines?.length
    ? opinion.evidenceLines.slice(0, 2).join('；')
    : isCardRunning(agent.code)
      ? '分析中'
      : isCardFailed(agent.code)
        ? getAgentFailureSummary(agent.code)
        : '暂无证据'
  const stateText = isManagerTimelineInconsistent
    ? displayStatus.text
    : opinion?.status
    ? (opinionStatusLabelMap[opinion.status] || opinion.status)
    : displayStatus.text
  return {
    code: agent.code,
    name: agent.name,
    role: agentRoleLabel[agent.code],
    priceText: price != null ? `¥${Number(price).toFixed(2)}` : '-',
    confidenceText,
    evidenceText,
    stateText,
    stage: displayStatus.stage
  }
}))

const numberOf = (value: unknown) => { const n = Number(value); return Number.isFinite(n) ? n : null }
const parsePositiveId = (value: unknown) => { const n = Number(Array.isArray(value) ? value[0] : value); return Number.isInteger(n) && n > 0 ? n : null }
const routeQueryText = (value: unknown) => String(Array.isArray(value) ? value[0] || '' : value || '').trim()
const currency = (value: unknown) => { const n = numberOf(value); return n == null ? '-' : n.toLocaleString('zh-CN', { style: 'currency', currency: 'CNY', minimumFractionDigits: 2, maximumFractionDigits: 2 }) }
const signedCurrency = (value: unknown) => { const n = numberOf(value); return n == null ? '-' : `${n >= 0 ? '+' : '-'}${currency(Math.abs(n))}` }
const isRunning = (status: PricingTaskStatus) => ['PENDING', 'QUEUED', 'RUNNING', 'RETRYING'].includes(status)
const isTerminal = (status: PricingTaskStatus) => ['COMPLETED', 'MANUAL_REVIEW', 'FAILED', 'CANCELLED'].includes(status)
const isArchivedTaskStatus = (status: PricingTaskStatus) => ['COMPLETED', 'MANUAL_REVIEW'].includes(status)
const stopPolling = () => { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }
const stopRealtime = () => { if (aborter) { aborter.abort(); aborter = null } stopPolling() }
const hasRevealInProgress = () => Boolean(revealQueue.active || revealQueue.queue.length)
const clearExpandedAgentSections = () => {
  agents.forEach((agent) => {
    delete expandedAgentSections[agent.code]
  })
}
// 流式动画状态与卡片内容解耦：停止动画时只清理展示队列，不影响后续用快照重建卡片。
const clearRevealState = () => { liveRevealEnabled.value = false; streamArrivedCards.clear(); clearRevealQueue(revealQueue); agents.forEach((agent) => { delete revealStages[agent.code]; delete revealLineCounts[agent.code]; delete pendingRevealCards[agent.code] }); clearExpandedAgentSections() }
const clearAgentRevealProgress = () => { streamArrivedCards.clear(); clearRevealQueue(revealQueue); agents.forEach((agent) => { delete revealStages[agent.code]; delete revealLineCounts[agent.code]; delete pendingRevealCards[agent.code] }); clearExpandedAgentSections() }
const toRunAttempt = (value: unknown): number | null => { const n = Number(value); return Number.isFinite(n) && n >= 0 ? n : null }
const syncStreamRunAttempt = (value: unknown) => {
  const attempt = toRunAttempt(value)
  if (attempt === null) return true
  if (currentRunAttempt.value !== null && attempt < currentRunAttempt.value) return false
  if (currentRunAttempt.value !== null && attempt > currentRunAttempt.value) {
    state.cards = emptyCards()
    clearAgentRevealProgress()
  }
  currentRunAttempt.value = attempt
  return true
}
const ensureRevealLineCounts = (code: PricingAgentCode) => {
  if (!revealLineCounts[code]) revealLineCounts[code] = { evidence: 0, suggestion: 0 }
  return revealLineCounts[code] as RevealLineCounts
}
const beginReveal = (code: PricingAgentCode) => { revealStages[code] = 'thinking'; revealLineCounts[code] = { evidence: 0, suggestion: 0 } }
const showCard = (code: PricingAgentCode, card: AgentCardContent | null, stage: AgentStage) => {
  state.cards[code] = stage === 'failed' ? failedCard(card) : normalizeCard(card, stage)
}
const activateQueuedReveal = (code: PricingAgentCode) => {
  const pending = pendingRevealCards[code]
  if (!pending) return
  delete pendingRevealCards[code]
  streamArrivedCards.add(code)
  beginReveal(code)
  showCard(code, pending.card, pending.stage)
  if (pending.stage === 'failed') completeReveal(code)
}
const queueStreamCard = (code: PricingAgentCode, card: AgentCardContent | null, stage: AgentStage) => {
  if (!liveRevealEnabled.value) {
    showCard(code, card, stage)
    return
  }
  if (analysisAgentCodeSet.has(code)) {
    streamArrivedCards.add(code)
    beginReveal(code)
    showCard(code, card, stage)
    if (stage === 'failed') completeReveal(code)
    return
  }
  const action = queueRevealCardRequest(revealQueue, pendingRevealCards, code, { card, stage }, agentRevealOrder)
  if (action === 'replace-active') {
    const pending = pendingRevealCards[code]
    if (!pending) return
    delete pendingRevealCards[code]
    streamArrivedCards.add(code)
    beginReveal(code)
    showCard(code, pending.card, pending.stage)
    if (pending.stage === 'failed') completeReveal(code)
    return
  }
  if (action === 'activate') activateQueuedReveal(code)
}
const completeReveal = (code: PricingAgentCode) => {
  revealStages[code] = 'done'
  streamArrivedCards.delete(code)
  const next = finishReveal(revealQueue, code)
  if (next) activateQueuedReveal(next)
}
const markThinkingDone = (code: PricingAgentCode) => {
  if (!shouldAnimate(code) || revealStages[code] !== 'thinking') return
  revealStages[code] = 'evidence'
  ensureRevealLineCounts(code).evidence = 1
}
const resetState = () => { stopRealtime(); clearRevealState(); taskId.value = null; currentRunAttempt.value = null; state.taskStatus = 'IDLE'; state.cards = emptyCards(); state.finalPrice = null; state.strategy = ''; state.finalSummary = ''; state.errorMessage = ''; comparisonData.value = []; archiveReportSummary.value = ''; streamArrivedCards.clear() }
const evidenceLines = (code: PricingAgentCode) => {
  const evidence = state.cards[code]?.evidence || []
  if (!evidence.length) return ['暂无依据']
  return evidence.map((item, index) => {
    const label = String(item.label || `依据${index + 1}`)
    return `${label}：${formatEvidenceValue(label, item.value)}`
  })
}
const suggestionLines = (code: PricingAgentCode) => {
  const suggestion = state.cards[code]?.suggestion && typeof state.cards[code]?.suggestion === 'object'
    ? state.cards[code]?.suggestion as Record<string, unknown>
    : {}
  const lines = getSuggestionLines(normalizeAgentCode(code), suggestion)
  if (code !== 'MARKET_INTEL') return lines
  const sourceStatus = String(suggestion.sourceStatus || '').toUpperCase()
  const dataQuality = String(suggestion.dataQuality || '').toUpperCase()
  const extra: string[] = []
  if (sourceStatus && sourceStatus !== 'OK') extra.push('提示：未获取到可靠竞品，市场建议已降级')
  else if (dataQuality === 'LOW') extra.push('提示：本次竞品数据不足，仅供参考')
  if (suggestion.pricingPosition) extra.push(`价格位置：${toNaturalChinese(suggestion.pricingPosition)}`)
  return [...lines, ...extra]
}
const isAgentSectionExpanded = (code: PricingAgentCode, section: AgentDetailSection) =>
  Boolean(expandedAgentSections[code]?.[section])
const setAgentSectionExpanded = (code: PricingAgentCode, section: AgentDetailSection, expanded: boolean) => {
  expandedAgentSections[code] = {
    ...(expandedAgentSections[code] || {}),
    [section]: expanded
  }
}
const toggleAgentSection = (code: PricingAgentCode, section: AgentDetailSection) => {
  setAgentSectionExpanded(code, section, !isAgentSectionExpanded(code, section))
}
const compactLines = (lines: string[], code: PricingAgentCode, section: AgentDetailSection) => {
  if (lines.length <= COMPACT_AGENT_LINE_LIMIT) return lines
  if (isAgentSectionExpanded(code, section)) return lines
  return lines.slice(0, COMPACT_AGENT_LINE_LIMIT)
}
const visibleEvidenceLines = (code: PricingAgentCode) => {
  const lines = evidenceLines(code)
  if (shouldAnimate(code) && revealStages[code] === 'evidence') {
    return lines.slice(0, Math.max(ensureRevealLineCounts(code).evidence, 1))
  }
  if (shouldAnimate(code) && revealStages[code] !== 'done') return lines
  return compactLines(lines, code, 'evidence')
}
const visibleSuggestionLines = (code: PricingAgentCode) => {
  const lines = suggestionLines(code)
  if (shouldAnimate(code) && revealStages[code] !== 'done') {
    return lines.slice(0, Math.max(ensureRevealLineCounts(code).suggestion, 1))
  }
  return compactLines(lines, code, 'suggestion')
}
const canToggleEvidenceLines = (code: PricingAgentCode) =>
  evidenceLines(code).length > COMPACT_AGENT_LINE_LIMIT && (!shouldAnimate(code) || revealStages[code] === 'done')
const canToggleSuggestionLines = (code: PricingAgentCode) =>
  suggestionLines(code).length > COMPACT_AGENT_LINE_LIMIT && (!shouldAnimate(code) || revealStages[code] === 'done')
const hiddenLineCount = (total: number) => Math.max(0, total - COMPACT_AGENT_LINE_LIMIT)
const getSectionToggleText = (code: PricingAgentCode, section: AgentDetailSection, total: number) => {
  if (isAgentSectionExpanded(code, section)) return '收起'
  return `展开 ${hiddenLineCount(total)} 条`
}
const isActiveEvidenceLine = (code: PricingAgentCode, index: number) => shouldAnimate(code) && revealStages[code] === 'evidence' && index === visibleEvidenceLines(code).length - 1
const isActiveSuggestionLine = (code: PricingAgentCode, index: number) => shouldAnimate(code) && revealStages[code] === 'suggestion' && index === visibleSuggestionLines(code).length - 1
const markEvidenceLineDone = (code: PricingAgentCode) => {
  if (!shouldAnimate(code) || revealStages[code] !== 'evidence') return
  const counts = ensureRevealLineCounts(code)
  if (counts.evidence < evidenceLines(code).length) {
    counts.evidence += 1
    return
  }
  revealStages[code] = 'suggestion'
  counts.suggestion = 1
}
const markSuggestionLineDone = (code: PricingAgentCode) => {
  if (!shouldAnimate(code) || revealStages[code] !== 'suggestion') return
  const counts = ensureRevealLineCounts(code)
  if (counts.suggestion < suggestionLines(code).length) {
    counts.suggestion += 1
    return
  }
  if (code === 'MANAGER_COORDINATOR' && state.cards[code]?.reasonWhy) {
    revealStages[code] = 'reason'
    return
  }
  completeReveal(code)
}
const agentRoleLabel: Record<PricingAgentCode, string> = { DATA_ANALYSIS: '数据判断', MARKET_INTEL: '市场判断', RISK_CONTROL: '风险校验', MANAGER_COORDINATOR: '最终协调' }
const analysisAgents = agents.filter((agent) => analysisAgentCodeSet.has(agent.code))
const managerAgent = agents.find((agent) => agent.code === MANAGER_AGENT_CODE) || agents[agents.length - 1]
const decisionSections = computed(() => [
  {
    key: 'analysis',
    title: '并行分析区',
    description: '数据、市场、风控三个分析智能体会同时展示，完成后各自更新状态。',
    panelClass: 'parallel-analysis-panel',
    gridClass: 'parallel-analysis-grid',
    agents: analysisAgents
  },
  {
    key: 'manager',
    title: '经理仲裁区',
    description: '经理在三路分析完成后汇总分歧、给出裁决并输出最终建议价。',
    panelClass: 'manager-arbitration-panel',
    gridClass: 'manager-arbitration-grid',
    agents: [managerAgent]
  }
])
const agentIcon: Record<PricingAgentCode, string> = { DATA_ANALYSIS: '数', MARKET_INTEL: '市', RISK_CONTROL: '控', MANAGER_COORDINATOR: '协' }
const getHighlightPrice = (code: PricingAgentCode): number | null => {
  const s = state.cards[code]?.suggestion && typeof state.cards[code]?.suggestion === 'object' ? state.cards[code]!.suggestion as Record<string, unknown> : {}
  const raw = code === 'MANAGER_COORDINATOR' ? s.finalPrice : s.recommendedPrice
  const n = Number(raw)
  return Number.isFinite(n) && n > 0 ? n : null
}
const getHighlightLabel = (code: PricingAgentCode) => code === 'MANAGER_COORDINATOR' ? '最终建议价' : code === 'RISK_CONTROL' ? '风控建议价' : '建议定价'
const isActiveReason = (code: PricingAgentCode) => shouldAnimate(code) && revealStages[code] === 'reason'
const markReasonDone = (code: PricingAgentCode) => {
  if (!isActiveReason(code)) return
  completeReveal(code)
}
const getManagerArbitration = (code: PricingAgentCode) => code === managerAgent.code ? getManagerArbitrationBlock(state.cards[code]) : null
const canShowManagerArbitration = (code: PricingAgentCode) => code === managerAgent.code && Boolean(getManagerArbitration(code)) && canShowReason(code)
const getWaitingText = (code: PricingAgentCode) => {
  if (code === managerAgent.code) {
    return decisionOverview.value.analysisCompletedCount === analysisAgents.length
      ? '等待经理仲裁开始...'
      : '等待前三位分析智能体完成后开始仲裁...'
  }
  return '等待分析开始...'
}

const onPlatformChange = async () => { taskConfig.shopId = undefined; taskConfig.productId = undefined; productOptions.value = []; if (availableShops.value.length === 1) { taskConfig.shopId = availableShops.value[0].id; await loadProducts() } }
const onShopChange = async () => { taskConfig.productId = undefined; productOptions.value = []; if (taskConfig.shopId) await loadProducts() }
const searchProducts = (keyword: string) => { void loadProducts(keyword) }
const loadProducts = async (keyword = '') => { const token = ++loadToken; if (!canSearchProducts.value) return; searchLoading.value = true; try { const res = await getProductList({ page: 1, size: 100, keyword, platform: taskConfig.platform || undefined, shopId: taskConfig.shopId }) as ApiResponse<{ records: Array<{ id: number; productName: string }> }>; if (token !== loadToken) return; productOptions.value = Array.isArray(res.data?.records) ? res.data.records.map((item) => ({ id: Number(item.id), productName: String(item.productName || '') })) : [] } finally { if (token === loadToken) searchLoading.value = false } }

const prefillFromRoute = async () => {
  const productId = parsePositiveId(route.query.productId)
  const shopId = parsePositiveId(route.query.shopId)
  const platform = routeQueryText(route.query.platform)
  const productName = routeQueryText(route.query.productName)

  if (!productId) return false

  if (platform) {
    taskConfig.platform = platform
  } else if (shopId) {
    const matchedShop = shopStore.shops.find((shop) => Number(shop.id) === shopId)
    taskConfig.platform = matchedShop?.platform || ''
  }

  if (!taskConfig.platform) {
    ElMessage.warning('未找到商品所属平台，请手动选择平台后继续定价')
    activeStep.value = 0
    return true
  }

  productOptions.value = []

  if (shopId && availableShops.value.some((shop) => Number(shop.id) === shopId)) {
    taskConfig.shopId = shopId
  } else if (availableShops.value.length === 1) {
    taskConfig.shopId = availableShops.value[0].id
  } else {
    ElMessage.info('请选择商品所属店铺后继续定价')
    activeStep.value = 0
    return true
  }

  await loadProducts(productName)
  let matchedProduct = productOptions.value.find((item) => Number(item.id) === productId)

  if (!matchedProduct && productName) {
    await loadProducts('')
    matchedProduct = productOptions.value.find((item) => Number(item.id) === productId)
  }

  if (matchedProduct) {
    taskConfig.productId = productId
  } else {
    ElMessage.warning('未在当前店铺下找到该商品，请在商品下拉中手动搜索')
  }

  activeStep.value = 0
  return true
}

const syncRoutePrefill = async () => {
  if (route.path !== '/lab' || !parsePositiveId(route.query.productId)) {
    return false
  }

  const token = ++routePrefillToken
  const loaded = await shopStore.fetchShops()
  if (token !== routePrefillToken || !loaded) {
    return false
  }

  return prefillFromRoute()
}

const applySnapshotDetail = (detail?: PricingTaskSnapshot['detail'] | null) => { if (!detail) return; state.taskStatus = (detail.taskStatus || 'RUNNING') as PricingTaskStatus; state.finalPrice = detail.finalPrice != null ? Number(detail.finalPrice) : null; state.strategy = String(detail.strategy || ''); state.finalSummary = String(detail.finalSummary || '') }
// 快照是断线重连、页面刷新和跳过动画时的兜底来源，需要把日志重建成当前最新一轮智能体卡片。
const applySnapshotLogs = (logs: DecisionLogItem[]) => {
  clearRevealState()
  const cards = emptyCards()
  const snapshot = buildSnapshotAgentCards(logs)
  currentRunAttempt.value = snapshot.runAttempt
  snapshot.cards.forEach(({ code, stage, card }) => {
    if (stage === 'running') {
      if (!cards[code]) cards[code] = runningCard()
      return
    }
    cards[code] = stage === 'failed' ? failedCard(card) : normalizeCard(card)
  })
  state.cards = cards
}
const mergeSnapshotLogs = (logs: DecisionLogItem[]) => {
  const snapshot = buildSnapshotAgentCards(logs)
  if (snapshot.runAttempt !== null) {
    if (currentRunAttempt.value !== null && snapshot.runAttempt < currentRunAttempt.value) return
    if (currentRunAttempt.value !== null && snapshot.runAttempt > currentRunAttempt.value) {
      state.cards = emptyCards()
      clearAgentRevealProgress()
    }
    currentRunAttempt.value = snapshot.runAttempt
  }
  snapshot.cards.forEach(({ code, stage, card }) => {
    if (stage === 'running') {
      if (!state.cards[code]) state.cards[code] = runningCard()
      return
    }
    state.cards[code] = stage === 'failed' ? failedCard(card) : normalizeCard(card)
  })
}
const applySnapshotComparison = (comparison: DecisionComparisonItem[]) => { comparisonData.value = comparison; archiveReportSummary.value = comparisonData.value.find((row) => String(row.resultSummary || '').trim())?.resultSummary || '' }
const loadSnapshot = async (id: number, options: SnapshotLoadOptions = {}) => {
  const requestToken = ++snapshotLoadToken
  const res = await getPricingTaskSnapshot(id) as ApiResponse<PricingTaskSnapshot>
  if (requestToken !== snapshotLoadToken) return
  if (res.code !== 200 || !res.data) return
  applySnapshotDetail(res.data.detail)
  if (options.applyLogs !== false) {
    const logs = Array.isArray(res.data.logs) ? res.data.logs : []
    if (options.mergeLogs) mergeSnapshotLogs(logs)
    else applySnapshotLogs(logs)
  }
  if (requestToken === snapshotLoadToken) applySnapshotComparison(Array.isArray(res.data.comparison) ? res.data.comparison : [])
}
const skipRevealAnimation = async () => {
  liveRevealEnabled.value = false
  if (taskId.value) await loadSnapshot(taskId.value)
  ElMessage.info('已切换为静态进度快照')
}
const openExistingTaskArchive = async (id: number) => {
  ElMessage.info('该任务已经执行过，已为你打开决策档案详情')
  await router.push({ path: '/archive', query: { taskId: String(id) } })
}

// SSE 只负责推进状态，不直接假设本地 UI 完整；完成或失败后仍会回拉一次快照做最终对齐。
const finalizeTaskFromServer = async (id: number) => {
  liveRevealEnabled.value = false
  clearAgentRevealProgress()
  await loadSnapshot(id, { applyLogs: true, mergeLogs: false })
  stopRealtime()
}

const handleStream = async (payload: PricingTaskStreamMessage) => {
  if (payload.type === 'task_started') state.taskStatus = (payload.status || 'RUNNING') as PricingTaskStatus
  if (payload.type === 'agent_card') {
    const code = payload.agentCode as PricingAgentCode
    if (!syncStreamRunAttempt(payload.runAttempt)) return
    if (code in state.cards) {
      if (payload.stage === 'running') {
        if (!state.cards[code]) state.cards[code] = runningCard()
      } else {
        queueStreamCard(code, payload.card, payload.stage === 'failed' ? 'failed' : 'completed')
      }
    }
  }
  if (payload.type === 'task_completed') {
    state.taskStatus = (payload.status || 'COMPLETED') as PricingTaskStatus
    if (payload.result) {
      state.finalPrice = numberOf(payload.result.finalPrice)
      state.strategy = String(payload.result.strategy || state.strategy || '')
      state.finalSummary = String(payload.result.summary || state.finalSummary || '')
    }
    await finalizeTaskFromServer(payload.taskId)
    ElMessage[state.taskStatus === 'MANUAL_REVIEW' ? 'warning' : 'success'](state.taskStatus === 'MANUAL_REVIEW' ? '任务已完成，当前结果需要人工审核' : '智能决策已完成，可以查看结果报告')
  }
  if (payload.type === 'task_failed') {
    state.taskStatus = (payload.status || 'FAILED') as PricingTaskStatus
    state.errorMessage = sanitizeErrorMessage(payload.message, state.taskStatus === 'CANCELLED' ? '任务已取消' : '任务执行失败')
    await finalizeTaskFromServer(payload.taskId)
    ElMessage[state.taskStatus === 'CANCELLED' || state.taskStatus === 'MANUAL_REVIEW' ? 'warning' : 'error'](state.errorMessage)
  }
}

// 轮询是 SSE 的补偿通道：当流式消息丢失、页面后台挂起或网络抖动时，仍能逐步追上最新状态。
const startPolling = () => {
  if (pollTimer || !taskId.value) return
  pollTimer = setInterval(async () => {
    if (!taskId.value) return
    if (!isRunning(state.taskStatus)) {
      stopRealtime()
      return
    }
    await loadSnapshot(taskId.value, {
      applyLogs: true,
      mergeLogs: liveRevealEnabled.value || hasRevealInProgress()
    })
    if (isTerminal(state.taskStatus)) {
      if (liveRevealEnabled.value || hasRevealInProgress()) stopPolling()
      else stopRealtime()
    }
  }, 2000)
}
// 这里手动解析 event-stream 数据块，把后端按 data: 推送的 JSON 消息逐条交给 handleStream。
const startStream = async (id: number) => {
  stopRealtime()
  const controller = new AbortController()
  aborter = controller
  try {
    const response = await fetch(getPricingTaskStreamUrl(id), { method: 'GET', headers: { Accept: 'text/event-stream', Authorization: `Bearer ${getAuthToken()}` }, credentials: 'include', signal: controller.signal })
    if (!response.ok || !response.body) throw new Error('stream failed')
    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const chunks = buffer.split('\n\n')
      buffer = chunks.pop() || ''
      for (const chunk of chunks) {
        const data = chunk.split('\n').filter((line) => line.startsWith('data:')).map((line) => line.slice(5).trim()).join('\n')
        if (!data) continue
        try { await handleStream(JSON.parse(data) as PricingTaskStreamMessage) } catch {}
      }
    }
  } catch {
    if (!controller.signal.aborted && taskId.value) {
      clearRevealState()
      await loadSnapshot(taskId.value)
    }
  } finally {
    if (aborter === controller) aborter = null
  }
}

// 启动任务时先做本地约束校验，再创建任务、加载首个快照，并同时拉起 SSE 与轮询两条同步链路。
const startTask = async () => {
  if (!taskConfig.platform) return ElMessage.warning('请选择平台')
  if (!taskConfig.shopId) return ElMessage.warning('请选择店铺')
  if (!taskConfig.productId) return ElMessage.warning('请选择一个商品')
  if (!taskConfig.strategyGoal) return ElMessage.warning('请选择策略目标')
  const constraintError = validatePricingConstraintForm(constraintForm)
  if (constraintError) return ElMessage.warning(constraintError)
  const constraints = serializePricingConstraints(constraintForm)
  starting.value = true
  try {
    resetState()
    state.taskStatus = 'QUEUED'
    const res = await createPricingTask({ productId: taskConfig.productId, constraints, strategyGoal: taskConfig.strategyGoal }) as ApiResponse<number>
    if (res.code !== 200 || !res.data) {
      state.taskStatus = 'FAILED'
      state.errorMessage = sanitizeErrorMessage(res.message, '启动任务失败')
      return ElMessage.error(state.errorMessage)
    }
    taskId.value = Number(res.data)
    await loadSnapshot(taskId.value, { applyLogs: false })
    if (isArchivedTaskStatus(state.taskStatus)) {
      await openExistingTaskArchive(taskId.value)
      return
    }
    liveRevealEnabled.value = true
    activeStep.value = 1
    void startStream(taskId.value)
    startPolling()
    ElMessage.success('任务已启动，进入智能决策阶段')
  } catch {
    state.taskStatus = 'FAILED'
    state.errorMessage = '启动任务失败'
    ElMessage.error(state.errorMessage)
  } finally {
    starting.value = false
  }
}
const cancelTask = async () => { if (!taskId.value || !canCancelTask.value) return; try { await ElMessageBox.confirm('确认取消当前任务吗？', '取消任务', { type: 'warning', confirmButtonText: '确认取消', cancelButtonText: '继续执行' }); await loadSnapshot(taskId.value); if (!['QUEUED', 'RUNNING', 'RETRYING'].includes(state.taskStatus)) return ElMessage.warning(`当前任务状态为 ${statusLabel.value}，不支持取消`); const res = await cancelPricingTask(taskId.value); if (res.code !== 200) return ElMessage.error(sanitizeErrorMessage(res.message, '取消任务失败')); stopRealtime(); state.taskStatus = 'CANCELLED'; state.errorMessage = '任务已取消'; await loadSnapshot(taskId.value); ElMessage.warning('任务已取消') } catch (error) { if (error !== 'cancel') ElMessage.error('取消任务失败') } }
const refreshSnapshot = async () => {
  if (!taskId.value) return
  const wasRevealEnabled = liveRevealEnabled.value
  clearRevealState()
  await loadSnapshot(taskId.value)
  liveRevealEnabled.value = shouldKeepRevealEnabledAfterRefresh(state.taskStatus, wasRevealEnabled)
  if (isRunning(state.taskStatus) && !aborter) void startStream(taskId.value)
  if (isRunning(state.taskStatus)) startPolling()
  ElMessage.success(`已刷新快照，当前已完成 ${completedCardCount.value}/4 条分析结果`)
}
const resetTask = () => { resetState(); activeStep.value = 0 }
const applyPrice = async (row: DecisionComparisonItem) => { const id = Number(row.resultId || 0); if (!id) return ElMessage.error('未找到可应用的结果记录'); try { await ElMessageBox.confirm(`确认将商品“${String(row.productTitle || '-')}”的售价更新为 ${currency(row.suggestedPrice)} 吗？`, '应用价格建议', { type: 'warning', confirmButtonText: '确认应用', cancelButtonText: '取消' }); applyingIds.value.push(id); const res = await applyDecision(id); if (res.code !== 200) return ElMessage.error(sanitizeErrorMessage(res.message, '应用失败')); ElMessage.success('价格建议已应用'); if (taskId.value) await loadSnapshot(taskId.value) } catch (error) { if (error !== 'cancel') ElMessage.error('应用失败') } finally { applyingIds.value = applyingIds.value.filter((item) => item !== id) } }

const syncLlmConfig = async () => {
  try {
    const response = await getLlmConfig()
    hasLlmConfig.value = hasConfiguredLlmApiKey(response)
  } catch {
    hasLlmConfig.value = false
  } finally {
    hasSyncedLlmConfigOnce.value = true
  }
}

onMounted(async () => {
  void syncLlmConfig()

  const hasPrefill = await syncRoutePrefill()
  const loaded = hasPrefill ? true : await shopStore.fetchShops()

  if (!hasPrefill && loaded && platformOptions.value.length === 1) {
    taskConfig.platform = platformOptions.value[0]
    await onPlatformChange()
  }
})
onActivated(() => {
  if (hasSyncedLlmConfigOnce.value) {
    void syncLlmConfig()
  }
  void syncRoutePrefill()
})
watch(
  () => [
    route.path,
    route.query.productId,
    route.query.shopId,
    route.query.platform,
    route.query.productName
  ],
  () => {
    void syncRoutePrefill()
  }
)
onBeforeUnmount(() => { stopRealtime(); clearRevealState() })
</script>

<style scoped>
.llm-alert{margin-bottom:14px}
.alert-link{color:#409eff;text-decoration:underline;margin-left:4px}
.pricing-page{--pricing-accent:#2563eb;--pricing-accent-soft:rgba(37,99,235,.08);--pricing-accent-border:rgba(147,197,253,.72);--pricing-border:rgba(15,23,42,.08);display:grid;gap:14px}
.panel-card{padding:16px 18px;border-radius:14px;background:linear-gradient(180deg,rgba(255,255,255,.98),#fff);border:1px solid var(--pricing-border);box-shadow:0 8px 24px rgba(15,23,42,.05)}
.section-head{display:flex;justify-content:space-between;gap:14px;margin-bottom:14px}
.section-head h2{margin:0 0 4px;font-size:24px;color:#172033;line-height:1.2}
.section-head p{margin:0;color:#6b7280;font-size:14px;line-height:1.7}
.config-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0 14px}
.full-span{grid-column:1/-1}
.toolbar{display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap}
.workflow-card{padding-block:14px 16px}
.workflow-head{margin-bottom:10px}
.workflow-copy{display:grid;gap:4px}
.workflow-copy h2{font-size:22px}
.workflow-copy p{max-width:520px}
.workflow-card :deep(.el-steps){padding-top:2px}
.workflow-card :deep(.el-step__main){padding-top:6px}
.workflow-card :deep(.el-step__title){font-size:15px;font-weight:700}
.workflow-card :deep(.el-step__icon){width:30px;height:30px}
.workflow-card :deep(.el-step__line){top:15px}
.constraint-panel{width:100%;display:grid;gap:14px;padding:14px 16px;border:1px solid #e2e8f0;border-radius:8px;background:#f8fafc}
.constraint-intro{display:flex;justify-content:space-between;align-items:center;gap:12px;color:#64748b;font-size:14px;line-height:1.7}
.constraint-intro strong{font-size:15px;color:#172033}
.constraint-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.constraint-field{min-width:0;padding:12px;border:1px solid #e2e8f0;border-radius:8px;background:#fff}
.constraint-field{display:grid;gap:8px}
.constraint-label{display:block;font-size:14px;font-weight:700;color:#334155;line-height:1.45}
.constraint-control{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:8px}
.constraint-control :deep(.el-input-number){width:100%}
.constraint-unit{font-size:14px;font-weight:700;color:#64748b}

/* ========== 智能体决策对话区 ========== */
.decision-chat-panel{background:#f8fafc;border-color:#e2e8f0;box-shadow:none}
.decision-chat-head{align-items:flex-start;padding-bottom:12px;margin-bottom:14px;border-bottom:1px solid #e2e8f0}
.decision-chat-title{display:grid;gap:4px;min-width:0}
.decision-chat-title h2{margin:0;font-size:22px;color:#0f172a}
.decision-chat-title p{margin:0;color:#64748b;font-size:14px;line-height:1.7}
.decision-chat-kicker{width:fit-content;font-size:13px;font-weight:700;color:#1f6feb;background:rgba(31,111,235,.09);border:1px solid rgba(31,111,235,.12);border-radius:8px;padding:3px 8px}
.decision-toolbar{align-items:center}

.decision-overview-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:14px}
.decision-overview-card{padding:14px 16px;border:1px solid #dbe5f0;border-radius:12px;background:linear-gradient(180deg,#fff,rgba(248,250,252,.92));display:grid;gap:8px;box-shadow:0 1px 2px rgba(15,23,42,.04)}
.decision-overview-label{font-size:13px;font-weight:700;color:#64748b;letter-spacing:.02em}
.decision-overview-card strong{font-size:22px;color:#0f172a;line-height:1.2;font-variant-numeric:tabular-nums}
.opinion-matrix-panel{display:grid;gap:10px;margin-bottom:14px;padding:14px;border:1px solid #dbe5f0;border-radius:12px;background:#fff}
.opinion-matrix-head h3{margin:0 0 4px;font-size:17px;color:#0f172a}
.opinion-matrix-head p{margin:0;color:#64748b;font-size:13px;line-height:1.6}
.opinion-grid{display:grid;grid-template-columns:minmax(150px,1.2fr) minmax(92px,.8fr) minmax(110px,.9fr) minmax(220px,1.8fr) minmax(92px,.8fr);gap:12px;align-items:start}
.opinion-grid-head{padding:0 4px;color:#64748b;font-size:12px;font-weight:700}
.opinion-grid-row{padding:12px 14px;border:1px solid #e2e8f0;border-radius:10px;background:#f8fafc}
.opinion-grid-row.is-running{border-color:rgba(31,111,235,.24);background:#f8fbff}
.opinion-grid-row.is-failed{border-color:#fecaca;background:#fff5f5}
.opinion-seat{display:grid;gap:4px;min-width:0}
.opinion-seat strong{font-size:14px;color:#0f172a;line-height:1.4}
.opinion-seat span{font-size:12px;color:#64748b;line-height:1.5}
.opinion-cell{display:block;font-size:13px;color:#334155;line-height:1.6;overflow-wrap:anywhere}
.opinion-price-cell{font-weight:700;color:#1d4ed8;font-variant-numeric:tabular-nums}
.opinion-evidence-cell{color:#475569}
.matrix-state-chip{display:inline-flex;align-items:center;justify-content:center;min-height:28px;padding:0 10px;border-radius:999px;border:1px solid #dbe5f0;background:#fff;color:#475569;font-size:12px;font-weight:700}
.matrix-state-chip.is-running{border-color:#bfdbfe;background:#eff6ff;color:#1d4ed8}
.matrix-state-chip.is-completed{border-color:#bbf7d0;background:#f0fdf4;color:#15803d}
.matrix-state-chip.is-failed{border-color:#fecaca;background:#fff1f2;color:#b42318}
.decision-lane-stack{display:grid;gap:14px}
.decision-lane{display:grid;gap:12px;padding:14px;border:1px solid #dbe5f0;border-radius:12px;background:rgba(255,255,255,.78)}
.decision-lane-head h3{margin:0 0 4px;font-size:18px;color:#0f172a}
.decision-lane-head p{margin:0;color:#64748b;font-size:13px;line-height:1.7}
.decision-lane-grid{display:grid;gap:14px}
.parallel-analysis-grid{grid-template-columns:1fr}
.manager-arbitration-grid{grid-template-columns:1fr}
.agent-box{--agent-color:#1f6feb;display:grid;grid-template-columns:34px minmax(0,1fr);gap:12px;align-items:start;animation:agent-enter .26s ease-out both}
.agent-message{min-width:0;padding:16px 18px;border:1px solid #e2e8f0;border-radius:8px;background:#fff;box-shadow:0 1px 2px rgba(15,23,42,.04)}
.agent-box.is-streaming .agent-message{border-color:rgba(31,111,235,.22)}
.agent-avatar{width:34px;height:34px;border-radius:8px;background:#eff6ff;color:#1d4ed8;border:1px solid #dbeafe;display:grid;place-items:center;font-size:14px;font-weight:700;line-height:1;flex-shrink:0}

.agent-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:12px}
.agent-identity{display:flex;align-items:flex-start;gap:12px;min-width:0}
.agent-title{display:flex;flex-direction:column;gap:4px;min-width:0}
.agent-title h3{margin:0;font-size:16px;font-weight:700;color:#0f172a;letter-spacing:0}
.agent-role{display:inline-block;width:fit-content;font-size:13px;font-weight:600;color:#64748b;background:#f8fafc;border:1px solid #e2e8f0;padding:2px 8px;border-radius:8px;line-height:1.5}

.agent-box h4{margin:14px 0 8px;font-size:14px;font-weight:700;color:#334155;letter-spacing:0}
.agent-section-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:14px 0 8px}
.agent-section-head h4{margin:0}
.agent-section-toggle{flex-shrink:0;font-weight:600}
.thinking{white-space:pre-wrap;line-height:1.8;color:#475569;font-size:15px;margin:0}

.evidence-list,.suggestion-list{margin:0;padding:0;list-style:none;display:grid;gap:8px}
.evidence-list li,.suggestion-list li{padding:9px 11px;background:#f8fafc;border:1px solid #edf2f7;border-radius:8px;line-height:1.7;color:#334155;font-size:15px}

.result-strip{margin:6px 0 10px;padding:12px 14px;border-radius:8px;background:#f8fafc;border:1px solid #dbeafe;display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.price-label{font-size:14px;color:#64748b;font-weight:600}
.price-value{font-size:26px;font-weight:800;color:#1f6feb;letter-spacing:0;font-variant-numeric:tabular-nums;line-height:1}
.price-unit{font-size:17px;font-weight:600;opacity:.7;margin-right:3px}
.disagreement-and-arbitration{display:grid;gap:14px;margin-top:14px;padding:16px;border:1px solid #cfe0f7;border-radius:8px;background:linear-gradient(180deg,#f3f8ff 0%,#fff 100%)}
.disagreement-and-arbitration,.disagreement-and-arbitration *{box-sizing:border-box}
.arbitration-head,.consensus-meter,.arbitration-summary-grid,.arbitration-detail-grid,.arbitration-decision-strip,.arbitration-panel,.arbitration-summary-item,.decision-chip{min-width:0;max-width:100%}
.arbitration-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}
.arbitration-head h4{margin:6px 0 0;font-size:18px;color:#0f172a}
.arbitration-kicker{width:fit-content;padding:3px 8px;border-radius:8px;background:#dbeafe;color:#1d4ed8;font-size:12px;font-weight:700}
.consensus-meter{min-width:180px;display:grid;gap:7px;padding:10px 12px;border:1px solid #dbeafe;border-radius:8px;background:#fff}
.consensus-meter-copy{display:flex;justify-content:space-between;gap:12px;align-items:baseline;color:#64748b;font-size:12px;font-weight:700}
.consensus-meter-copy strong{color:#1d4ed8;font-size:18px;line-height:1}
.consensus-track{height:7px;border-radius:999px;background:#dbeafe;overflow:hidden}
.consensus-track span{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#60a5fa,#2563eb)}
.arbitration-summary-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.arbitration-summary-item{display:grid;gap:6px;padding:12px 14px;border-left:3px solid #2563eb;background:#fff;border-radius:8px;box-shadow:0 1px 2px rgba(15,23,42,.04)}
.arbitration-summary-item span,.decision-chip span{font-size:12px;font-weight:700;color:#64748b}
.arbitration-summary-item p{margin:0;color:#1e293b;font-size:15px;line-height:1.75}
.arbitration-summary-item p,.arbitration-muted,.arbitration-list li span:last-child,.decision-chip strong{overflow-wrap:anywhere;word-break:break-word}
.arbitration-detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.arbitration-panel{display:grid;gap:10px;align-content:start;padding:12px;border:1px solid #dbe5f0;border-radius:8px;background:#fff}
.arbitration-panel-head{display:flex;align-items:center;gap:8px}
.arbitration-panel-head h5{margin:0;color:#0f172a;font-size:15px}
.arbitration-dot{width:9px;height:9px;border-radius:999px;box-shadow:0 0 0 4px rgba(37,99,235,.1)}
.disagreement-dot{background:#f97316;box-shadow:0 0 0 4px rgba(249,115,22,.12)}
.decision-dot{background:#10b981;box-shadow:0 0 0 4px rgba(16,185,129,.12)}
.arbitration-muted{margin:0;padding:10px 12px;border-radius:8px;background:#f8fafc;color:#334155;line-height:1.7;font-size:14px}
.opinion-group{display:grid;gap:8px}
.opinion-label{width:fit-content;padding:2px 8px;border-radius:8px;font-size:12px;font-weight:700}
.accepted-label{background:#dcfce7;color:#047857}
.rejected-label{background:#fee2e2;color:#b42318}
.arbitration-list{margin:0;padding:0;list-style:none;display:grid;gap:8px}
.arbitration-list li{display:grid;grid-template-columns:22px minmax(0,1fr);gap:8px;align-items:start;padding:9px 10px;border:1px solid #edf2f7;border-radius:8px;background:#f8fafc;line-height:1.65;color:#334155;font-size:14px}
.arbitration-index{width:22px;height:22px;border-radius:7px;display:grid;place-items:center;background:#e0edff;color:#1d4ed8;font-size:12px;font-weight:800;line-height:1}
.arbitration-decision-strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;padding:10px;border:1px solid #bfdbfe;border-radius:8px;background:#eff6ff}
.decision-chip{display:grid;gap:4px;padding:10px 12px;border-radius:8px;background:#fff}
.decision-chip strong{color:#0f172a;font-size:15px;line-height:1.35}
.decision-chip-price strong{font-size:20px;color:#1d4ed8;font-variant-numeric:tabular-nums}

.failed-card{display:grid;gap:8px;padding:12px 14px;border-radius:8px;border:1px solid #fecaca;background:#fef2f2}
.failed-card-title{font-size:14px;font-weight:700;color:#b42318}
.failed-card-message{margin:0;line-height:1.7;color:#7a271a}
.waiting{min-height:104px;display:grid;place-items:center;color:#94a3b8}
.running-pulse{display:flex;align-items:center;justify-content:center;gap:10px;color:#1f6feb;font-size:14px;font-weight:600}
.pulse-dot{width:8px;height:8px;border-radius:50%;background:#1f6feb;animation:pulse 1.2s ease-in-out infinite}

.fade-in-item{opacity:0;animation:fadeSlideIn .38s cubic-bezier(.16,1,.3,1) forwards;animation-delay:calc(var(--i, 0) * 60ms)}

@keyframes agent-enter{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
@keyframes pulse{0%,100%{transform:scale(1);opacity:1}50%{transform:scale(1.6);opacity:.4}}
@keyframes fadeSlideIn{from{opacity:0;transform:translateX(-6px)}to{opacity:1;transform:translateX(0)}}
@keyframes typing-dot{0%,80%,100%{opacity:.35;transform:translateY(0)}40%{opacity:1;transform:translateY(-4px)}}

/* ========== 结果报告区 ========== */
.report-page,.metric-grid{display:grid;gap:12px}
.metric-grid{grid-template-columns:repeat(4,minmax(0,1fr))}
.metric-card{position:relative;padding:18px 18px 16px;border-radius:14px;background:#fff;border:1px solid rgba(15,23,42,.06);box-shadow:0 1px 2px rgba(15,23,42,.04),0 8px 22px rgba(15,23,42,.05);display:grid;gap:8px;transition:box-shadow .25s ease,transform .25s ease,border-color .25s ease}
.metric-card:hover{transform:translateY(-2px);box-shadow:0 2px 4px rgba(15,23,42,.06),0 14px 30px rgba(15,23,42,.08)}
.metric-card span{font-size:14px;color:#64748b;font-weight:600;letter-spacing:0}
.metric-card strong{font-size:24px;color:#0f172a;font-weight:700;letter-spacing:-.02em;font-variant-numeric:tabular-nums;line-height:1.1}
.metric-card-primary,.metric-card-accent{border-color:var(--pricing-accent-border);background:linear-gradient(180deg,rgba(239,246,255,.95),rgba(255,255,255,.98))}
.metric-card-primary strong{font-size:31px;color:#1d4ed8}
.metric-card-secondary strong{font-size:24px}
.metric-card-accent strong{font-size:29px}
.metric-card-primary::before,.metric-card-accent::before{content:'';position:absolute;inset:0 0 auto 0;height:3px;border-radius:14px 14px 0 0;background:linear-gradient(90deg,#60a5fa,#2563eb)}
.report-panel{padding-top:18px}
.report-head{align-items:flex-start;margin-bottom:12px}
.report-copy{display:grid;gap:8px;max-width:min(900px,100%)}
.report-copy h2{margin:0;font-size:26px;line-height:1.2}
.report-copy p{margin:0;color:#516074;font-size:15px;line-height:1.8}
.report-toolbar{align-items:flex-start}
.report-toolbar :deep(.el-button){min-height:36px;font-size:14px}
.report-toolbar :deep(.el-button--primary){box-shadow:0 8px 18px rgba(37,99,235,.18)}
.report-table :deep(.el-table__header th){padding-block:11px;background:#f8fbff;color:#334155;font-weight:700;font-size:14px}
.report-table :deep(.el-table__cell){padding-block:10px;font-size:15px}
.report-table :deep(.el-table__body tr:hover > td){background:#f8fbff}
.report-table :deep(.el-tag){border-radius:999px;padding-inline:10px;font-size:14px;font-weight:700}
.report-table :deep(.el-button.is-link){font-size:15px;font-weight:700}
.report-table :deep(.cell){line-height:1.5}
@media (max-width:1100px){.config-grid,.metric-grid,.constraint-grid,.decision-overview-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.opinion-grid{grid-template-columns:minmax(120px,1fr) minmax(80px,.7fr) minmax(100px,.8fr) minmax(180px,1.5fr) minmax(88px,.7fr)}}
@media (max-width:760px){.config-grid,.metric-grid,.constraint-grid,.decision-overview-grid,.parallel-analysis-grid,.arbitration-summary-grid,.arbitration-detail-grid,.arbitration-decision-strip{grid-template-columns:1fr}.opinion-grid,.opinion-grid-head{grid-template-columns:1fr}.opinion-grid-head{display:none}.constraint-intro,.section-head,.agent-head,.arbitration-head{flex-direction:column;align-items:flex-start}.toolbar{justify-content:flex-start}.workflow-copy p,.report-copy{max-width:none}.agent-box{grid-template-columns:30px minmax(0,1fr);gap:10px}.agent-avatar{width:30px;height:30px}.result-strip{flex-direction:column;align-items:flex-start;gap:4px}.consensus-meter{width:100%;min-width:0}.opinion-grid-row{gap:8px}.matrix-state-chip{width:fit-content}}
@media (prefers-reduced-motion:reduce){.agent-box,.metric-card,.fade-in-item,.pulse-dot,.agent-stream-pulse span{animation:none!important;transition:none!important}.metric-card:hover{transform:none}}
</style>

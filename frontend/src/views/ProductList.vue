<template>
  <div class="page-shell">
    <section class="panel-card table-card product-card">
      <div class="section-head">
        <div class="section-title">
          <h2>商品数据管理</h2>
          <p>支持按平台筛选，并在详情中完整查看商品日指标、SKU 与流量推广数据。</p>
        </div>
        <div class="toolbar-actions">
          <el-button type="success" @click="openAddDialog">新增商品</el-button>
          <el-button type="primary" plain :disabled="selectedIds.length === 0" @click="openBatchPricingDialog">
            批量定价
          </el-button>
          <el-button type="danger" :disabled="selectedIds.length === 0" @click="handleBatchDelete">
            批量删除
          </el-button>
        </div>
      </div>

      <div class="search-toolbar">
        <el-input
          v-model="filters.keyword"
          clearable
          placeholder="搜索商品名称、类目、商品ID或平台商品ID"
          @keyup.enter="applyFilters"
        />
        <el-select v-model="filters.platform" class="toolbar-select" placeholder="平台筛选">
          <el-option label="全部平台" value="ALL" />
          <el-option v-for="platform in platformOptions" :key="platform" :label="platform" :value="platform" />
        </el-select>
        <el-select v-model="filters.status" class="toolbar-select" placeholder="状态筛选">
          <el-option label="全部状态" value="ALL" />
          <el-option label="出售中" value="出售中" />
          <el-option label="下架" value="下架" />
        </el-select>
        <el-button type="primary" @click="applyFilters">搜索</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>

      <div class="selected-bar" v-if="selectedIds.length > 0">
        <el-tag type="success">已选择 {{ selectedIds.length }} 个商品</el-tag>
        <div class="selected-bar-actions">
          <el-button link type="danger" @click="clearSelection">清空选择</el-button>
        </div>
      </div>

      <div v-if="!isMobile" class="table-wrap">
        <el-table
          ref="tableRef"
          :data="displayData"
          row-key="id"
          border
          stripe
          v-loading="loading"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="46" :reserve-selection="true" />

          <el-table-column label="商品名称" min-width="260" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="product-cell">
                <strong class="product-name">{{ row.productName || '-' }}</strong>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="类别" width="120" show-overflow-tooltip>
            <template #default="{ row }">{{ row.categoryName || '-' }}</template>
          </el-table-column>

          <el-table-column label="商品平台" width="100">
            <template #default="{ row }">{{ row.platform || '-' }}</template>
          </el-table-column>

          <el-table-column label="价格" width="150">
            <template #default="{ row }">
              <div class="cell-stack">
                <strong>{{ formatCurrency(row.salePrice) }}</strong>
                <span>成本 {{ formatCurrency(row.costPrice) }}</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="statusTagType(row.status)">{{ formatStatusText(row.status) }}</el-tag>
            </template>
          </el-table-column>

          <el-table-column label="库存" width="120">
            <template #default="{ row }">
              <span :class="['stock-text', { low: Number(row.stock || 0) <= 20 }]">
                {{ formatCount(row.stock) }}
              </span>
            </template>
          </el-table-column>

          <el-table-column v-if="!isVeryNarrowDesktop" label="经营表现" width="130">
            <template #default="{ row }">
              <div class="cell-stack">
                <strong>月销量 {{ Number(row.monthlySales || 0) }}</strong>
                <span>转化 {{ formatPercent(row.conversionRate) }}</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="210" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDetailDrawer(row)">详情</el-button>
              <el-button link type="success" @click="openTrendDrawer(row)">趋势</el-button>
              <el-button link type="warning" @click="goPricing(row)">定价</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-else class="mobile-list" v-loading="loading">
        <el-empty v-if="displayData.length === 0" description="当前筛选条件下暂无商品" />
        <article v-for="row in displayData" :key="row.id" class="mobile-card">
          <div class="mobile-head">
            <div class="mobile-title">
              <strong>{{ row.productName || '-' }}</strong>
            </div>
            <el-tag :type="statusTagType(row.status)">{{ formatStatusText(row.status) }}</el-tag>
          </div>

          <div class="mobile-meta">
            <span>平台：{{ row.platform || '-' }}</span>
            <span>类目：{{ row.categoryName || '未分类' }}</span>
          </div>

          <div class="mobile-grid">
            <div class="mobile-item">
              <span>售价</span>
              <strong>{{ formatCurrency(row.salePrice) }}</strong>
            </div>
            <div class="mobile-item">
              <span>成本</span>
              <strong>{{ formatCurrency(row.costPrice) }}</strong>
            </div>
            <div class="mobile-item">
              <span>库存</span>
              <strong :class="{ low: Number(row.stock || 0) <= 20 }">{{ Number(row.stock || 0) }}</strong>
            </div>
            <div class="mobile-item">
              <span>月销量</span>
              <strong>{{ Number(row.monthlySales || 0) }}</strong>
            </div>
          </div>

          <div class="mobile-actions">
            <el-button size="small" :type="isSelected(row.id) ? 'primary' : 'default'" @click="toggleRowSelection(row)">
              {{ isSelected(row.id) ? '取消选择' : '选择' }}
            </el-button>
            <el-button size="small" @click="openDetailDrawer(row)">详情</el-button>
            <el-button size="small" type="success" plain @click="openTrendDrawer(row)">趋势</el-button>
            <el-button size="small" type="warning" plain @click="goPricing(row)">定价</el-button>
          </div>
        </article>
      </div>

      <div class="table-footer">
        <el-pagination
          v-model:current-page="queryParams.page"
          v-model:page-size="queryParams.size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSearch"
          @current-change="handleSearch"
        />
      </div>
    </section>

    <el-dialog
      v-model="dialogVisible"
      :title="isMobile ? '新增商品' : '新增商品（新库模型）'"
      width="560px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="96px" class="product-form">
        <div class="form-grid">
          <el-form-item label="平台商品ID" prop="externalProductId">
            <el-input v-model="form.externalProductId" clearable placeholder="可留空自动生成或输入平台商品ID" />
          </el-form-item>
          <el-form-item label="商品名称" prop="productName">
            <el-input v-model="form.productName" placeholder="请输入商品名称" />
          </el-form-item>
          <el-form-item label="类目名称" prop="categoryName">
            <el-input v-model="form.categoryName" placeholder="请输入类目名称" />
          </el-form-item>
          <el-form-item label="状态" prop="status">
            <el-select v-model="form.status" placeholder="请选择状态">
              <el-option label="出售中" value="出售中" />
              <el-option label="下架" value="下架" />
            </el-select>
          </el-form-item>
          <el-form-item label="成本价" prop="costPrice">
            <el-input-number v-model="form.costPrice" :min="0" :precision="2" :step="0.1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="当前售价" prop="salePrice">
            <el-input-number v-model="form.salePrice" :min="0" :precision="2" :step="0.1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="库存" prop="stock">
            <el-input-number v-model="form.stock" :min="0" :precision="0" :step="1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="近30天销量" prop="monthlySales">
            <el-input-number v-model="form.monthlySales" :min="0" :precision="0" :step="1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="平均转化率" prop="conversionRate">
            <el-input-number
              v-model="form.conversionRate"
              :min="0"
              :max="1"
              :precision="4"
              :step="0.0001"
              style="width: 100%"
            />
          </el-form-item>
        </div>
        <div class="mini-note">平台商品ID可留空自动生成。近30天销量与转化率会用于初始化 `product_daily_metric`。</div>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitProduct">保存商品</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="batchPricingVisible"
      title="批量定价"
      width="760px"
    >
      <div class="batch-pricing-shell">
        <div class="batch-pricing-intro">
          <strong>已选择 {{ selectedIds.length }} 个商品</strong>
          <span>统一配置策略目标和硬约束，系统会为每个商品创建或复用现有定价任务。</span>
        </div>

        <el-form label-position="top" class="batch-pricing-form">
          <el-form-item label="策略目标">
            <el-radio-group v-model="batchPricingForm.strategyGoal">
              <el-radio v-for="goal in goalOptions" :key="goal.label" :label="goal.label" border>{{ goal.name }}</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="约束条件">
            <div class="constraint-panel">
              <div class="constraint-intro">
                <strong>定价硬约束</strong>
                <span>未填写的售价区间和降价幅度不会参与限制。</span>
              </div>
              <div class="constraint-grid">
                <div class="constraint-field">
                  <span class="constraint-label">最低利润率</span>
                  <div class="constraint-control">
                    <el-input-number
                      v-model="batchConstraintForm.minProfitRatePercent"
                      :min="0.01"
                      :max="99.99"
                      :step="1"
                      :precision="2"
                      controls-position="right"
                    />
                    <span class="constraint-unit">%</span>
                  </div>
                </div>
                <div class="constraint-field">
                  <span class="constraint-label">最低售价</span>
                  <div class="constraint-control">
                    <el-input-number
                      v-model="batchConstraintForm.minPrice"
                      :min="0.01"
                      :step="1"
                      :precision="2"
                      controls-position="right"
                      placeholder="不限制"
                    />
                    <span class="constraint-unit">元</span>
                  </div>
                </div>
                <div class="constraint-field">
                  <span class="constraint-label">最高售价</span>
                  <div class="constraint-control">
                    <el-input-number
                      v-model="batchConstraintForm.maxPrice"
                      :min="0.01"
                      :step="1"
                      :precision="2"
                      controls-position="right"
                      placeholder="不限制"
                    />
                    <span class="constraint-unit">元</span>
                  </div>
                </div>
                <div class="constraint-field">
                  <span class="constraint-label">最大降价幅度</span>
                  <div class="constraint-control">
                    <el-input-number
                      v-model="batchConstraintForm.maxDiscountRatePercent"
                      :min="0.01"
                      :max="100"
                      :step="1"
                      :precision="2"
                      controls-position="right"
                      placeholder="不限制"
                    />
                    <span class="constraint-unit">%</span>
                  </div>
                </div>
              </div>
            </div>
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="batchPricingVisible = false">取消</el-button>
        <el-button type="primary" :loading="batchStarting" @click="submitBatchPricing">启动批量定价</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="detailVisible"
      :size="isMobile ? '100%' : '65%'"
      :destroy-on-close="false"
      title="商品数据明细"
    >
      <div v-if="currentProduct" class="detail-shell">
        <el-tabs v-model="detailTab">
          <el-tab-pane label="基础信息" name="base">
            <section class="base-overview">
              <div class="base-hero">
                <div class="base-hero-main">
                  <p class="base-hero-caption">商品名称</p>
                  <h3>{{ currentProduct.productName || '-' }}</h3>
                  <div class="base-tags">
                    <el-tag size="small" :type="statusTagType(currentProduct.status)">
                      {{ formatStatusText(currentProduct.status) }}
                    </el-tag>
                    <el-tag size="small" type="info">
                      平台 {{ currentProduct.platform || '-' }}
                    </el-tag>
                    <span class="base-category">{{ currentProduct.categoryName || '未分类' }}</span>
                  </div>
                </div>
                <div class="base-id-group">
                  <div class="base-id-item">
                    <span>商品ID</span>
                    <strong>{{ currentProduct.id }}</strong>
                  </div>
                  <div class="base-id-item">
                    <span>平台商品ID</span>
                    <strong>{{ currentProduct.externalProductId || '-' }}</strong>
                  </div>
                </div>
              </div>

              <div class="base-kpi-grid">
                <div class="base-kpi-item">
                  <span>当前售价</span>
                  <strong>{{ formatCurrency(currentProduct.salePrice) }}</strong>
                </div>
                <div class="base-kpi-item">
                  <span>成本价</span>
                  <strong>{{ formatCurrency(currentProduct.costPrice) }}</strong>
                </div>
                <div class="base-kpi-item">
                  <span>毛利空间</span>
                  <strong>{{ formatCurrency(calcGrossProfit(currentProduct.salePrice, currentProduct.costPrice)) }}</strong>
                </div>
                <div class="base-kpi-item">
                  <span>库存</span>
                  <strong>{{ formatCount(currentProduct.stock) }}</strong>
                </div>
                <div class="base-kpi-item">
                  <span>近30天销量</span>
                  <strong>{{ formatCount(currentProduct.monthlySales) }}</strong>
                </div>
                <div class="base-kpi-item">
                  <span>平均转化率</span>
                  <strong>{{ formatPercent(currentProduct.conversionRate) }}</strong>
                </div>
              </div>

            </section>
          </el-tab-pane>

          <el-tab-pane label="商品日指标" name="daily">
            <div class="detail-table-wrap" v-loading="detailLoading">
              <div v-if="dailyMetrics.length > 0" class="detail-kpi-grid">
                <div class="detail-kpi-item">
                  <span>统计天数</span>
                  <strong>{{ dailySummary.days }}</strong>
                </div>
                <div class="detail-kpi-item">
                  <span>累计访客</span>
                  <strong>{{ formatCount(dailySummary.totalVisitors) }}</strong>
                </div>
                <div class="detail-kpi-item">
                  <span>累计成交</span>
                  <strong>{{ formatCurrency(dailySummary.totalTurnover) }}</strong>
                </div>
                <div class="detail-kpi-item">
                  <span>平均转化率</span>
                  <strong>{{ formatPercent(dailySummary.avgConversionRate) }}</strong>
                </div>
              </div>
              <el-empty v-if="dailyMetrics.length === 0" description="暂无商品日指标数据" />
              <template v-else>
                <el-table :data="dailyMetrics" border stripe size="small">
                  <el-table-column label="日期" width="120">
                    <template #default="{ row }">{{ row.statDate || '-' }}</template>
                  </el-table-column>
                  <el-table-column label="流量与转化" min-width="280">
                    <template #default="{ row }">
                      <div class="metric-pairs">
                        <span><label>访客</label><strong>{{ formatCount(row.visitorCount) }}</strong></span>
                        <span><label>加购</label><strong>{{ formatCount(row.addCartCount) }}</strong></span>
                        <span><label>支付买家</label><strong>{{ formatCount(row.payBuyerCount) }}</strong></span>
                        <span><label>转化率</label><strong>{{ formatPercent(row.conversionRate) }}</strong></span>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column label="交易数据" min-width="240">
                    <template #default="{ row }">
                      <div class="metric-pairs">
                        <span><label>支付件数</label><strong>{{ formatCount(row.salesCount) }}</strong></span>
                        <span><label>成交金额</label><strong>{{ formatCurrency(row.turnover) }}</strong></span>
                        <span><label>退款金额</label><strong>{{ formatCurrency(row.refundAmount) }}</strong></span>
                      </div>
                    </template>
                  </el-table-column>
                </el-table>
                <div class="detail-pagination">
                  <el-pagination
                    v-model:current-page="dailyMetricPagination.page"
                    v-model:page-size="dailyMetricPagination.size"
                    :total="dailyMetricPagination.total"
                    :page-sizes="[10, 20, 50]"
                    layout="total, sizes, prev, pager, next"
                    @current-change="handleDailyMetricPageChange"
                    @size-change="handleDailyMetricSizeChange"
                  />
                </div>
              </template>
            </div>
          </el-tab-pane>

          <el-tab-pane label="商品SKU" name="sku">
            <div class="detail-table-wrap" v-loading="detailLoading">
              <div v-if="skus.length > 0" class="detail-kpi-grid">
                <div class="detail-kpi-item">
                  <span>SKU数量</span>
                  <strong>{{ skuSummary.count }}</strong>
                </div>
                <div class="detail-kpi-item">
                  <span>总库存</span>
                  <strong>{{ formatCount(skuSummary.totalStock) }}</strong>
                </div>
                <div class="detail-kpi-item">
                  <span>平均库存</span>
                  <strong>{{ formatCount(skuSummary.avgStock) }}</strong>
                </div>
                <div class="detail-kpi-item">
                  <span>平均售价</span>
                  <strong>{{ formatCurrency(skuSummary.avgSalePrice) }}</strong>
                </div>
              </div>
              <el-empty v-if="skus.length === 0" description="暂无 SKU 数据" />
              <el-table v-else :data="skus" border stripe size="small">
                <el-table-column label="SKU信息" min-width="260">
                  <template #default="{ row }">
                    <div class="cell-stack">
                      <strong>{{ row.skuName || '-' }}</strong>
                      <span>SKU ID {{ row.externalSkuId || '-' }}</span>
                      <span>{{ row.skuAttr || '无规格属性' }}</span>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="价格" min-width="160">
                  <template #default="{ row }">
                    <div class="cell-stack">
                      <strong>{{ formatCurrency(row.salePrice) }}</strong>
                      <span>成本 {{ formatCurrency(row.costPrice) }}</span>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="毛利空间" width="120">
                  <template #default="{ row }">{{ formatCurrency(calcGrossProfit(row.salePrice, row.costPrice)) }}</template>
                </el-table-column>
                <el-table-column label="库存数量" width="120">
                  <template #default="{ row }">
                    <strong :class="['sku-stock-value', { low: Number(row.stock || 0) <= 20 }]">
                      {{ formatCount(row.stock) }}
                    </strong>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-tab-pane>

          <el-tab-pane label="流量与推广日指标" name="traffic">
            <div class="detail-table-wrap" v-loading="detailLoading">
              <div v-if="trafficPromos.length > 0" class="detail-kpi-grid">
                <div class="detail-kpi-item">
                  <span>渠道来源数</span>
                  <strong>{{ trafficSummary.sourceCount }}</strong>
                </div>
                <div class="detail-kpi-item">
                  <span>累计花费</span>
                  <strong>{{ formatCurrency(trafficSummary.totalCost) }}</strong>
                </div>
                <div class="detail-kpi-item">
                  <span>累计成交</span>
                  <strong>{{ formatCurrency(trafficSummary.totalPay) }}</strong>
                </div>
                <div class="detail-kpi-item">
                  <span>平均ROI</span>
                  <strong>{{ trafficSummary.avgRoi.toFixed(2) }}</strong>
                </div>
              </div>
              <el-empty v-if="trafficPromos.length === 0" description="暂无流量与推广数据" />
              <el-table v-else :data="trafficPromos" border stripe size="small">
                <el-table-column label="日期" width="120">
                  <template #default="{ row }">{{ row.statDate || '-' }}</template>
                </el-table-column>
                <el-table-column label="来源" width="110" show-overflow-tooltip>
                  <template #default="{ row }">{{ row.trafficSource || '-' }}</template>
                </el-table-column>
                <el-table-column label="投放表现" min-width="260">
                  <template #default="{ row }">
                    <div class="metric-pairs">
                      <span><label>展现</label><strong>{{ formatCount(row.impressionCount) }}</strong></span>
                      <span><label>点击</label><strong>{{ formatCount(row.clickCount) }}</strong></span>
                      <span><label>访客</label><strong>{{ formatCount(row.visitorCount) }}</strong></span>
                      <span><label>点击率</label><strong>{{ formatPercent(calcRate(row.clickCount, row.impressionCount)) }}</strong></span>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="投放产出" min-width="240">
                  <template #default="{ row }">
                    <div class="metric-pairs">
                      <span><label>花费</label><strong>{{ formatCurrency(row.costAmount) }}</strong></span>
                      <span><label>成交</label><strong>{{ formatCurrency(row.payAmount) }}</strong></span>
                      <span><label>ROI</label><strong>{{ Number(row.roi || 0).toFixed(2) }}</strong></span>
                      <span><label>单次点击成本</label><strong>{{ formatCurrency(calcRate(row.costAmount, row.clickCount)) }}</strong></span>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </el-tab-pane>
        </el-tabs>

      </div>
    </el-drawer>

    <ProductTrendDrawer ref="trendDrawerRef" />
  </div>
</template>

<script setup lang="ts">
// 商品列表页：负责商品查询、筛选、趋势查看与基础维护操作。

import { computed, nextTick, reactive, ref, watch } from 'vue'
import { createPricingBatch } from '../api/pricingBatch'
import {
  addProductManual,
  batchDeleteProducts,
  getProductList,
  type ProductListVO,
} from '../api/product'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import ProductTrendDrawer from '../components/ProductTrendDrawer.vue'
import { useProductDetailDrawer, calcGrossProfit } from '../composables/product-list/useProductDetailDrawer'
import { useViewport } from '../composables/useViewport'
import { resolveRequestErrorMessage } from '../utils/error'
import { formatCount, formatCurrency as sharedFormatCurrency, formatPercent as sharedFormatPercent } from '../utils/formatters'
import { createDefaultPricingConstraintForm, serializePricingConstraints, validatePricingConstraintForm } from '../utils/pricingConstraints'
import { PRICING_GOAL_OPTIONS, type PricingGoal } from '../utils/pricingTaskOptions'
import { useRouter } from 'vue-router'

interface ProductFormModel {
  externalProductId: string
  productName: string
  categoryName: string
  costPrice: number
  salePrice: number
  stock: number
  monthlySales: number
  conversionRate: number
  status: string
}

const { width } = useViewport()
const router = useRouter()

const loading = ref(false)
const tableData = ref<ProductListVO[]>([])
const total = ref(0)
const selectedIds = ref<number[]>([])
const dialogVisible = ref(false)
const batchPricingVisible = ref(false)
const batchStarting = ref(false)
const formRef = ref<FormInstance>()
const tableRef = ref<any>(null)
const trendDrawerRef = ref<InstanceType<typeof ProductTrendDrawer>>()
let syncingTableSelection = false

const queryParams = reactive({
  page: 1,
  size: 10
})

const filters = reactive({
  keyword: '',
  status: 'ALL',
  platform: 'ALL'
})
const goalOptions = PRICING_GOAL_OPTIONS
const batchPricingForm = reactive({
  strategyGoal: undefined as PricingGoal | undefined
})
const batchConstraintForm = reactive(createDefaultPricingConstraintForm())

const createDefaultForm = (): ProductFormModel => ({
  externalProductId: '',
  productName: '',
  categoryName: '',
  costPrice: 0,
  salePrice: 0,
  stock: 0,
  monthlySales: 120,
  conversionRate: 0.04,
  status: '出售中'
})

const form = reactive(createDefaultForm())

const rules = {
  productName: [{ required: true, message: '请输入商品名称', trigger: 'blur' }],
  costPrice: [{ required: true, message: '请输入成本价', trigger: 'blur' }],
  salePrice: [{ required: true, message: '请输入当前售价', trigger: 'blur' }]
}

const isMobile = computed(() => width.value <= 768)
const isVeryNarrowDesktop = computed(() => width.value <= 1024)
const {
  currentProduct,
  dailyMetricPagination,
  dailyMetrics,
  dailySummary,
  detailLoading,
  detailTab,
  detailVisible,
  handleDailyMetricPageChange,
  handleDailyMetricSizeChange,
  openDetailDrawer,
  skuSummary,
  skus,
  trafficPromos,
  trafficSummary
} = useProductDetailDrawer()

const platformOptions = computed(() => {
  const defaults = ['淘宝', '天猫', '京东', '拼多多', '抖音']
  const values = new Set(defaults)
  tableData.value.forEach((row) => {
    if (row.platform) values.add(row.platform)
  })
  return Array.from(values)
})

const displayData = computed(() => tableData.value)

const formatCurrency = (value?: number | null) => sharedFormatCurrency(value)
const formatPercent = (value?: number | null) => sharedFormatPercent(value)
const formatStatusText = (status?: string) => status || '-'
const calcRate = (numerator?: number | null, denominator?: number | null) => {
  const den = Number(denominator || 0)
  if (den <= 0) return 0
  return Number(numerator || 0) / den
}

const statusTagType = (status?: string) => {
  if (status === '出售中') return 'success'
  if (status === '下架') return 'info'
  return 'warning'
}

const clearSelection = () => {
  selectedIds.value = []
  tableRef.value?.clearSelection?.()
}

const resetBatchPricingForm = () => {
  batchPricingForm.strategyGoal = undefined
  Object.assign(batchConstraintForm, createDefaultPricingConstraintForm())
}

const isSelected = (id: number) => selectedIds.value.includes(id)

const syncTableSelection = async () => {
  if (isMobile.value) return
  await nextTick()

  const table = tableRef.value
  if (!table) return

  const selectedSet = new Set(selectedIds.value)
  syncingTableSelection = true
  table.clearSelection()
  displayData.value.forEach((row) => {
    if (selectedSet.has(row.id)) {
      table.toggleRowSelection(row, true)
    }
  })
  await nextTick()
  syncingTableSelection = false
}

const toggleRowSelection = (row: ProductListVO) => {
  if (isSelected(row.id)) {
    selectedIds.value = selectedIds.value.filter((id) => id !== row.id)
    return
  }
  selectedIds.value = Array.from(new Set([...selectedIds.value, row.id]))
}

const goPricing = (row: ProductListVO) => {
  router.push({
    path: '/lab',
    query: {
      productId: String(row.id),
      platform: row.platform || '',
      shopId: row.shopId ? String(row.shopId) : '',
      productName: row.productName || ''
    }
  })
}

watch(
  [displayData, isMobile],
  () => {
    void syncTableSelection()
  },
  { deep: true }
)

const resetForm = () => {
  Object.assign(form, createDefaultForm())
}

const handleSearch = async () => {
  loading.value = true
  try {
    const res: any = await getProductList({
      page: queryParams.page,
      size: queryParams.size,
      keyword: filters.keyword.trim() || undefined,
      platform: filters.platform === 'ALL' ? undefined : filters.platform,
      status: filters.status === 'ALL' ? undefined : filters.status
    })
    if (res?.code === 200) {
      tableData.value = res.data.records || []
      total.value = res.data.total || 0
      await syncTableSelection()
      return
    }
    ElMessage.error(res?.message || '加载商品失败')
  } catch (error) {
    ElMessage.error(await resolveRequestErrorMessage(error, '加载商品失败'))
  } finally {
    loading.value = false
  }
}

const applyFilters = () => {
  queryParams.page = 1
  handleSearch()
}

const resetFilters = () => {
  filters.keyword = ''
  filters.platform = 'ALL'
  filters.status = 'ALL'
  queryParams.page = 1
  handleSearch()
}

const refreshList = () => {
  queryParams.page = 1
  handleSearch()
}

defineExpose({ refreshList })

const handleSelectionChange = (selection: ProductListVO[]) => {
  if (syncingTableSelection) return

  const selectedSet = new Set(selectedIds.value)
  const currentPageIds = displayData.value.map((item) => item.id)

  currentPageIds.forEach((id) => selectedSet.delete(id))
  selection.forEach((item) => selectedSet.add(item.id))

  selectedIds.value = Array.from(selectedSet)
}

const confirmBatchDelete = async () => {
  await ElMessageBox.confirm(
    '确定删除已选择的 ' + selectedIds.value.length + ' 个商品吗？此操作不可恢复。',
    '批量删除确认',
    {
      confirmButtonText: '确认删除',
      cancelButtonText: '取消',
      type: 'warning'
    }
  )
}

const handleBatchDelete = async () => {
  if (selectedIds.value.length === 0) {
    ElMessage.warning('请先选择要删除的商品')
    return
  }

  try {
    await confirmBatchDelete()
    loading.value = true
    const res: any = await batchDeleteProducts(selectedIds.value)
    if (res?.code === 200) {
      ElMessage.success('批量删除成功')
      clearSelection()
      refreshList()
      return
    }
    ElMessage.error(res?.message || '批量删除失败')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(await resolveRequestErrorMessage(error, '批量删除失败'))
    }
  } finally {
    loading.value = false
  }
}

const openBatchPricingDialog = () => {
  if (selectedIds.value.length === 0) {
    ElMessage.warning('请先选择要定价的商品')
    return
  }
  resetBatchPricingForm()
  batchPricingVisible.value = true
}

const submitBatchPricing = async () => {
  if (selectedIds.value.length === 0) {
    ElMessage.warning('请先选择要定价的商品')
    return
  }
  const constraintError = validatePricingConstraintForm(batchConstraintForm)
  if (constraintError) {
    ElMessage.warning(constraintError)
    return
  }
  if (!batchPricingForm.strategyGoal) {
    ElMessage.warning('请选择策略目标')
    return
  }

  batchStarting.value = true
  try {
    const constraints = serializePricingConstraints(batchConstraintForm)
    const res: any = await createPricingBatch({
      productIds: selectedIds.value,
      strategyGoal: batchPricingForm.strategyGoal,
      constraints
    })
    if (res?.code !== 200 || !res?.data?.batchId) {
      ElMessage.error(res?.message || '批量定价启动失败')
      return
    }
    batchPricingVisible.value = false
    clearSelection()
    if (Number(res.data.createFailedCount || 0) > 0) {
      ElMessage.warning(`批量定价已创建，${Number(res.data.createFailedCount)} 个商品创建失败`)
    } else {
      ElMessage.success('批量定价已启动')
    }
    await router.push(`/archive/batches/${Number(res.data.batchId)}`)
  } catch (error) {
    ElMessage.error(await resolveRequestErrorMessage(error, '批量定价启动失败'))
  } finally {
    batchStarting.value = false
  }
}

const openAddDialog = () => {
  resetForm()
  dialogVisible.value = true
}

const submitProduct = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    try {
      const res: any = await addProductManual(form)
      if (res?.code === 200) {
        ElMessage.success('商品新增成功')
        dialogVisible.value = false
        refreshList()
        return
      }
      ElMessage.error(res?.message || '商品新增失败')
    } catch (error) {
      ElMessage.error(await resolveRequestErrorMessage(error, '提交失败，请稍后重试'))
    }
  })
}

const openTrendDrawer = (row: ProductListVO) => {
  trendDrawerRef.value?.open(row)
}

handleSearch()
</script>


<style scoped>
.product-card {
  padding: 18px;
}

.search-toolbar {
  display: grid;
  grid-template-columns: minmax(320px, 1.35fr) repeat(2, 148px) 108px 108px;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.search-toolbar :deep(.el-input),
.search-toolbar :deep(.el-select),
.search-toolbar :deep(.el-button) {
  width: 100%;
}

.toolbar-select {
  width: 140px;
}

.selected-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(47, 161, 116, 0.16);
  background: rgba(47, 161, 116, 0.06);
}

.selected-bar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.batch-pricing-shell {
  display: grid;
  gap: 16px;
}

.batch-pricing-intro {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(31, 46, 77, 0.06);
  background: var(--surface-2);
}

.batch-pricing-intro strong {
  color: var(--text-1);
}

.batch-pricing-intro span {
  color: var(--text-3);
  line-height: 1.7;
}

.batch-pricing-form {
  display: grid;
  gap: 8px;
}

.constraint-panel {
  width: 100%;
  display: grid;
  gap: 14px;
  padding: 14px 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.constraint-intro {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  color: #64748b;
  font-size: 14px;
  line-height: 1.7;
}

.constraint-intro strong {
  font-size: 15px;
  color: #172033;
}

.constraint-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.constraint-field {
  display: grid;
  gap: 8px;
  min-width: 0;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
}

.constraint-label {
  display: block;
  font-size: 14px;
  font-weight: 700;
  color: #334155;
  line-height: 1.45;
}

.constraint-control {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
}

.constraint-control :deep(.el-input-number) {
  width: 100%;
}

.constraint-unit {
  font-size: 14px;
  font-weight: 700;
  color: #64748b;
}

.table-wrap {
  width: 100%;
  overflow: hidden;
}

.table-wrap :deep(.el-table) {
  width: 100%;
  table-layout: fixed;
}

.table-wrap :deep(.el-table .cell) {
  overflow: hidden;
}

.product-cell {
  display: grid;
  gap: 4px;
}

.product-name {
  color: var(--text-1);
  line-height: 1.4;
  font-size: 15px;
  letter-spacing: 0.01em;
}

.product-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  color: var(--text-3);
  font-size: 12px;
}

.cell-stack {
  display: grid;
  gap: 3px;
}

.cell-stack strong {
  color: var(--text-1);
}

.cell-stack span {
  color: var(--text-3);
  font-size: 12px;
}

.stock-text.low {
  color: #b45309;
  font-weight: 600;
}

.mobile-list {
  display: grid;
  gap: 12px;
}

.mobile-card {
  display: grid;
  gap: 12px;
  padding: 16px;
  border-radius: 14px;
  border: 1px solid rgba(31, 46, 77, 0.08);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(247, 250, 255, 0.96));
  box-shadow: 0 8px 22px rgba(20, 40, 63, 0.06);
}

.mobile-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
}

.mobile-title {
  display: grid;
  gap: 4px;
}

.mobile-title strong {
  color: var(--text-1);
  line-height: 1.4;
  font-size: 15px;
}

.mobile-title span,
.mobile-meta {
  color: var(--text-3);
  font-size: 12px;
}

.mobile-meta {
  display: grid;
  gap: 4px;
}

.mobile-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.mobile-item {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--surface-2);
  border: 1px solid rgba(31, 46, 77, 0.05);
}

.mobile-item span {
  color: var(--text-3);
  font-size: 12px;
}

.mobile-item strong {
  color: var(--text-1);
}

.mobile-item strong.low {
  color: #b45309;
}

.mobile-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.detail-shell {
  display: grid;
  gap: 10px;
}

.detail-group {
  display: grid;
  gap: 10px;
}

.base-overview {
  display: grid;
  gap: 10px;
}

.base-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 320px);
  gap: 14px;
  padding: 0 0 6px;
  border-radius: 16px;
  border: 0;
  background: transparent;
}

.base-hero-main {
  display: grid;
  gap: 8px;
}

.base-hero-caption {
  margin: 0;
  color: var(--text-3);
  font-size: 12px;
}

.base-hero-main h3 {
  margin: 0;
  color: #162749;
  font-size: 22px;
  line-height: 1.25;
  font-weight: 700;
}

.base-tags {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.base-category {
  color: #5d6f8c;
  font-size: 13px;
  font-weight: 500;
}

.base-id-group {
  display: grid;
  gap: 8px;
  align-content: center;
}

.base-id-item {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(31, 46, 77, 0.06);
  background: var(--surface-2);
}

.base-id-item span {
  color: var(--text-3);
  font-size: 12px;
}

.base-id-item strong {
  color: #142a52;
  line-height: 1.35;
  word-break: break-all;
}

.base-kpi-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.base-kpi-item {
  display: grid;
  gap: 6px;
  padding: 11px 13px;
  border-radius: 12px;
  border: 1px solid rgba(31, 46, 77, 0.06);
  background: var(--surface-2);
}

.base-kpi-item span {
  color: var(--text-3);
  font-size: 12px;
}

.base-kpi-item strong {
  color: var(--text-1);
  font-size: 22px;
  line-height: 1.15;
}

.base-kpi-item:nth-child(1) strong,
.base-kpi-item:nth-child(3) strong {
  color: #1d4ed8;
}

.base-kpi-item:nth-child(2) strong {
  color: #334155;
}

.base-kpi-item:nth-child(4) strong,
.base-kpi-item:nth-child(5) strong,
.base-kpi-item:nth-child(6) strong {
  font-size: 20px;
}

.base-meta-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.base-meta-item {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px dashed #ccd8ee;
  background: #f8fafc;
}

.base-meta-item span {
  color: #6b7d98;
  font-size: 12px;
}

.base-meta-item strong {
  color: #1e293b;
  font-size: 15px;
  line-height: 1.3;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.detail-item {
  display: grid;
  gap: 6px;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid var(--line-soft);
  background: #fff;
}

.detail-item span {
  color: var(--text-3);
  font-size: 12px;
}

.detail-item strong {
  color: var(--text-1);
  line-height: 1.35;
  word-break: break-word;
}

.detail-table-wrap {
  width: 100%;
}

.detail-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.detail-kpi-item {
  display: grid;
  gap: 8px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(31, 46, 77, 0.06);
  background: var(--surface-2);
}

.detail-kpi-item span {
  color: var(--text-3);
  font-size: 13px;
}

.detail-kpi-item strong {
  color: var(--text-1);
  font-size: 22px;
  line-height: 1.3;
}

.metric-pairs {
  display: grid;
  gap: 8px;
}

.metric-pairs span {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.metric-pairs label {
  color: var(--text-3);
  font-size: 13px;
}

.metric-pairs strong {
  color: var(--text-1);
  font-size: 15px;
}

.sku-stock-value {
  color: var(--text-1);
  font-size: 15px;
  font-weight: 600;
}

.sku-stock-value.low {
  color: #b45309;
}

.detail-table-wrap :deep(.el-table) {
  width: 100%;
  table-layout: fixed;
}

.detail-table-wrap :deep(.el-table th),
.detail-table-wrap :deep(.el-table td) {
  padding: 10px 0;
}

.detail-table-wrap :deep(.el-table th .cell) {
  font-size: 14px;
}

.detail-table-wrap :deep(.el-table td .cell) {
  font-size: 14px;
  line-height: 1.65;
}

.detail-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
}

.detail-actions {
  display: flex;
  justify-content: flex-end;
}

.product-form {
  display: grid;
  gap: 12px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 14px;
}

@media (max-width: 1280px) {
  .search-toolbar {
    grid-template-columns: minmax(220px, 1fr) repeat(2, 128px) repeat(2, 96px);
  }

  .toolbar-select {
    width: 128px;
  }

  .detail-kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .base-hero {
    grid-template-columns: minmax(0, 1fr);
  }

  .base-kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .product-card {
    padding: 16px;
  }

  .search-toolbar,
  .mobile-grid,
  .base-id-group,
  .base-kpi-grid,
  .base-meta-grid,
  .detail-kpi-grid,
  .detail-grid,
  .constraint-grid,
  .form-grid {
    grid-template-columns: 1fr;
  }

  .mobile-actions {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>

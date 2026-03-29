<template>
  <div class="page-shell">
    <section class="panel-card table-card product-card">
      <div class="section-head">
        <div class="section-title">
          <h3>商品数据管理</h3>
          <p>支持按平台筛选，并在详情中完整查看商品日指标、SKU 与流量推广数据。</p>
        </div>
        <div class="toolbar-actions">
          <el-button @click="handleSearch">刷新</el-button>
          <el-button type="success" @click="openAddDialog">新增商品</el-button>
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
          @keyup.enter="handleSearch"
        />
        <el-select v-model="filters.platform" class="toolbar-select" placeholder="平台筛选">
          <el-option label="全部平台" value="ALL" />
          <el-option v-for="platform in platformOptions" :key="platform" :label="platform" :value="platform" />
        </el-select>
        <el-select v-model="filters.status" class="toolbar-select" placeholder="状态筛选">
          <el-option label="全部状态" value="ALL" />
          <el-option label="销售中" value="ON_SALE" />
          <el-option label="下架" value="OFF_SHELF" />
          <el-option label="未知" value="UNKNOWN" />
        </el-select>
        <el-button type="primary" @click="handleSearch">搜索</el-button>
      </div>

      <div class="selected-bar" v-if="selectedIds.length > 0">
        <el-tag type="success">已选择 {{ selectedIds.length }} 个商品</el-tag>
        <el-button link type="danger" @click="clearSelection">清空选择</el-button>
      </div>

      <div v-if="!isMobile" class="table-wrap">
        <el-table
          ref="tableRef"
          :data="displayData"
          border
          stripe
          v-loading="loading"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="46" />

          <el-table-column label="商品信息" min-width="260" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="product-cell">
                <strong class="product-name">{{ row.productName || '-' }}</strong>
                <div class="product-meta">
                  <span>商品ID {{ row.id }}</span>
                  <span>平台ID {{ row.externalProductId || '-' }}</span>
                  <span>{{ row.categoryName || '未分类' }}</span>
                </div>
              </div>
            </template>
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
                <strong>销量 {{ Number(row.monthlySales || 0) }}</strong>
                <span>转化 {{ formatPercent(row.conversionRate) }}</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDetailDrawer(row)">详情</el-button>
              <el-button link type="success" @click="openTrendDrawer(row)">趋势</el-button>
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
              <span>商品ID {{ row.id }}</span>
            </div>
            <el-tag :type="statusTagType(row.status)">{{ formatStatusText(row.status) }}</el-tag>
          </div>

          <div class="mobile-meta">
            <span>平台：{{ row.platform || '-' }}</span>
            <span>平台ID：{{ row.externalProductId || '-' }}</span>
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
              <span>近30天销量</span>
              <strong>{{ Number(row.monthlySales || 0) }}</strong>
            </div>
          </div>

          <div class="mobile-actions">
            <el-button size="small" :type="isSelected(row.id) ? 'primary' : 'default'" @click="toggleRowSelection(row)">
              {{ isSelected(row.id) ? '取消选择' : '选择' }}
            </el-button>
            <el-button size="small" @click="openDetailDrawer(row)">详情</el-button>
            <el-button size="small" type="success" plain @click="openTrendDrawer(row)">趋势</el-button>
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
              <el-option label="销售中" value="ON_SALE" />
              <el-option label="下架" value="OFF_SHELF" />
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
                  <h4>{{ currentProduct.productName || '-' }}</h4>
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

              <div class="base-meta-grid">
                <div class="base-meta-item">
                  <span>商品平台</span>
                  <strong>{{ currentProduct.platform || '-' }}</strong>
                </div>
                <div class="base-meta-item">
                  <span>库存数量</span>
                  <strong>{{ formatCount(currentProduct.stock) }}</strong>
                </div>
                <div class="base-meta-item">
                  <span>销售状态</span>
                  <strong>{{ formatStatusText(currentProduct.status) }}</strong>
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
              <el-table v-else :data="dailyMetrics" border stripe size="small">
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
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
  addProductManual,
  batchDeleteProducts,
  getProductDailyMetrics,
  getProductList,
  getProductSkus,
  getTrafficPromoDaily,
  type ProductDailyMetricVO,
  type ProductListVO,
  type ProductSkuVO,
  type TrafficPromoDailyVO
} from '../api/product'
import { ElMessage, ElMessageBox, type FormInstance } from 'element-plus'
import ProductTrendDrawer from '../components/ProductTrendDrawer.vue'

const loading = ref(false)
const tableData = ref<ProductListVO[]>([])
const total = ref(0)
const selectedIds = ref<number[]>([])
const dialogVisible = ref(false)
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailTab = ref('base')
const currentProduct = ref<ProductListVO | null>(null)
const dailyMetrics = ref<ProductDailyMetricVO[]>([])
const skus = ref<ProductSkuVO[]>([])
const trafficPromos = ref<TrafficPromoDailyVO[]>([])
const formRef = ref<FormInstance>()
const tableRef = ref<any>(null)
const trendDrawerRef = ref<InstanceType<typeof ProductTrendDrawer>>()
const viewportWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1440)

const queryParams = reactive({
  page: 1,
  size: 10
})

const filters = reactive({
  keyword: '',
  status: 'ALL',
  platform: 'ALL'
})

const form = reactive({
  externalProductId: '',
  productName: '',
  categoryName: '',
  costPrice: 0,
  salePrice: 0,
  stock: 0,
  monthlySales: 120,
  conversionRate: 0.04,
  status: 'ON_SALE'
})

const rules = {
  productName: [{ required: true, message: '请输入商品名称', trigger: 'blur' }],
  costPrice: [{ required: true, message: '请输入成本价', trigger: 'blur' }],
  salePrice: [{ required: true, message: '请输入当前售价', trigger: 'blur' }]
}

const isMobile = computed(() => viewportWidth.value <= 768)
const isVeryNarrowDesktop = computed(() => viewportWidth.value <= 1024)

const platformOptions = computed(() => {
  const defaults = ['淘宝', '天猫', '京东', '拼多多', '抖音']
  const values = new Set<string>(defaults)
  tableData.value.forEach((row) => {
    if (row.platform) values.add(row.platform)
  })
  return Array.from(values)
})

const displayData = computed(() => {
  return tableData.value.filter((row) => {
    if (filters.status !== 'ALL' && row.status !== filters.status) {
      return false
    }
    return true
  })
})

const formatCurrency = (value?: number | null) => `¥${Number(value || 0).toFixed(2)}`
const formatPercent = (value?: number | null) => `${(Number(value || 0) * 100).toFixed(2)}%`
const formatCount = (value?: number | null) => Number(value || 0).toLocaleString('zh-CN')
const formatStatusText = (status?: string) => (status === 'ON_SALE' ? '销售中' : status || '-')
const average = (sum: number, count: number) => (count > 0 ? sum / count : 0)
const calcRate = (numerator?: number | null, denominator?: number | null) => {
  const den = Number(denominator || 0)
  if (den <= 0) return 0
  return Number(numerator || 0) / den
}
const calcGrossProfit = (salePrice?: number | null, costPrice?: number | null) =>
  Number(salePrice || 0) - Number(costPrice || 0)
const dailySummary = computed(() => {
  const rows = dailyMetrics.value
  const totalVisitors = rows.reduce((sum, row) => sum + Number(row.visitorCount || 0), 0)
  const totalTurnover = rows.reduce((sum, row) => sum + Number(row.turnover || 0), 0)
  const avgConversionRate = average(
    rows.reduce((sum, row) => sum + Number(row.conversionRate || 0), 0),
    rows.length
  )
  return {
    days: rows.length,
    totalVisitors,
    totalTurnover,
    avgConversionRate
  }
})

const skuSummary = computed(() => {
  const rows = skus.value
  const totalStock = rows.reduce((sum, row) => sum + Number(row.stock || 0), 0)
  const avgStock = Math.round(average(totalStock, rows.length))
  const avgSalePrice = average(
    rows.reduce((sum, row) => sum + Number(row.salePrice || 0), 0),
    rows.length
  )
  return {
    count: rows.length,
    totalStock,
    avgStock,
    avgSalePrice
  }
})

const trafficSummary = computed(() => {
  const rows = trafficPromos.value
  const sourceCount = new Set(rows.map((row) => row.trafficSource).filter(Boolean)).size
  const totalCost = rows.reduce((sum, row) => sum + Number(row.costAmount || 0), 0)
  const totalPay = rows.reduce((sum, row) => sum + Number(row.payAmount || 0), 0)
  const avgRoi = average(
    rows.reduce((sum, row) => sum + Number(row.roi || 0), 0),
    rows.length
  )
  return {
    sourceCount,
    totalCost,
    totalPay,
    avgRoi
  }
})

const statusTagType = (status?: string) => {
  if (status === 'ON_SALE') return 'success'
  if (status === 'OFF_SHELF') return 'info'
  return 'warning'
}

const clearSelection = () => {
  selectedIds.value = []
  tableRef.value?.clearSelection?.()
}

const isSelected = (id: number) => selectedIds.value.includes(id)

const toggleRowSelection = (row: ProductListVO) => {
  if (isSelected(row.id)) {
    selectedIds.value = selectedIds.value.filter((id) => id !== row.id)
    return
  }
  selectedIds.value = [...selectedIds.value, row.id]
}

watch(
  () => filters.status,
  () => {
    clearSelection()
  }
)

const resetForm = () => {
  form.externalProductId = ''
  form.productName = ''
  form.categoryName = ''
  form.costPrice = 0
  form.salePrice = 0
  form.stock = 0
  form.monthlySales = 120
  form.conversionRate = 0.04
  form.status = 'ON_SALE'
}

const handleSearch = async () => {
  loading.value = true
  try {
    const res: any = await getProductList({
      page: queryParams.page,
      size: queryParams.size,
      keyword: filters.keyword.trim() || undefined,
      platform: filters.platform === 'ALL' ? undefined : filters.platform
    })
    if (res?.code === 200) {
      tableData.value = res.data.records || []
      total.value = res.data.total || 0
      clearSelection()
      return
    }
    ElMessage.error(res?.message || '加载商品失败')
  } catch {
    ElMessage.error('网络异常，无法加载商品')
  } finally {
    loading.value = false
  }
}

const refreshList = () => {
  queryParams.page = 1
  handleSearch()
}

defineExpose({ refreshList })

const handleSelectionChange = (selection: ProductListVO[]) => {
  selectedIds.value = selection.map((item) => item.id)
}

const handleBatchDelete = async () => {
  if (selectedIds.value.length === 0) {
    ElMessage.warning('请先选择要删除的商品')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定删除已选择的 ${selectedIds.value.length} 个商品吗？此操作不可恢复。`,
      '批量删除确认',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    loading.value = true
    const res: any = await batchDeleteProducts(selectedIds.value)
    if (res?.code === 200) {
      ElMessage.success('批量删除成功')
      refreshList()
      return
    }
    ElMessage.error(res?.message || '批量删除失败')
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error('批量删除失败')
    }
  } finally {
    loading.value = false
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
    } catch {
      ElMessage.error('提交失败，请稍后重试')
    }
  })
}

const openTrendDrawer = (row: ProductListVO) => {
  trendDrawerRef.value?.open(row)
}

const loadDetailData = async (productId: number) => {
  detailLoading.value = true
  try {
    const [dailyRes, skuRes, trafficRes] = await Promise.all([
      getProductDailyMetrics(productId, { limit: 90 }),
      getProductSkus(productId),
      getTrafficPromoDaily(productId, { limit: 90 })
    ])

    dailyMetrics.value = dailyRes?.code === 200 ? dailyRes.data || [] : []
    skus.value = skuRes?.code === 200 ? skuRes.data || [] : []
    trafficPromos.value = trafficRes?.code === 200 ? trafficRes.data || [] : []
  } catch {
    ElMessage.error('加载商品明细数据失败')
    dailyMetrics.value = []
    skus.value = []
    trafficPromos.value = []
  } finally {
    detailLoading.value = false
  }
}

const openDetailDrawer = async (row: ProductListVO) => {
  currentProduct.value = row
  detailTab.value = 'base'
  detailVisible.value = true
  await loadDetailData(row.id)
}

const handleResize = () => {
  viewportWidth.value = window.innerWidth
}

onMounted(() => {
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', handleResize)
  }
  handleSearch()
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', handleResize)
  }
})
</script>

<style scoped>
.product-card {
  padding: 20px;
}

.search-toolbar {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) 140px 140px 104px;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
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
  gap: 6px;
}

.product-name {
  color: var(--text-1);
  line-height: 1.4;
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
  gap: 4px;
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
  gap: 10px;
  padding: 14px;
  border-radius: 12px;
  border: 1px solid var(--line-soft);
  background: #fff;
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
  padding: 10px;
  border-radius: 10px;
  background: var(--surface-2);
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
  gap: 12px;
}

.detail-group {
  display: grid;
  gap: 10px;
}

.base-overview {
  display: grid;
  gap: 12px;
}

.base-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(260px, 320px);
  gap: 12px;
  padding: 14px;
  border-radius: 14px;
  border: 1px solid #dbe7ff;
  background: linear-gradient(135deg, #f8fbff 0%, #eef5ff 100%);
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

.base-hero-main h4 {
  margin: 0;
  color: #162749;
  font-size: 24px;
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
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #d8e3f8;
  background: rgba(255, 255, 255, 0.86);
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
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--line-soft);
  background: #fff;
}

.base-kpi-item span {
  color: var(--text-3);
  font-size: 12px;
}

.base-kpi-item strong {
  color: var(--text-1);
  font-size: 24px;
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
  gap: 12px;
  margin-bottom: 14px;
}

.detail-kpi-item {
  display: grid;
  gap: 8px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid var(--line-soft);
  background: linear-gradient(135deg, #f8fbff 0%, #f1f6ff 100%);
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
    grid-template-columns: minmax(220px, 1fr) 128px 128px 96px;
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
  .form-grid {
    grid-template-columns: 1fr;
  }

  .mobile-actions {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>

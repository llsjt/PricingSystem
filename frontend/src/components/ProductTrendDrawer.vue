<template>
  <el-drawer
    v-model="visible"
    :size="drawerSize"
    :destroy-on-close="true"
    title="商品经营趋势"
  >
    <div v-loading="loading" class="trend-shell">
      <section v-if="product" class="panel-card product-panel">
        <div class="section-head">
          <div class="section-title">
            <h3>{{ product.productName }}</h3>
            <p>围绕销量、访客和转化表现查看商品近期经营波动。</p>
          </div>
          <div class="price-pill">当前售价 {{ formatCurrency(product.salePrice) }}</div>
        </div>

        <div class="metric-grid compact-metrics" v-if="trendData">
          <article class="metric-card trend-metric-card">
            <div class="metric-label">日销售量</div>
            <div class="trend-lines">
              <div class="trend-line">
                <span class="trend-line-label">当前值</span>
                <span class="trend-line-value">{{ formatQuantity(trendData.currentDailySales) }}</span>
              </div>
              <div class="trend-line">
                <span class="trend-line-label">增长量</span>
                <span class="trend-line-value">{{ formatSignedQuantity(trendData.dailySalesGrowth) }}</span>
              </div>
              <div class="trend-line">
                <span class="trend-line-label">增长率</span>
                <span class="trend-line-value">{{ formatSignedPercent(trendData.dailySalesGrowthRate) }}</span>
              </div>
            </div>
          </article>
          <article class="metric-card trend-metric-card">
            <div class="metric-label">月销售量</div>
            <div class="trend-lines">
              <div class="trend-line">
                <span class="trend-line-label">当前值</span>
                <span class="trend-line-value">{{ formatQuantity(trendData.currentMonthlySales) }}</span>
              </div>
              <div class="trend-line">
                <span class="trend-line-label">增长量</span>
                <span class="trend-line-value">{{ formatSignedQuantity(trendData.monthlySalesGrowth) }}</span>
              </div>
              <div class="trend-line">
                <span class="trend-line-label">增长率</span>
                <span class="trend-line-value">{{ formatSignedPercent(trendData.monthlySalesGrowthRate) }}</span>
              </div>
            </div>
          </article>
          <article class="metric-card trend-metric-card">
            <div class="metric-label">日利润</div>
            <div class="trend-lines">
              <div class="trend-line">
                <span class="trend-line-label">当前值</span>
                <span class="trend-line-value">{{ formatCurrency(trendData.currentDailyProfit) }}</span>
              </div>
              <div class="trend-line">
                <span class="trend-line-label">增长量</span>
                <span class="trend-line-value">{{ formatSignedCurrency(trendData.dailyProfitGrowth) }}</span>
              </div>
              <div class="trend-line">
                <span class="trend-line-label">增长率</span>
                <span class="trend-line-value">{{ formatSignedPercent(trendData.dailyProfitGrowthRate) }}</span>
              </div>
            </div>
          </article>
          <article class="metric-card trend-metric-card">
            <div class="metric-label">月利润</div>
            <div class="trend-lines">
              <div class="trend-line">
                <span class="trend-line-label">当前值</span>
                <span class="trend-line-value">{{ formatCurrency(trendData.currentMonthlyProfit) }}</span>
              </div>
              <div class="trend-line">
                <span class="trend-line-label">增长量</span>
                <span class="trend-line-value">{{ formatSignedCurrency(trendData.monthlyProfitGrowth) }}</span>
              </div>
              <div class="trend-line">
                <span class="trend-line-label">增长率</span>
                <span class="trend-line-value">{{ formatSignedPercent(trendData.monthlyProfitGrowthRate) }}</span>
              </div>
            </div>
          </article>
        </div>
      </section>

      <section class="panel-card control-panel">
        <div class="section-head">
          <div class="section-title">
            <h3>时间范围</h3>
            <p>按不同时间窗口查看趋势变化。</p>
          </div>
        </div>

        <el-radio-group v-model="days" @change="fetchTrendData">
          <el-radio-button :label="7">近 7 天</el-radio-button>
          <el-radio-button :label="30">近 30 天</el-radio-button>
          <el-radio-button :label="90">近 90 天</el-radio-button>
        </el-radio-group>
      </section>

      <section class="panel-card chart-panel">
        <div class="section-head">
          <div class="section-title">
            <h3>趋势图表</h3>
            <p>图表会根据数据自动显示销量、访客和转化率曲线。</p>
          </div>
        </div>
        <div ref="chartRef" class="chart-container"></div>
      </section>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../api/request'
import { useEChart } from '../composables/useEChart'
import { useViewport } from '../composables/useViewport'
import { resolveRequestErrorMessage } from '../utils/error'
import {
  formatCount,
  formatCurrency as sharedFormatCurrency,
  formatSignedCurrency,
  formatSignedNumber,
  formatSignedPercent
} from '../utils/formatters'

const visible = ref(false)
const loading = ref(false)
const days = ref(30)
const product = ref<any>(null)
const trendData = ref<any>(null)
const { width } = useViewport()
const { chartRef, disposeChart, resizeChart, setChartOption } = useEChart()

const drawerSize = computed(() => (width.value < 900 ? '100%' : '60%'))

const open = (row: any) => {
  product.value = row
  days.value = 30
  visible.value = true
  fetchTrendData()
}

defineExpose({ open })

const formatQuantity = (value: number | string) => formatCount(value)
const formatCurrency = (value: number | string) => sharedFormatCurrency(value)
const formatSignedQuantity = (value: number | string) => formatSignedNumber(value)

const renderChart = () => {
  if (!trendData.value) return

  const visitors = Array.isArray(trendData.value.visitors) ? trendData.value.visitors : []
  const sales = Array.isArray(trendData.value.sales) ? trendData.value.sales : []
  const conversionRates = Array.isArray(trendData.value.conversionRates) ? trendData.value.conversionRates : []
  const hasVisitors = visitors.some((item: number) => Number(item || 0) > 0)
  const hasConversion = conversionRates.some((item: number) => Number(item || 0) > 0)

  const series: any[] = [
    {
      name: '销量',
      type: 'line',
      smooth: true,
      yAxisIndex: 0,
      data: sales
    }
  ]

  if (hasVisitors) {
    series.unshift({
      name: '访客数',
      type: 'bar',
      barMaxWidth: 18,
      yAxisIndex: 0,
      data: visitors
    })
  }

  if (hasConversion) {
    series.push({
      name: '转化率',
      type: 'line',
      smooth: true,
      yAxisIndex: 1,
      data: conversionRates
    })
  }

  setChartOption({
    color: ['#1f6feb', '#10b981', '#f59e0b'],
    tooltip: {
      trigger: 'axis'
    },
    legend: {
      top: 0
    },
    grid: {
      top: 48,
      left: 12,
      right: 24,
      bottom: 40,
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: trendData.value.dates || []
    },
    yAxis: [
      {
        type: 'value',
        name: '数量'
      },
      {
        type: 'value',
        name: '转化率',
        axisLabel: {
          formatter: (value: number) => (value * 100).toFixed(0) + '%'
        }
      }
    ],
    dataZoom: [
      {
        type: 'inside',
        start: 0,
        end: 100
      },
      {
        start: 0,
        end: 100
      }
    ],
    series
  })
}

const fetchTrendData = async () => {
  if (!product.value) return
  loading.value = true
  try {
    const res: any = await request.get('/products/' + product.value.id + '/trend', {
      params: { days: days.value }
    })
    if (res.code === 200) {
      trendData.value = res.data
      await nextTick()
      renderChart()
      return
    }
    ElMessage.error(res.message || '获取趋势数据失败')
  } catch (error) {
    ElMessage.error(await resolveRequestErrorMessage(error, '获取趋势数据失败'))
  } finally {
    loading.value = false
  }
}

watch(width, () => {
  resizeChart()
})

watch(visible, (nextVisible) => {
  if (nextVisible) return
  trendData.value = null
  product.value = null
  disposeChart()
})
</script>


<style scoped>
.trend-shell {
  display: grid;
  gap: 18px;
}

.compact-metrics {
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
}

.trend-metric-card {
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(249, 252, 255, 0.98));
  border: 1px solid var(--border-soft);
  box-shadow: var(--shadow-card);
}

.trend-metric-card::before {
  display: none;
}

.trend-metric-card:hover {
  border-color: var(--border-soft);
  box-shadow: var(--shadow-card);
}

.trend-metric-card .metric-label {
  font-size: 17px;
  font-weight: 700;
  color: #2f4361;
}

.trend-lines {
  margin-top: 10px;
  display: grid;
  gap: 8px;
}

.trend-line {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  align-items: center;
  gap: 14px;
}

.trend-line-label {
  font-size: 14px;
  font-weight: 600;
  color: #5b6f8d;
  white-space: nowrap;
  word-break: keep-all;
}

.trend-line-value {
  min-width: 0;
  font-size: clamp(18px, 1.5vw, 24px);
  line-height: 1.08;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: #1a2f4e;
  text-align: right;
  white-space: nowrap;
  word-break: keep-all;
  font-variant-numeric: tabular-nums;
}

.price-pill {
  display: inline-flex;
  align-items: center;
  min-height: 42px;
  padding: 0 16px;
  border-radius: 999px;
  background: rgba(31, 111, 235, 0.1);
  color: #1f6feb;
  font-weight: 700;
}

.chart-container {
  width: 100%;
  height: 420px;
}

@media (max-width: 768px) {
  .compact-metrics {
    grid-template-columns: 1fr;
  }

  .trend-metric-card .metric-label {
    font-size: 16px;
  }

  .trend-line-value {
    font-size: 22px;
  }

  .trend-line {
    grid-template-columns: 64px minmax(0, 1fr);
    gap: 10px;
  }

  .chart-container {
    height: 320px;
  }
}
</style>

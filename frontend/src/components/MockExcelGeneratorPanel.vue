<template>
  <section class="panel-card generator-panel" v-loading="downloading">
    <div class="section-head">
      <div class="section-title">
        <h2>模拟 Excel 生成</h2>
        <p>按条数生成 4 份可直接导入系统的电商平台导出 Excel，并打包成 zip 下载。</p>
        <p>同一批商品会复用同一组商品 ID，确保跨文件关联一致。</p>
      </div>

      <div class="hero-actions">
        <el-button @click="resetForm">恢复默认</el-button>
        <el-button type="primary" :icon="Download" :loading="downloading" @click="handleDownload">
          生成并下载
        </el-button>
      </div>
    </div>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="导入说明"
      description="生成的数据结构与系统导入模板对齐。下载后回到“批量导入”页签，按实际平台选择后上传即可。"
      class="intro-alert"
    />

    <div class="summary-grid">
      <article v-for="item in outputFiles" :key="item.fileName" class="summary-card">
        <span>{{ item.label }}</span>
        <strong>{{ item.count }}</strong>
        <small>{{ item.fileName }}</small>
      </article>
    </div>

    <el-form label-position="top" class="generator-form">
      <div class="form-grid">
        <el-form-item label="商品基础信息条数">
          <el-input-number v-model="form.productCount" :min="1" :max="5000" :step="1" controls-position="right" />
        </el-form-item>

        <el-form-item label="商品日指标条数">
          <el-input-number v-model="form.dailyCount" :min="1" :max="20000" :step="1" controls-position="right" />
        </el-form-item>

        <el-form-item label="商品 SKU 条数">
          <el-input-number v-model="form.skuCount" :min="1" :max="20000" :step="1" controls-position="right" />
        </el-form-item>

        <el-form-item label="流量推广条数">
          <el-input-number v-model="form.trafficCount" :min="1" :max="20000" :step="1" controls-position="right" />
        </el-form-item>

        <el-form-item label="起始商品 ID">
          <el-input-number
            v-model="form.startProductId"
            :min="1"
            :max="9999999999999"
            :step="1"
            controls-position="right"
          />
        </el-form-item>

        <el-form-item label="最新统计日期">
          <el-date-picker
            v-model="form.startDate"
            type="date"
            value-format="YYYY-MM-DD"
            format="YYYY-MM-DD"
            placeholder="选择日期"
            class="date-field"
          />
        </el-form-item>

        <el-form-item label="随机种子">
          <el-input-number
            v-model="form.seed"
            :min="1"
            :max="999999999"
            :step="1"
            controls-position="right"
          />
        </el-form-item>

        <div class="helper-card">
          <div class="helper-title">生成规则</div>
          <ul>
            <li>4 个 Excel 会共用同一批商品 ID。</li>
            <li>商品基础信息条数决定商品池大小。</li>
            <li>其余 3 张表的条数不能小于商品基础信息条数。</li>
            <li>下载结果是 1 个 zip，内含 4 个 `.xlsx` 文件。</li>
          </ul>
        </div>
      </div>
    </el-form>

    <div class="generator-footer">
      <div class="footer-note">
        <el-tag effect="plain">总输出行数 {{ totalRows }}</el-tag>
        <el-tag effect="plain">商品 ID 连续生成</el-tag>
        <el-tag effect="plain">表头与导入模板一致</el-tag>
      </div>
      <div class="validation-text" :class="{ invalid: !!countError }">
        {{ countError || '当前配置可生成，点击“生成并下载”即可导出 zip。' }}
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { downloadMockExcelBundle, type MockExcelExportDTO } from '../api/product'

type GeneratorForm = Required<MockExcelExportDTO>

const createDefaultForm = (): GeneratorForm => {
  const today = new Date().toISOString().slice(0, 10)
  const compact = today.replace(/-/g, '')
  return {
    productCount: 20,
    dailyCount: 120,
    skuCount: 60,
    trafficCount: 140,
    startProductId: Number(compact) * 10000 + 1,
    startDate: today,
    seed: 20260402
  }
}

const form = reactive<GeneratorForm>(createDefaultForm())
const downloading = ref(false)

const outputFiles = computed(() => [
  { label: '商品基础信息', count: form.productCount, fileName: 'product_base_mock.xlsx' },
  { label: '商品经营日报', count: form.dailyCount, fileName: 'product_daily_metric_mock.xlsx' },
  { label: '商品 SKU', count: form.skuCount, fileName: 'product_sku_mock.xlsx' },
  { label: '流量推广日报', count: form.trafficCount, fileName: 'traffic_promo_daily_mock.xlsx' }
])

const totalRows = computed(() => {
  return form.productCount + form.dailyCount + form.skuCount + form.trafficCount
})

const countError = computed(() => {
  if (form.productCount <= 0) return '商品基础信息条数必须大于 0。'
  if (form.dailyCount < form.productCount) return '商品日指标条数不能小于商品基础信息条数。'
  if (form.skuCount < form.productCount) return '商品 SKU 条数不能小于商品基础信息条数。'
  if (form.trafficCount < form.productCount) return '流量推广条数不能小于商品基础信息条数。'
  return ''
})

const resetForm = () => {
  Object.assign(form, createDefaultForm())
}

const resolveFileName = (contentDisposition?: string) => {
  if (!contentDisposition) return `mock_excel_bundle_${Date.now()}.zip`
  const utf8Match = contentDisposition.match(/filename\*=utf-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1])
  }
  const plainMatch = contentDisposition.match(/filename="?([^"]+)"?/i)
  if (plainMatch?.[1]) {
    return plainMatch[1]
  }
  return `mock_excel_bundle_${Date.now()}.zip`
}

const resolveErrorMessage = async (error: any) => {
  const raw = error?.response?.data
  if (raw instanceof Blob) {
    try {
      const text = await raw.text()
      const parsed = JSON.parse(text)
      return parsed?.message || parsed?.error || '下载失败'
    } catch {
      return '下载失败'
    }
  }
  return error?.response?.data?.message || error?.message || '下载失败'
}

const handleDownload = async () => {
  if (countError.value) {
    ElMessage.warning(countError.value)
    return
  }

  downloading.value = true
  try {
    const payload: MockExcelExportDTO = {
      productCount: form.productCount,
      dailyCount: form.dailyCount,
      skuCount: form.skuCount,
      trafficCount: form.trafficCount,
      startProductId: form.startProductId,
      startDate: form.startDate,
      seed: form.seed
    }

    const response = await downloadMockExcelBundle(payload)
    const blob = new Blob([response.data], { type: 'application/zip' })
    const fileName = resolveFileName(response.headers['content-disposition'])
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = fileName
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('模拟 Excel 已开始下载')
  } catch (error: any) {
    ElMessage.error(await resolveErrorMessage(error))
  } finally {
    downloading.value = false
  }
}
</script>

<style scoped>
.generator-panel {
  padding: 20px;
}

.section-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.section-title {
  display: grid;
  gap: 6px;
}

.section-title h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
  color: #24324a;
}

.section-title p {
  margin: 0;
  color: #5e6a7d;
  line-height: 1.6;
}

.hero-actions {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.intro-alert {
  margin-bottom: 16px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.summary-card {
  display: grid;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(37, 99, 235, 0.08), rgba(255, 255, 255, 0.94));
  border: 1px solid rgba(37, 99, 235, 0.15);
}

.summary-card span {
  color: #5f6d82;
  font-size: 12px;
}

.summary-card strong {
  color: #22324b;
  font-size: 26px;
  line-height: 1;
}

.summary-card small {
  color: #44618d;
  word-break: break-all;
}

.generator-form {
  margin-top: 4px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  align-items: start;
}

.generator-form :deep(.el-input-number),
.date-field {
  width: 100%;
}

.helper-card {
  grid-column: span 2;
  min-height: 100%;
  padding: 16px;
  border-radius: 12px;
  background: #fafcff;
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.helper-title {
  margin-bottom: 10px;
  font-weight: 700;
  color: #22324b;
}

.helper-card ul {
  margin: 0;
  padding-left: 18px;
  color: #5e6a7d;
  line-height: 1.8;
}

.generator-footer {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-top: 8px;
}

.footer-note {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.validation-text {
  color: #516076;
  text-align: right;
}

.validation-text.invalid {
  color: #c2410c;
}

@media (max-width: 1200px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .form-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .helper-card {
    grid-column: span 2;
  }
}

@media (max-width: 768px) {
  .section-head,
  .generator-footer {
    flex-direction: column;
    align-items: stretch;
  }

  .hero-actions {
    justify-content: stretch;
  }

  .hero-actions .el-button {
    flex: 1;
  }

  .summary-grid,
  .form-grid {
    grid-template-columns: 1fr;
  }

  .helper-card {
    grid-column: span 1;
  }

  .validation-text {
    text-align: left;
  }
}
</style>

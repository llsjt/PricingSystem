<template>
  <div class="page-shell data-page">
    <el-tabs v-model="activeTab" class="data-tabs">
      <el-tab-pane name="products">
        <template #label>
          <span class="tab-label">
            <el-icon><Document /></el-icon>
            <span>商品管理</span>
          </span>
        </template>
        <ProductList ref="productListRef" />
      </el-tab-pane>

      <el-tab-pane name="import">
        <template #label>
          <span class="tab-label">
            <el-icon><UploadFilled /></el-icon>
            <span>批量导入</span>
          </span>
        </template>

        <section class="panel-card import-panel">
          <div class="section-head">
            <div class="section-title">
              <h2>Excel 批量导入</h2>
              <p>支持导入 4 类电商平台 Excel 模板：商品基础信息、商品SKU、商品经营日报、流量推广日报。</p>
              <p>当前导入模式为自动识别 Excel（根据表头自动匹配模板类型）。</p>
            </div>
          </div>

          <div class="template-brief">
            <span>可导入模板：</span>
            <el-tag size="small" effect="plain">商品基础信息</el-tag>
            <el-tag size="small" effect="plain">商品SKU</el-tag>
            <el-tag size="small" effect="plain">商品经营日报</el-tag>
            <el-tag size="small" effect="plain">流量推广日报</el-tag>
          </div>

          <div class="platform-picker">
            <span class="picker-label">电商平台</span>
            <el-select v-model="selectedPlatform" placeholder="请先选择电商平台" class="platform-select" clearable>
              <el-option
                v-for="platform in platformOptions"
                :key="platform"
                :label="platform"
                :value="platform"
              />
            </el-select>
          </div>

          <div class="import-layout">
            <div class="import-main">
              <el-upload
                class="upload-box"
                drag
                :http-request="handleCustomUpload"
                :before-upload="beforeUpload"
                :show-file-list="false"
                accept=".xlsx,.xls"
                :limit="1"
              >
                <el-icon class="upload-icon"><UploadFilled /></el-icon>
                <div class="upload-title">上传电商平台导出的 Excel</div>
                <div class="upload-desc">
                  {{
                    selectedPlatform
                      ? `当前平台：${selectedPlatform}；${autoDetect ? '系统会根据表头自动识别导入类型' : `当前将按“${selectedTypeInfo.title}”解析`}`
                      : '请先选择电商平台，再上传 Excel'
                  }}
                </div>
                <div class="upload-hint">支持 `.xlsx` 和 `.xls`，单文件不超过 10MB</div>
              </el-upload>
            </div>
          </div>

          <el-alert
            v-if="importResult"
            :title="importAlertTitle"
            :type="importAlertType"
            :description="importResult.summary"
            show-icon
            class="upload-feedback"
          />

          <div v-if="importResult" class="result-card">
            <div class="result-grid">
              <div class="result-item">
                <span>导入类型</span>
                <strong>{{ importResult.dataTypeLabel }}</strong>
              </div>
              <div class="result-item">
                <span>目标表</span>
                <strong>{{ importResult.targetTable }}</strong>
              </div>
              <div class="result-item">
                <span>总行数</span>
                <strong>{{ importResult.rowCount }}</strong>
              </div>
              <div class="result-item">
                <span>成功 / 失败</span>
                <strong>{{ importResult.successCount }} / {{ importResult.failCount }}</strong>
              </div>
              <div class="result-item">
                <span>时间范围</span>
                <strong>{{ formatDateRange(importResult.startDate, importResult.endDate) }}</strong>
              </div>
              <div class="result-item">
                <span>识别方式</span>
                <strong>{{ importResult.autoDetected ? '表头自动识别' : '手动指定类型' }}</strong>
              </div>
            </div>

            <div v-if="importResult.errors?.length" class="error-box">
              <strong>部分失败明细</strong>
              <ul>
                <li v-for="item in importResult.errors" :key="item">{{ item }}</li>
              </ul>
            </div>
          </div>
        </section>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Document, UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, type UploadProps } from 'element-plus'
import ProductList from './ProductList.vue'
import { downloadTemplate, type ImportDataType, type ImportResultVO } from '../api/product'
import request from '../api/request'

interface ImportTypeOption {
  code: Exclude<ImportDataType, 'AUTO'>
  title: string
  table: string
  description: string
  fields: string[]
}

const importTypes: ImportTypeOption[] = [
  {
    code: 'PRODUCT_BASE',
    title: '商品基础信息',
    table: 'product',
    description: '同步电商平台商品主档，写入商品 ID、标题、类目、售价、成本价、库存和状态。',
    fields: ['商品ID', '商品标题', '商品类目', '当前售价', '库存']
  },
  {
    code: 'PRODUCT_SKU',
    title: '商品SKU',
    table: 'product_sku',
    description: '导入商品 SKU 明细，按商品维度写入 SKU 编号、规格属性、价格和库存。',
    fields: ['商品ID', 'SKU ID', 'SKU属性', 'SKU售价', 'SKU库存']
  },
  {
    code: 'PRODUCT_DAILY_METRIC',
    title: '商品经营日报',
    table: 'product_daily_metric',
    description: '导入商品维度的日经营指标，沉淀访客、加购、支付件数、支付金额和转化率。',
    fields: ['统计日期', '商品ID', '访客数', '支付件数', '支付金额']
  },
  {
    code: 'TRAFFIC_PROMO_DAILY',
    title: '流量推广日报',
    table: 'traffic_promo_daily',
    description: '导入渠道曝光、点击、花费、支付金额、ROI 等推广数据。',
    fields: ['统计日期', '流量来源', '展现量', '点击量', '花费']
  }
]

const activeTab = ref('products')
const autoDetect = ref(true)
const selectedType = ref<Exclude<ImportDataType, 'AUTO'>>('PRODUCT_BASE')
const selectedPlatform = ref('')
const platformOptions = ['淘宝', '天猫', '京东', '拼多多', '抖音']
const importResult = ref<ImportResultVO | null>(null)
const productListRef = ref<any>(null)

const selectedTypeInfo = computed(() => {
  return importTypes.find((item) => item.code === selectedType.value) || importTypes[0]
})

const requestType = computed<ImportDataType>(() => {
  return autoDetect.value ? 'AUTO' : selectedType.value
})

const importAlertType = computed(() => {
  if (!importResult.value) return 'info'
  if (importResult.value.uploadStatus === 'SUCCESS') return 'success'
  if (importResult.value.uploadStatus === 'PARTIAL_SUCCESS') return 'warning'
  return 'error'
})

const importAlertTitle = computed(() => {
  if (!importResult.value) return ''
  if (importResult.value.uploadStatus === 'SUCCESS') return '导入成功'
  if (importResult.value.uploadStatus === 'PARTIAL_SUCCESS') return '部分导入成功'
  return '导入失败'
})

const resolveErrorMessage = (error: any) => {
  return error?.response?.data?.message || error?.message || '网络异常'
}

const createUploadError = (message: string) => {
  return Object.assign(new Error(message), {
    name: 'UploadAjaxError',
    status: 500,
    method: 'POST',
    url: '/products/import'
  })
}

const beforeUpload: UploadProps['beforeUpload'] = (rawFile) => {
  if (!selectedPlatform.value) {
    ElMessage.warning('请先选择电商平台')
    return false
  }
  const name = rawFile.name.toLowerCase()
  if (!name.endsWith('.xlsx') && !name.endsWith('.xls')) {
    ElMessage.error('请上传 Excel 文件（.xls / .xlsx）')
    return false
  }
  if (rawFile.size / 1024 / 1024 > 10) {
    ElMessage.error('文件大小不能超过 10MB')
    return false
  }
  return true
}

const handleCustomUpload: UploadProps['httpRequest'] = async (options) => {
  const formData = new FormData()
  formData.append('file', options.file)

  try {
    const response: any = await request.post('/products/import', formData, {
      params: { dataType: requestType.value, platform: selectedPlatform.value },
      headers: { 'Content-Type': 'multipart/form-data' }
    })

    if (response.code === 200) {
      importResult.value = response.data
      ElMessage.success('导入完成')
      productListRef.value?.refreshList?.()
      options.onSuccess?.(response.data)
      return
    }

    importResult.value = null
    const message = response.message || '导入失败'
    ElMessage.error(message)
    options.onError?.(createUploadError(message))
  } catch (error: any) {
    importResult.value = null
    const message = resolveErrorMessage(error)
    ElMessage.error(`上传失败：${message}`)
    options.onError?.(createUploadError(message))
  }
}

const handleDownloadTemplate = async (type: Exclude<ImportDataType, 'AUTO'> = selectedType.value) => {
  try {
    const response: any = await downloadTemplate(type)
    const blob = new Blob([response], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    const current = importTypes.find((item) => item.code === type)
    link.href = url
    link.download = `${current?.title || '电商平台导入'}模板.xlsx`
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('模板下载成功')
  } catch (error: any) {
    ElMessage.error(`模板下载失败：${resolveErrorMessage(error)}`)
  }
}

const formatDateRange = (start?: string, end?: string) => {
  if (!start && !end) return '无日期字段'
  if (start && end) return `${start} ~ ${end}`
  return start || end || '-'
}
</script>

<style scoped>
.data-page {
  gap: 16px;
}

.data-tabs :deep(.el-tabs__content) {
  padding-top: 8px;
}

.data-tabs :deep(.el-tab-pane > .page-shell) {
  gap: 0;
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.import-panel {
  padding: 20px;
}

.section-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
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

.template-brief {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
  color: #4b5b73;
}

.template-brief :deep(.el-tag) {
  border-color: rgba(37, 99, 235, 0.25);
  color: #2356c5;
}

.platform-picker {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.picker-label {
  color: #4b5b73;
  font-weight: 600;
  white-space: nowrap;
}

.platform-select {
  width: 220px;
}

.import-layout {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.import-main {
  min-width: 0;
}

.upload-box {
  width: 100%;
}

.upload-box :deep(.el-upload) {
  width: 100%;
}

.upload-box :deep(.el-upload-dragger) {
  width: 100%;
  min-height: 250px;
  border-radius: 14px;
  border: 1.5px dashed rgba(37, 99, 235, 0.26);
  background: linear-gradient(180deg, rgba(37, 99, 235, 0.06), rgba(255, 255, 255, 0.94));
}

.upload-icon {
  font-size: 42px;
  color: #2563eb;
  margin-bottom: 12px;
}

.upload-title {
  font-size: 18px;
  font-weight: 700;
  color: #21324d;
  margin-bottom: 8px;
}

.upload-desc,
.upload-hint {
  color: #627086;
  line-height: 1.7;
}

.upload-feedback {
  margin-top: 16px;
}

.result-card {
  margin-top: 16px;
  padding: 16px;
  border-radius: 12px;
  background: #fafcff;
  border: 1px solid rgba(37, 99, 235, 0.12);
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.result-item {
  display: grid;
  gap: 6px;
  padding: 14px;
  border-radius: 10px;
  background: white;
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.result-item span {
  color: #6b778a;
  font-size: 12px;
}

.result-item strong {
  color: #23334e;
  font-size: 15px;
}

.error-box {
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 10px;
  background: rgba(248, 113, 113, 0.08);
  border: 1px solid rgba(248, 113, 113, 0.18);
}

.error-box strong {
  display: block;
  margin-bottom: 8px;
  color: #b42318;
}

.error-box ul {
  margin: 0;
  padding-left: 18px;
  color: #7c2d12;
  line-height: 1.8;
}

@media (max-width: 1100px) {
  .result-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .import-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .platform-picker {
    flex-direction: column;
    align-items: flex-start;
  }

  .platform-select {
    width: 100%;
  }

  .result-grid {
    grid-template-columns: 1fr;
  }
}
</style>

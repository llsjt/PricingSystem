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
              <p>支持导入 4 类电商平台 Excel 模板：商品基础信息、商品 SKU、商品经营日报、流量推广日报。</p>
              <p>当前导入模式为自动识别 Excel，会根据表头自动匹配模板类型。</p>
            </div>
          </div>

          <div class="template-brief">
            <span>可导入模板：</span>
            <el-tag size="small" effect="plain">商品基础信息</el-tag>
            <el-tag size="small" effect="plain">商品 SKU</el-tag>
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
                      ? (autoDetect
                        ? `当前平台：${selectedPlatform}，系统会根据表头自动识别导入类型`
                        : `当前平台：${selectedPlatform}，当前将按“${selectedTypeInfo.title}”解析`)
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

      <el-tab-pane name="mock">
        <template #label>
          <span class="tab-label">
            <el-icon><Download /></el-icon>
            <span>模拟数据</span>
          </span>
        </template>
        <MockExcelGeneratorPanel />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Document, Download, UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, type UploadProps } from 'element-plus'
import MockExcelGeneratorPanel from '../components/MockExcelGeneratorPanel.vue'
import ProductList from './ProductList.vue'
import { downloadTemplate, type ImportDataType, type ImportResultVO } from '../api/product'
import request from '../api/request'
import { resolveRequestErrorMessage } from '../utils/error'

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
    title: '\u5546\u54c1\u57fa\u7840\u4fe1\u606f',
    table: 'product',
    description: '\u7528\u4e8e\u5bfc\u5165\u5546\u54c1\u4e3b\u6863\u4fe1\u606f\u3002\u5546\u54c1 ID \u9700\u8981\u4e0e\u5176\u4ed6\u6a21\u677f\u4fdd\u6301\u4e00\u81f4\uff0c\u4fbf\u4e8e\u8de8\u8868\u5173\u8054\u3002',
    fields: ['\u5546\u54c1ID', '\u5546\u54c1\u6807\u9898', '\u5546\u54c1\u7c7b\u76ee', '\u5f53\u524d\u552e\u4ef7', '\u5e93\u5b58']
  },
  {
    code: 'PRODUCT_SKU',
    title: '\u5546\u54c1SKU',
    table: 'product_sku',
    description: '\u7528\u4e8e\u5bfc\u5165 SKU \u660e\u7ec6\u3002\u6bcf\u6761\u8bb0\u5f55\u9700\u8981\u5305\u542b SKU ID\uff0c\u5e76\u901a\u8fc7\u5546\u54c1 ID \u5173\u8054\u5230\u5bf9\u5e94\u5546\u54c1\u3002',
    fields: ['\u5546\u54c1ID', 'SKU ID', 'SKU\u540d\u79f0', 'SKU\u552e\u4ef7', 'SKU\u5e93\u5b58']
  },
  {
    code: 'PRODUCT_DAILY_METRIC',
    title: '\u5546\u54c1\u65e5\u6307\u6807',
    table: 'product_daily_metric',
    description: '\u7528\u4e8e\u5bfc\u5165\u5546\u54c1\u6bcf\u65e5\u7ecf\u8425\u6307\u6807\uff0c\u9002\u5408\u6a21\u62df\u5e73\u53f0\u5bfc\u51fa\u7684\u65e5\u62a5\u6570\u636e\u3002',
    fields: ['\u7edf\u8ba1\u65e5\u671f', '\u5546\u54c1ID', '\u8bbf\u5ba2\u6570', '\u6210\u4ea4\u91d1\u989d', '\u652f\u4ed8\u4ef6\u6570']
  },
  {
    code: 'TRAFFIC_PROMO_DAILY',
    title: '\u6d41\u91cf\u4e0e\u63a8\u5e7f\u65e5\u6307\u6807',
    table: 'traffic_promo_daily',
    description: '\u7528\u4e8e\u5bfc\u5165\u6d41\u91cf\u6765\u6e90\u4e0e\u63a8\u5e7f\u6548\u679c\u6570\u636e\uff0c\u652f\u6301\u66dd\u5149\u3001\u70b9\u51fb\u3001\u82b1\u8d39\u3001ROI \u7b49\u6307\u6807\u3002',
    fields: ['\u7edf\u8ba1\u65e5\u671f', '\u6d41\u91cf\u6765\u6e90', '\u66dd\u5149\u91cf', '\u70b9\u51fb\u91cf', 'ROI']
  }
]

const activeTab = ref('products')
const autoDetect = ref(true)
const selectedType = ref<Exclude<ImportDataType, 'AUTO'>>('PRODUCT_BASE')
const selectedPlatform = ref('')
const platformOptions = ['\u6dd8\u5b9d', '\u5929\u732b', '\u4eac\u4e1c', '\u62fc\u591a\u591a', '\u6296\u5e97']
const importResult = ref<ImportResultVO | null>(null)
const productListRef = ref<any>(null)

const selectedTypeInfo = computed(() => importTypes.find((item) => item.code === selectedType.value) || importTypes[0])
const requestType = computed<ImportDataType>(() => (autoDetect.value ? 'AUTO' : selectedType.value))

const importAlertType = computed(() => {
  if (!importResult.value) return 'info'
  if (importResult.value.uploadStatus === 'SUCCESS') return 'success'
  if (importResult.value.uploadStatus === 'PARTIAL_SUCCESS') return 'warning'
  return 'error'
})

const importAlertTitle = computed(() => {
  if (!importResult.value) return ''
  if (importResult.value.uploadStatus === 'SUCCESS') return '\u5bfc\u5165\u6210\u529f'
  if (importResult.value.uploadStatus === 'PARTIAL_SUCCESS') return '\u90e8\u5206\u5bfc\u5165\u6210\u529f'
  return '\u5bfc\u5165\u5931\u8d25'
})

const createUploadError = (message: string) => Object.assign(new Error(message), {
  name: 'UploadAjaxError',
  status: 500,
  method: 'POST',
  url: '/products/import'
})

const beforeUpload: UploadProps['beforeUpload'] = (rawFile) => {
  if (!selectedPlatform.value) {
    ElMessage.warning('\u8bf7\u5148\u9009\u62e9\u7535\u5546\u5e73\u53f0')
    return false
  }

  const name = rawFile.name.toLowerCase()
  if (!name.endsWith('.xlsx') && !name.endsWith('.xls')) {
    ElMessage.error('\u8bf7\u4e0a\u4f20 Excel \u6587\u4ef6\uff08.xls / .xlsx\uff09')
    return false
  }

  if (rawFile.size / 1024 / 1024 > 10) {
    ElMessage.error('\u6587\u4ef6\u5927\u5c0f\u4e0d\u80fd\u8d85\u8fc7 10MB')
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
      ElMessage.success('\u5bfc\u5165\u6210\u529f')
      productListRef.value?.refreshList?.()
      options.onSuccess?.(response.data)
      return
    }

    importResult.value = null
    const message = response.message || '\u5bfc\u5165\u5931\u8d25'
    ElMessage.error(message)
    options.onError?.(createUploadError(message))
  } catch (error) {
    importResult.value = null
    const message = await resolveRequestErrorMessage(error)
    ElMessage.error(`\u5bfc\u5165\u5931\u8d25\uff1a${message}`)
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
    link.download = `${current?.title || '\u5bfc\u5165\u6a21\u677f'}\u6a21\u677f.xlsx`
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('\u6a21\u677f\u4e0b\u8f7d\u6210\u529f')
  } catch (error) {
    const message = await resolveRequestErrorMessage(error)
    ElMessage.error(`\u6a21\u677f\u4e0b\u8f7d\u5931\u8d25\uff1a${message}`)
  }
}

const formatDateRange = (start?: string, end?: string) => {
  if (!start && !end) return '\u672a\u63d0\u4f9b'
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


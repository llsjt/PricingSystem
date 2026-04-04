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

          <div class="platform-picker">
            <span class="picker-label">目标店铺</span>
            <el-select v-model="selectedShopId" placeholder="请选择导入的目标店铺" class="platform-select" clearable>
              <el-option
                v-for="shop in filteredShops"
                :key="shop.id"
                :label="`${shop.shopName}（${shop.platform}）`"
                :value="shop.id"
              />
            </el-select>
          </div>

          <div class="import-layout">
            <div class="import-main">
              <el-upload
                ref="uploadRef"
                class="upload-box"
                drag
                :http-request="handleCustomUpload"
                :before-upload="beforeUpload"
                :show-file-list="false"
                accept=".xlsx,.xls"
                multiple
                :disabled="batchProcessing || preparingUploads > 0"
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
                <div class="upload-hint">
                  支持一次选择多个 `.xlsx` 和 `.xls`，系统会自动按模板类型排序并逐个导入
                </div>
              </el-upload>
            </div>
          </div>

          <el-alert
            v-if="hasBatchResults"
            :title="batchAlertTitle"
            :type="batchAlertType"
            :description="batchAlertDescription"
            show-icon
            class="upload-feedback"
          />

          <div v-if="hasBatchResults" class="result-card">
            <div class="result-grid">
              <div class="result-item">
                <span>批次文件数</span>
                <strong>{{ batchSummary.totalFiles }}</strong>
              </div>
              <div class="result-item">
                <span>成功文件</span>
                <strong>{{ batchSummary.successFiles }}</strong>
              </div>
              <div class="result-item">
                <span>失败文件</span>
                <strong>{{ batchSummary.failedFiles }}</strong>
              </div>
              <div class="result-item">
                <span>累计总行数</span>
                <strong>{{ batchSummary.totalRows }}</strong>
              </div>
              <div class="result-item">
                <span>累计成功 / 失败行</span>
                <strong>{{ batchSummary.successRows }} / {{ batchSummary.failedRows }}</strong>
              </div>
              <div class="result-item">
                <span>部分成功文件</span>
                <strong>{{ batchSummary.partialFiles }}</strong>
              </div>
            </div>

            <div class="file-result-list">
              <article v-for="item in sortedBatchFiles" :key="item.uid" class="file-result-card">
                <div class="file-result-head">
                  <div class="file-result-title">
                    <strong>{{ item.fileName }}</strong>
                    <span>{{ resolveFileTypeLabel(item) }}</span>
                  </div>
                  <el-tag size="small" :type="resolveFileStatusTagType(item)">{{ resolveFileStatusText(item) }}</el-tag>
                </div>

                <div class="result-grid file-result-grid">
                  <div class="result-item">
                    <span>识别类型</span>
                    <strong>{{ resolveFileTypeLabel(item) }}</strong>
                  </div>
                  <div class="result-item">
                    <span>目标表</span>
                    <strong>{{ resolveFileTargetTable(item) }}</strong>
                  </div>
                  <div class="result-item">
                    <span>总行数</span>
                    <strong>{{ item.result?.rowCount ?? '-' }}</strong>
                  </div>
                  <div class="result-item">
                    <span>成功 / 失败</span>
                    <strong>{{ item.result ? `${item.result.successCount} / ${item.result.failCount}` : '-' }}</strong>
                  </div>
                  <div class="result-item">
                    <span>时间范围</span>
                    <strong>{{ item.result ? formatDateRange(item.result.startDate, item.result.endDate) : '-' }}</strong>
                  </div>
                  <div class="result-item">
                    <span>识别方式</span>
                    <strong>{{ resolveFileDetectMode(item) }}</strong>
                  </div>
                </div>

                <div v-if="resolveFileErrorText(item)" class="error-box compact-error-box">
                  <strong>错误摘要</strong>
                  <p>{{ resolveFileErrorText(item) }}</p>
                </div>
              </article>
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
import { computed, onMounted, ref } from 'vue'
import { Document, Download, UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, type UploadInstance, type UploadProps, type UploadRequestOptions } from 'element-plus'
import MockExcelGeneratorPanel from '../components/MockExcelGeneratorPanel.vue'
import ProductList from './ProductList.vue'
import { downloadTemplate, type ImportDataType, type ImportResultVO } from '../api/product'
import request from '../api/request'
import { resolveRequestErrorMessage } from '../utils/error'
import { useShopStore } from '../stores/shop'
import {
  detectImportTypeFromFile,
  getImportDetectionRule,
  type SupportedImportType
} from '../utils/importDetection'

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

type FileImportStatus = 'detecting' | 'pending' | 'uploading' | 'success' | 'partial' | 'failed'

interface ImportBatchFileItem {
  uid: string
  fileName: string
  status: FileImportStatus
  sequence: number
  detectedType: SupportedImportType | null
  detectError?: string
  result?: ImportResultVO
  errorMessage?: string
  processingOrder?: number
}

interface QueuedUploadItem {
  fileItem: ImportBatchFileItem
  options: UploadRequestOptions
}

const shopStore = useShopStore()
const activeTab = ref('products')
const autoDetect = ref(true)
const selectedType = ref<Exclude<ImportDataType, 'AUTO'>>('PRODUCT_BASE')
const selectedPlatform = ref('')
const selectedShopId = ref<number | null>(null)
const platformOptions = ['\u6dd8\u5b9d', '\u5929\u732b', '\u4eac\u4e1c', '\u62fc\u591a\u591a', '\u6296\u5e97']
const productListRef = ref<any>(null)
const uploadRef = ref<UploadInstance>()
const importBatchFiles = ref<ImportBatchFileItem[]>([])
const queuedUploads = ref<QueuedUploadItem[]>([])
const batchProcessing = ref(false)
const preparingUploads = ref(0)
const currentUploadIndex = ref(-1)
const uploadSequence = ref(0)
const processingSequence = ref(0)
let queueTimer: number | undefined

const filteredShops = computed(() => {
  if (!selectedPlatform.value) return shopStore.shops
  return shopStore.shops.filter((s) => s.platform === selectedPlatform.value)
})

onMounted(() => {
  shopStore.fetchShops()
})

const selectedTypeInfo = computed(() => importTypes.find((item) => item.code === selectedType.value) || importTypes[0])
const requestType = computed<ImportDataType>(() => (autoDetect.value ? 'AUTO' : selectedType.value))
const hasBatchResults = computed(() => importBatchFiles.value.length > 0)
const completedFileStatuses: FileImportStatus[] = ['success', 'partial', 'failed']
const sortedBatchFiles = computed(() =>
  [...importBatchFiles.value].sort((left, right) => {
    const leftOrder = left.processingOrder ?? Number.MAX_SAFE_INTEGER
    const rightOrder = right.processingOrder ?? Number.MAX_SAFE_INTEGER
    if (leftOrder !== rightOrder) {
      return leftOrder - rightOrder
    }
    return left.sequence - right.sequence
  })
)
const batchSummary = computed(() => {
  const successFiles = importBatchFiles.value.filter((item) => item.status === 'success').length
  const partialFiles = importBatchFiles.value.filter((item) => item.status === 'partial').length
  const failedFiles = importBatchFiles.value.filter((item) => item.status === 'failed').length
  const totalRows = importBatchFiles.value.reduce((sum, item) => sum + (item.result?.rowCount ?? 0), 0)
  const successRows = importBatchFiles.value.reduce((sum, item) => sum + (item.result?.successCount ?? 0), 0)
  const failedRows = importBatchFiles.value.reduce((sum, item) => sum + (item.result?.failCount ?? 0), 0)

  return {
    totalFiles: importBatchFiles.value.length,
    successFiles,
    partialFiles,
    failedFiles,
    totalRows,
    successRows,
    failedRows
  }
})
const batchAlertType = computed(() => {
  if (!hasBatchResults.value) return 'info'
  if (batchProcessing.value || preparingUploads.value > 0) return 'info'
  if (batchSummary.value.failedFiles === 0) return 'success'
  if (batchSummary.value.successFiles + batchSummary.value.partialFiles > 0) return 'warning'
  return 'error'
})
const batchAlertTitle = computed(() => {
  if (!hasBatchResults.value) return ''
  if (batchProcessing.value || preparingUploads.value > 0) return '\u6b63\u5728\u5904\u7406\u5bfc\u5165\u6279\u6b21'
  if (batchSummary.value.failedFiles === 0) return '\u6279\u91cf\u5bfc\u5165\u6210\u529f'
  if (batchSummary.value.successFiles + batchSummary.value.partialFiles > 0) return '\u6279\u91cf\u5bfc\u5165\u5df2\u5b8c\u6210\uff0c\u4f46\u90e8\u5206\u6587\u4ef6\u5931\u8d25'
  return '\u6279\u91cf\u5bfc\u5165\u5931\u8d25'
})
const batchAlertDescription = computed(() => {
  if (!hasBatchResults.value) return ''

  if (batchProcessing.value || preparingUploads.value > 0) {
    const completedFiles = importBatchFiles.value.filter((item) => completedFileStatuses.includes(item.status)).length
    const currentFileIndex = currentUploadIndex.value >= 0 ? currentUploadIndex.value + 1 : completedFiles + 1
    return `\u5df2\u6536\u5230 ${batchSummary.value.totalFiles} \u4e2a\u6587\u4ef6\uff0c\u5f53\u524d\u6b63\u5728\u5904\u7406\u7b2c ${Math.min(currentFileIndex, Math.max(batchSummary.value.totalFiles, 1))} \u4e2a\u6587\u4ef6\u3002\u5355\u4e2a\u6587\u4ef6\u5bfc\u5165\u5931\u8d25\u65f6\uff0c\u7cfb\u7edf\u4f1a\u81ea\u52a8\u7ee7\u7eed\u5904\u7406\u540e\u7eed\u6587\u4ef6\u3002`
  }

  if (batchSummary.value.failedFiles === 0) {
    return `\u5171\u5904\u7406 ${batchSummary.value.totalFiles} \u4e2a\u6587\u4ef6\uff0c\u6210\u529f ${batchSummary.value.successFiles + batchSummary.value.partialFiles} \u4e2a\uff0c\u7d2f\u8ba1\u5bfc\u5165 ${batchSummary.value.successRows} \u884c\u6709\u6548\u6570\u636e\u3002`
  }

  if (batchSummary.value.successFiles + batchSummary.value.partialFiles > 0) {
    return `\u5171\u5904\u7406 ${batchSummary.value.totalFiles} \u4e2a\u6587\u4ef6\uff0c\u6210\u529f ${batchSummary.value.successFiles} \u4e2a\uff0c\u90e8\u5206\u6210\u529f ${batchSummary.value.partialFiles} \u4e2a\uff0c\u5931\u8d25 ${batchSummary.value.failedFiles} \u4e2a\u3002`
  }

  return `\u5171\u5904\u7406 ${batchSummary.value.totalFiles} \u4e2a\u6587\u4ef6\uff0c\u5168\u90e8\u5bfc\u5165\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5 Excel \u8868\u5934\u548c\u76ee\u6807\u5e97\u94fa\u914d\u7f6e\u540e\u91cd\u8bd5\u3002`
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
  if (!selectedShopId.value) {
    ElMessage.warning('\u8bf7\u5148\u9009\u62e9\u76ee\u6807\u5e97\u94fa')
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

const compareImportTypeOrder = (left: SupportedImportType | null, right: SupportedImportType | null) => {
  const leftRule = getImportDetectionRule(left)
  const rightRule = getImportDetectionRule(right)
  const leftOrder = leftRule?.order ?? Number.MAX_SAFE_INTEGER
  const rightOrder = rightRule?.order ?? Number.MAX_SAFE_INTEGER
  return leftOrder - rightOrder
}

const scheduleQueueProcessing = () => {
  if (queueTimer) {
    window.clearTimeout(queueTimer)
  }
  queueTimer = window.setTimeout(() => {
    queueTimer = undefined
    void processUploadQueue()
  }, 0)
}

const resolveLocalErrorMessage = (error: unknown) => {
  if (error instanceof Error && error.message) {
    return error.message
  }
  return '\u65e0\u6cd5\u9884\u8bc6\u522b Excel \u7c7b\u578b'
}

const isImportResponseSuccessful = (result?: ImportResultVO) =>
  result?.uploadStatus === 'SUCCESS' || result?.uploadStatus === 'PARTIAL_SUCCESS'

const handleCustomUpload: UploadProps['httpRequest'] = async (options) => {
  const sequence = uploadSequence.value++
  const fileItem: ImportBatchFileItem = {
    uid: `${Date.now()}-${sequence}`,
    fileName: options.file.name,
    status: 'detecting',
    sequence,
    detectedType: null
  }

  importBatchFiles.value.push(fileItem)
  preparingUploads.value += 1

  try {
    fileItem.detectedType = await detectImportTypeFromFile(options.file)
  } catch (error) {
    fileItem.detectError = resolveLocalErrorMessage(error)
  } finally {
    fileItem.status = 'pending'
    queuedUploads.value.push({
      fileItem,
      options: options as UploadRequestOptions
    })
    preparingUploads.value = Math.max(0, preparingUploads.value - 1)
    scheduleQueueProcessing()
  }
}

const importSingleFile = async (queuedItem: QueuedUploadItem) => {
  const { fileItem, options } = queuedItem
  const formData = new FormData()
  formData.append('file', options.file)

  try {
    const response: any = await request.post('/products/import', formData, {
      params: { dataType: requestType.value, platform: selectedPlatform.value, shopId: selectedShopId.value },
      headers: { 'Content-Type': 'multipart/form-data' }
    })

    if (response.code !== 200) {
      const message = response.message || '\u5bfc\u5165\u5931\u8d25'
      fileItem.errorMessage = message
      fileItem.status = 'failed'
      options.onError?.(createUploadError(message))
      return
    }

    const result = response.data as ImportResultVO
    fileItem.result = result
    if (result.uploadStatus === 'SUCCESS') {
      fileItem.status = 'success'
    } else if (result.uploadStatus === 'PARTIAL_SUCCESS') {
      fileItem.status = 'partial'
    } else {
      fileItem.status = 'failed'
    }
    options.onSuccess?.(result)
  } catch (error) {
    const message = await resolveRequestErrorMessage(error)
    fileItem.errorMessage = message
    fileItem.status = 'failed'
    options.onError?.(createUploadError(message))
  }
}

const processUploadQueue = async () => {
  if (batchProcessing.value) {
    return
  }
  if (preparingUploads.value > 0) {
    scheduleQueueProcessing()
    return
  }
  if (!queuedUploads.value.length) {
    uploadRef.value?.clearFiles()
    return
  }

  batchProcessing.value = true
  const processedInCurrentRound: ImportBatchFileItem[] = []

  try {
    queuedUploads.value.sort((left, right) => {
      const typeCompare = compareImportTypeOrder(left.fileItem.detectedType, right.fileItem.detectedType)
      if (typeCompare !== 0) {
        return typeCompare
      }
      return left.fileItem.sequence - right.fileItem.sequence
    })

    while (queuedUploads.value.length) {
      const currentItem = queuedUploads.value.shift()
      if (!currentItem) {
        break
      }

      currentItem.fileItem.processingOrder = processingSequence.value++
      currentItem.fileItem.status = 'uploading'
      currentUploadIndex.value = processedInCurrentRound.length
      await importSingleFile(currentItem)
      processedInCurrentRound.push(currentItem.fileItem)
    }
  } finally {
    batchProcessing.value = false
    currentUploadIndex.value = -1
    uploadRef.value?.clearFiles()

    const successfulFiles = processedInCurrentRound.filter((item) => isImportResponseSuccessful(item.result))
    if (successfulFiles.length > 0) {
      productListRef.value?.refreshList?.()
    }

    if (processedInCurrentRound.length > 0) {
      const successCount = successfulFiles.length
      const failedCount = processedInCurrentRound.length - successCount
      ElMessage({
        type: failedCount === 0 ? 'success' : successCount > 0 ? 'warning' : 'error',
        message:
          failedCount === 0
            ? `\u5df2\u5b8c\u6210 ${processedInCurrentRound.length} \u4e2a Excel \u6587\u4ef6\u5bfc\u5165`
            : `\u5df2\u5b8c\u6210 ${processedInCurrentRound.length} \u4e2a Excel \u6587\u4ef6\u5bfc\u5165\uff0c\u6210\u529f ${successCount} \u4e2a\uff0c\u5931\u8d25 ${failedCount} \u4e2a`
      })
    }
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

const resolveFileTypeLabel = (item: ImportBatchFileItem) => {
  if (item.result?.dataTypeLabel) {
    return item.result.dataTypeLabel
  }
  const rule = getImportDetectionRule(item.detectedType)
  return rule?.label || '\u672a\u8bc6\u522b'
}

const resolveFileTargetTable = (item: ImportBatchFileItem) => {
  if (item.result?.targetTable) {
    return item.result.targetTable
  }
  const rule = getImportDetectionRule(item.detectedType)
  return rule?.targetTable || '-'
}

const resolveFileStatusText = (item: ImportBatchFileItem) => {
  if (item.status === 'detecting') return '\u9884\u8bc6\u522b\u4e2d'
  if (item.status === 'pending') return '\u961f\u5217\u4e2d'
  if (item.status === 'uploading') return '\u5bfc\u5165\u4e2d'
  if (item.status === 'success') return '\u5bfc\u5165\u6210\u529f'
  if (item.status === 'partial') return '\u90e8\u5206\u6210\u529f'
  return '\u5bfc\u5165\u5931\u8d25'
}

const resolveFileStatusTagType = (item: ImportBatchFileItem) => {
  if (item.status === 'success') return 'success'
  if (item.status === 'partial') return 'warning'
  if (item.status === 'failed') return 'danger'
  return 'info'
}

const resolveFileDetectMode = (item: ImportBatchFileItem) => {
  if (item.result) {
    return item.result.autoDetected ? '\u8868\u5934\u81ea\u52a8\u8bc6\u522b' : '\u7528\u6237\u6307\u5b9a\u7c7b\u578b'
  }
  if (item.detectedType) {
    return '\u524d\u7aef\u9884\u5206\u7c7b'
  }
  if (item.detectError) {
    return '\u9884\u8bc6\u522b\u5931\u8d25'
  }
  return '\u5f85\u8bc6\u522b'
}

const resolveFileErrorText = (item: ImportBatchFileItem) => {
  if (item.errorMessage) {
    return item.errorMessage
  }
  if (item.result?.errors?.length) {
    return item.result.errors.join('\uff1b')
  }
  if (item.detectError) {
    return item.detectError
  }
  return ''
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

.file-result-list {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}

.file-result-card {
  padding: 16px;
  border-radius: 12px;
  background: #ffffff;
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.file-result-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 14px;
}

.file-result-title {
  display: grid;
  gap: 4px;
}

.file-result-title strong {
  color: #24324a;
  font-size: 15px;
}

.file-result-title span {
  color: #6b778a;
  font-size: 13px;
}

.file-result-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
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

.compact-error-box {
  margin-top: 12px;
}

.compact-error-box p {
  margin: 0;
  color: #7c2d12;
  line-height: 1.7;
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

  .file-result-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

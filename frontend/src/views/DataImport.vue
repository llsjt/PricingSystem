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
              <p>上传模板文件后会自动同步到商品管理列表。</p>
            </div>
          </div>

          <div class="import-layout">
            <div class="import-main">
              <div class="template-action">
                <el-button type="primary" class="template-btn" @click="handleDownloadTemplate">
                  <el-icon><Download /></el-icon>
                  <span>下载导入模板</span>
                </el-button>
              </div>

              <el-upload
                class="upload-box"
                drag
                :http-request="handleCustomUpload"
                :before-upload="beforeUpload"
                accept=".xlsx,.xls"
                :limit="1"
              >
                <el-icon class="upload-icon"><UploadFilled /></el-icon>
                <div class="upload-title">上传商品 Excel</div>
                <div class="upload-desc">支持 `.xlsx` 和 `.xls`，单文件不超过 10MB</div>
              </el-upload>
            </div>

            <div class="import-side">
              <div class="action-card">
                <strong>导入后自动刷新商品列表</strong>
                <span>导入完成后可切换到“商品管理”标签继续查询、编辑和批量操作。</span>
              </div>
              <div class="action-card warm">
                <strong>建议优先使用模板整理字段</strong>
                <span>可降低字段不匹配、格式错误等导入失败问题。</span>
              </div>
            </div>
          </div>

          <el-alert
            v-if="importResult"
            :title="importResult.title"
            :type="importResult.type"
            :description="importResult.message"
            show-icon
            class="upload-feedback"
          />
        </section>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Document, Download, UploadFilled } from '@element-plus/icons-vue'
import { ElMessage, type UploadProps } from 'element-plus'
import ProductList from './ProductList.vue'
import { downloadTemplate } from '../api/product'
import request from '../api/request'

const activeTab = ref('products')
const importResult = ref<any>(null)
const productListRef = ref<any>(null)

const beforeUpload: UploadProps['beforeUpload'] = (rawFile) => {
  if (rawFile.size / 1024 / 1024 > 10) {
    ElMessage.error('文件大小不能超过 10MB')
    return false
  }
  return true
}

const handleCustomUpload: UploadProps['httpRequest'] = async (options) => {
  const { file } = options
  const formData = new FormData()
  formData.append('file', file)

  try {
    const response: any = await request.post('/products/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })

    if (response.code === 200) {
      importResult.value = {
        title: '导入成功',
        type: 'success',
        message: response.data
      }
      ElMessage.success('导入完成')
      productListRef.value?.refreshList?.()
      return
    }

    importResult.value = {
      title: '导入失败',
      type: 'error',
      message: response.message
    }
    ElMessage.error(response.message || '导入失败')
  } catch (error: any) {
    importResult.value = {
      title: '上传失败',
      type: 'error',
      message: error.message || '网络异常'
    }
    ElMessage.error(`上传失败：${error.message || '网络异常'}`)
  }
}

const handleDownloadTemplate = async () => {
  try {
    const response: any = await downloadTemplate()
    const blob = new Blob([response], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = '商品导入模板.xlsx'
    link.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('模板下载成功')
  } catch (error: any) {
    ElMessage.error(`模板下载失败：${error.message || '未知错误'}`)
  }
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

.template-btn {
  --el-button-bg-color: #1f6feb;
  --el-button-border-color: #1f6feb;
  --el-button-hover-bg-color: #1558b5;
  --el-button-hover-border-color: #1558b5;
  --el-button-active-bg-color: #1558b5;
  --el-button-active-border-color: #1558b5;
  height: 40px;
  padding: 0 16px;
  border-radius: 10px;
  font-weight: 700;
  box-shadow: 0 8px 20px rgba(31, 111, 235, 0.28);
}

.import-layout {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(260px, 0.75fr);
  gap: 16px;
  align-items: stretch;
}

.import-main {
  display: grid;
  gap: 12px;
}

.template-action {
  display: flex;
  justify-content: flex-start;
}

.upload-box,
.upload-box :deep(.el-upload) {
  width: 100%;
}

.upload-box :deep(.el-upload-dragger) {
  width: 100%;
  min-height: 200px;
  border-radius: 10px;
  padding: 32px 18px;
  border: 1px dashed rgba(31, 111, 235, 0.28);
  background: linear-gradient(180deg, rgba(31, 111, 235, 0.04), rgba(255, 159, 67, 0.05));
}

.upload-icon {
  font-size: 40px;
  color: var(--brand);
}

.upload-title {
  margin-top: 10px;
  font-size: 18px;
  font-weight: 700;
}

.upload-desc {
  margin-top: 8px;
  color: var(--text-2);
  font-size: 14px;
}

.import-side {
  display: grid;
  gap: 14px;
}

.action-card {
  display: grid;
  gap: 8px;
  padding: 18px 20px;
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(31, 111, 235, 0.08), rgba(255, 255, 255, 0.95));
  border: 1px solid rgba(31, 111, 235, 0.12);
}

.action-card.warm {
  background: linear-gradient(180deg, rgba(255, 159, 67, 0.12), rgba(255, 255, 255, 0.95));
  border-color: rgba(255, 159, 67, 0.18);
}

.action-card strong,
.action-card span {
  margin: 0;
}

.action-card span {
  color: var(--text-2);
  line-height: 1.7;
}

.upload-feedback {
  margin-top: 16px;
}

@media (max-width: 1080px) {
  .import-layout {
    grid-template-columns: 1fr;
  }
}
</style>

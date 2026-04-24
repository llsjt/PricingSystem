<template>
  <div class="page-shell model-page">
    <section class="panel-card model-card">
      <div class="section-head">
        <div class="section-title">
          <h2>模型管理</h2>
          <p>为当前账号配置智能定价使用的大模型 API。支持 OpenAI 兼容接口。</p>
        </div>
      </div>

      <div class="model-summary">
        <div class="summary-item">
          <span>当前账号</span>
          <strong>{{ username }}</strong>
        </div>
        <div class="summary-item">
          <span>配置状态</span>
          <el-tag :type="hasStoredApiKey ? 'success' : 'warning'">
            {{ hasStoredApiKey ? '已配置 API Key' : '未配置 API Key' }}
          </el-tag>
        </div>
      </div>

      <el-form :model="llmForm" label-width="120px" class="llm-form">
        <el-form-item label="API Key">
          <el-input
            v-model="llmForm.apiKey"
            :placeholder="'请输入 API Key'"
            type="password"
            show-password
            clearable
          />
        </el-form-item>

        <el-form-item label="Base URL">
          <el-input
            v-model="llmForm.baseUrl"
            placeholder="例如 https://dashscope.aliyuncs.com/compatible-mode/v1"
            clearable
          />
        </el-form-item>

        <el-form-item label="模型名称">
          <el-input
            v-model="llmForm.model"
            placeholder="请输入你的模型名称"
            clearable
          />
        </el-form-item>

        <el-form-item>
          <div class="llm-actions">
            <el-button type="primary" :loading="saving" @click="handleSave">保存配置</el-button>
            <el-button :loading="verifying" @click="handleVerify">验证连接</el-button>
            <el-button v-if="hasStoredApiKey" type="danger" plain @click="handleDelete">删除配置</el-button>
          </div>
        </el-form-item>
      </el-form>
    </section>
  </div>
</template>

<script setup lang="ts">
// 模型管理页：负责维护用户个人大模型配置和连通性校验。

import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteLlmConfig, getLlmConfig, saveLlmConfig, verifyLlmConfig, type LlmConfigVO } from '../api/llmConfig'
import { useUserStore } from '../stores/user'
import { resolveRequestErrorMessage } from '../utils/error'
import { extractLlmConfig } from '../utils/llmConfigResponse'

const userStore = useUserStore()

const llmConfig = ref<LlmConfigVO | null>(null)
const llmForm = reactive({
  apiKey: '',
  baseUrl: '',
  model: ''
})
const saving = ref(false)
const verifying = ref(false)

const username = computed(() => userStore.username || 'User')
const hasStoredApiKey = computed(() => Boolean(llmConfig.value?.hasApiKey))

const applyConfigToForm = (config: LlmConfigVO | null) => {
  llmForm.apiKey = config?.apiKey || ''
  llmForm.baseUrl = config?.baseUrl || ''
  llmForm.model = config?.model || ''
}

const loadLlmConfig = async () => {
  try {
    const response = await getLlmConfig()
    llmConfig.value = extractLlmConfig(response)
    applyConfigToForm(llmConfig.value)
  } catch {
    llmConfig.value = null
    applyConfigToForm(null)
  }
}

const handleSave = async () => {
  if (!llmForm.baseUrl.trim() || !llmForm.model.trim()) {
    ElMessage.warning('请填写 Base URL 和模型名称')
    return
  }

  if (!hasStoredApiKey.value && !llmForm.apiKey.trim()) {
    ElMessage.warning('请填写 API Key')
    return
  }

  saving.value = true
  try {
    await saveLlmConfig({
      apiKey: llmForm.apiKey.trim(),
      baseUrl: llmForm.baseUrl.trim(),
      model: llmForm.model.trim()
    })
    ElMessage.success('配置已保存')
    await loadLlmConfig()
  } catch (error) {
    ElMessage.error(await resolveRequestErrorMessage(error, '保存配置失败'))
  } finally {
    saving.value = false
  }
}

const handleVerify = async () => {
  if (!llmForm.baseUrl.trim() || !llmForm.model.trim()) {
    ElMessage.warning('请先填写 Base URL 和模型名称')
    return
  }

  const apiKey = llmForm.apiKey.trim()
  if (!apiKey) {
    ElMessage.warning('请填写 API Key')
    return
  }

  verifying.value = true
  try {
    await verifyLlmConfig({
      apiKey,
      baseUrl: llmForm.baseUrl.trim(),
      model: llmForm.model.trim()
    })
    ElMessage.success('连接验证成功')
  } catch (error) {
    ElMessage.error(await resolveRequestErrorMessage(error, '连接验证失败'))
  } finally {
    verifying.value = false
  }
}

const handleDelete = async () => {
  try {
    await ElMessageBox.confirm('确定删除当前账号的大模型配置吗？删除后将无法使用智能定价功能。', '确认删除', {
      type: 'warning'
    })
    await deleteLlmConfig()
    llmConfig.value = null
    applyConfigToForm(null)
    ElMessage.success('配置已删除')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(await resolveRequestErrorMessage(error, '删除配置失败'))
    }
  }
}

onMounted(loadLlmConfig)
</script>

<style scoped>
.model-page {
  gap: 16px;
}

.model-card {
  width: min(100%, 980px);
  margin: 0 auto;
  padding: 22px;
}

.model-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-bottom: 18px;
}

.summary-item {
  min-width: 180px;
  display: grid;
  gap: 6px;
}

.summary-item span {
  font-size: 13px;
  color: var(--text-3);
}

.summary-item strong {
  font-size: 16px;
  color: var(--text-1);
}

.llm-form {
  width: min(100%, 760px);
}

.llm-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.field-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-3);
}

@media (max-width: 768px) {
  .model-card {
    padding: 18px;
  }

  .model-summary {
    flex-direction: column;
    align-items: flex-start;
  }

  .llm-form {
    width: 100%;
  }
}
</style>

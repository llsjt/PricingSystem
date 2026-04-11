<template>
  <div class="page-shell profile-page">
    <section class="panel-card profile-card">
      <div class="profile-header">
        <el-avatar :size="72" class="profile-avatar">{{ avatarText }}</el-avatar>
        <div class="profile-main">
          <h2>{{ username }}</h2>
          <div class="profile-tags">
            <el-tag :type="isAdmin ? 'danger' : 'success'">{{ isAdmin ? '管理员' : '普通用户' }}</el-tag>
          </div>
        </div>
      </div>

      <el-descriptions :column="1" border class="profile-descriptions">
        <el-descriptions-item label="用户名">{{ username }}</el-descriptions-item>
        <el-descriptions-item label="角色">{{ isAdmin ? '管理员' : '普通用户' }}</el-descriptions-item>
        <el-descriptions-item label="账号类型">{{ isAdmin ? '系统管理账号' : '业务操作账号' }}</el-descriptions-item>
        <el-descriptions-item label="最近登录">{{ loginTime }}</el-descriptions-item>
      </el-descriptions>

      <div class="profile-actions">
        <el-button @click="router.push('/import')">返回数据管理</el-button>
        <el-button type="danger" @click="handleLogout">退出登录</el-button>
      </div>
    </section>

    <section class="panel-card llm-config-card">
      <h3 class="section-title">大模型 API 配置</h3>
      <p class="section-desc">配置您的大模型 API 密钥，用于智能定价功能。支持 OpenAI 兼容接口。</p>

      <el-form :model="llmForm" label-width="120px" class="llm-form">
        <el-form-item label="API Key">
          <el-input
            v-model="llmForm.apiKey"
            :placeholder="llmConfig?.hasApiKey ? llmConfig.apiKeyPreview : '请输入 API Key'"
            type="password"
            show-password
            clearable
          />
          <div v-if="llmConfig?.hasApiKey" class="field-hint">已配置，留空则保留原 Key</div>
        </el-form-item>
        <el-form-item label="Base URL">
          <el-input v-model="llmForm.baseUrl" placeholder="例如 https://dashscope.aliyuncs.com/compatible-mode/v1" clearable />
        </el-form-item>
        <el-form-item label="模型名称">
          <el-input v-model="llmForm.model" placeholder="例如 qwen-plus" clearable />
        </el-form-item>
        <el-form-item>
          <div class="llm-actions">
            <el-button type="primary" :loading="saving" @click="handleSave">保存配置</el-button>
            <el-button :loading="verifying" @click="handleVerify">验证连接</el-button>
            <el-button v-if="llmConfig?.hasApiKey" type="danger" plain @click="handleDelete">删除配置</el-button>
          </div>
        </el-form-item>
      </el-form>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '../stores/user'
import { useShopStore } from '../stores/shop'
import { getLlmConfig, saveLlmConfig, deleteLlmConfig, verifyLlmConfig, type LlmConfigVO } from '../api/llmConfig'

const router = useRouter()
const userStore = useUserStore()
const shopStore = useShopStore()

userStore.syncFromSession()

const username = computed(() => userStore.username || 'User')
const loginTime = computed(() => userStore.loginTime || new Date().toLocaleString('zh-CN'))
const isAdmin = computed(() => userStore.isAdmin)
const avatarText = computed(() => username.value.trim().slice(0, 1).toUpperCase() || 'U')

const handleLogout = () => {
  shopStore.resetState()
  userStore.clearSession()
  ElMessage.success('已退出登录')
  router.push('/login')
}

const llmConfig = ref<LlmConfigVO | null>(null)
const llmForm = reactive({ apiKey: '', baseUrl: '', model: '' })
const saving = ref(false)
const verifying = ref(false)

const loadLlmConfig = async () => {
  try {
    const res = await getLlmConfig()
    llmConfig.value = res.data?.data || null
    if (llmConfig.value) {
      llmForm.baseUrl = llmConfig.value.baseUrl || ''
      llmForm.model = llmConfig.value.model || ''
    }
  } catch { /* ignore */ }
}

const handleSave = async () => {
  if (!llmForm.baseUrl.trim() || !llmForm.model.trim()) {
    ElMessage.warning('请填写 Base URL 和模型名称')
    return
  }
  if (!llmConfig.value?.hasApiKey && !llmForm.apiKey.trim()) {
    ElMessage.warning('请填写 API Key')
    return
  }
  saving.value = true
  try {
    const payload = {
      apiKey: llmForm.apiKey.trim() || '',
      baseUrl: llmForm.baseUrl.trim(),
      model: llmForm.model.trim()
    }
    await saveLlmConfig(payload)
    ElMessage.success('配置已保存')
    llmForm.apiKey = ''
    await loadLlmConfig()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '保存失败')
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
  if (!apiKey && !llmConfig.value?.hasApiKey) {
    ElMessage.warning('请填写 API Key')
    return
  }
  if (!apiKey) {
    ElMessage.warning('验证需要输入完整的 API Key')
    return
  }
  verifying.value = true
  try {
    await verifyLlmConfig({ apiKey, baseUrl: llmForm.baseUrl.trim(), model: llmForm.model.trim() })
    ElMessage.success('连接验证成功')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.message || '连接验证失败')
  } finally {
    verifying.value = false
  }
}

const handleDelete = async () => {
  try {
    await ElMessageBox.confirm('确定删除大模型配置？删除后将无法使用智能定价功能。', '确认删除', { type: 'warning' })
    await deleteLlmConfig()
    llmConfig.value = null
    llmForm.apiKey = ''
    llmForm.baseUrl = ''
    llmForm.model = ''
    ElMessage.success('配置已删除')
  } catch { /* cancelled */ }
}

onMounted(loadLlmConfig)
</script>

<style scoped>
.profile-page {
  gap: 14px;
}

.profile-card {
  padding: 20px;
  width: min(100%, 980px);
  margin: 0 auto;
}

.profile-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 18px;
}

.profile-avatar {
  background: linear-gradient(135deg, #1f6feb, #4a82b0);
  color: #fff;
  font-size: 28px;
  font-weight: 700;
}

.profile-main {
  display: grid;
  gap: 8px;
}

.profile-main h2 {
  margin: 0;
  font-size: 28px;
}

.profile-tags {
  display: flex;
  gap: 8px;
}

.profile-descriptions {
  width: min(100%, 760px);
  margin-bottom: 18px;
}

.profile-descriptions :deep(.el-descriptions__table) {
  width: 100%;
  table-layout: fixed;
}

.profile-descriptions :deep(.el-descriptions__label.is-bordered-label) {
  width: 180px;
  font-size: 16px;
  font-weight: 600;
  padding: 12px 14px;
}

.profile-descriptions :deep(.el-descriptions__content.is-bordered-content) {
  font-size: 16px;
  padding: 12px 14px;
}

.profile-actions {
  width: min(100%, 760px);
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.llm-config-card {
  padding: 20px;
  width: min(100%, 980px);
  margin: 0 auto;
}

.section-title {
  font-size: 20px;
  font-weight: 600;
  margin: 0 0 6px;
}

.section-desc {
  color: #8b949e;
  font-size: 14px;
  margin: 0 0 18px;
}

.llm-form {
  width: min(100%, 760px);
}

.llm-actions {
  display: flex;
  gap: 10px;
}

.field-hint {
  color: #8b949e;
  font-size: 12px;
  margin-top: 4px;
}

@media (max-width: 768px) {
  .profile-card {
    padding: 16px;
  }

  .profile-header {
    align-items: flex-start;
  }

  .profile-main h2 {
    font-size: 24px;
  }

  .profile-actions {
    width: 100%;
    justify-content: stretch;
  }

  .profile-actions :deep(.el-button) {
    flex: 1;
  }

  .profile-descriptions {
    width: 100%;
  }

  .profile-descriptions :deep(.el-descriptions__label.is-bordered-label) {
    width: 120px;
    font-size: 14px;
    padding: 10px 12px;
  }

  .profile-descriptions :deep(.el-descriptions__content.is-bordered-content) {
    font-size: 14px;
    padding: 10px 12px;
  }
}
</style>

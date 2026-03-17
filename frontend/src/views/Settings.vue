<template>
  <div class="page-shell settings-page">
    <section class="panel-card settings-hero">
      <div class="section-title">
        <h2>系统设置</h2>
        <p>集中维护模型接入与默认推理配置，便于管理员快速完成环境准备。</p>
      </div>
      <div class="metric-grid compact-metrics">
        <article class="metric-card">
          <div class="metric-label">配置项</div>
          <div class="metric-value">2</div>
          <div class="metric-hint">仅保留运行所需的核心设置</div>
        </article>
        <article class="metric-card">
          <div class="metric-label">默认模型</div>
          <div class="metric-value small">{{ configForm.agentModel }}</div>
          <div class="metric-hint">用于多 Agent 推理的默认模型</div>
        </article>
        <article class="metric-card">
          <div class="metric-label">密钥状态</div>
          <div class="metric-value small">{{ configForm.dashscopeApiKey ? '已配置' : '未配置' }}</div>
          <div class="metric-hint">保存后立即用于后续任务</div>
        </article>
      </div>
    </section>

    <div class="responsive-two">
      <section class="panel-card form-panel" v-loading="loading">
        <div class="section-head">
          <div class="section-title">
            <h3>核心配置</h3>
            <p>减少无关选项，便于管理员快速确认系统是否可用。</p>
          </div>
        </div>

        <el-form :model="configForm" label-position="top" class="settings-form">
          <el-form-item label="DashScope API Key">
            <el-input
              v-model="configForm.dashscopeApiKey"
              type="password"
              show-password
              placeholder="请输入 DashScope API Key"
            />
          </el-form-item>

          <el-form-item label="Agent 默认模型">
            <el-select v-model="configForm.agentModel" placeholder="请选择默认模型">
              <el-option label="qwen-plus" value="qwen-plus" />
              <el-option label="qwen-max" value="qwen-max" />
            </el-select>
          </el-form-item>

          <div class="toolbar-actions">
            <el-button type="primary" :loading="loading" @click="saveConfig">保存配置</el-button>
          </div>
        </el-form>
      </section>

      <section class="panel-card guide-panel">
        <div class="section-head">
          <div class="section-title">
            <h3>配置说明</h3>
            <p>为管理员提供最少但必要的操作指引。</p>
          </div>
        </div>

        <div class="tips-list">
          <article class="tip-item">
            <strong>API Key</strong>
            <span>用于连接模型服务。建议由管理员统一维护，避免在用户端分散配置。</span>
          </article>
          <article class="tip-item">
            <strong>默认模型</strong>
            <span>将作为数据分析、市场情报、风险控制和经理协调的默认推理模型。</span>
          </article>
          <article class="tip-item">
            <strong>保存生效</strong>
            <span>保存后新启动的智能定价任务会直接读取最新配置，无需额外刷新服务。</span>
          </article>
        </div>

        <div class="summary-card">
          <div class="summary-title">当前配置摘要</div>
          <div class="summary-line">默认模型：{{ configForm.agentModel }}</div>
          <div class="summary-line">
            密钥状态：{{ configForm.dashscopeApiKey ? '已录入，可直接发起任务' : '尚未录入，请先完成配置' }}
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../api/request'

const loading = ref(false)

const configForm = reactive({
  dashscopeApiKey: '',
  agentModel: 'qwen-plus'
})

const fetchConfig = async () => {
  loading.value = true
  try {
    const res: any = await request.get('/config/all')
    if (res.code === 200 && res.data) {
      configForm.dashscopeApiKey = res.data.DASHSCOPE_API_KEY || ''
      configForm.agentModel = res.data.AGENT_MODEL || 'qwen-plus'
      return
    }
    ElMessage.error(res.message || '获取配置失败')
  } catch {
    ElMessage.error('获取配置失败')
  } finally {
    loading.value = false
  }
}

const saveConfig = async () => {
  loading.value = true
  try {
    const res: any = await request.post('/config/update', {
      DASHSCOPE_API_KEY: configForm.dashscopeApiKey,
      AGENT_MODEL: configForm.agentModel
    })
    if (res.code === 200) {
      ElMessage.success('配置已保存')
      return
    }
    ElMessage.error(res.message || '保存失败')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchConfig()
})
</script>

<style scoped>
.settings-page {
  gap: 20px;
}

.compact-metrics {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.settings-form {
  display: grid;
  gap: 8px;
}

@media (max-width: 1200px) {
  .compact-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .compact-metrics {
    grid-template-columns: 1fr;
  }
}
</style>

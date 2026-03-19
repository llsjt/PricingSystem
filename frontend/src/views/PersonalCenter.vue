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
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const router = useRouter()
const username = ref(localStorage.getItem('username') || 'User')
const loginTime = ref(localStorage.getItem('loginTime') || new Date().toLocaleString('zh-CN'))

const isAdmin = computed(() => username.value === 'admin')
const avatarText = computed(() => username.value.trim().slice(0, 1).toUpperCase() || 'U')

const handleLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('username')
  ElMessage.success('已退出登录')
  router.push('/login')
}
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

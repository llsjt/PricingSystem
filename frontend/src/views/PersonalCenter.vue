<template>
  <div class="personal-center-container">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>个人中心</span>
        </div>
      </template>
      <div class="user-info">
        <el-avatar :size="100" src="https://cube.elemecdn.com/0/88/03b0d39583f48206768a7534e55bcpng.png" />
        <div class="info-content">
          <h2>{{ username }}</h2>
          <el-tag :type="isAdmin ? 'danger' : 'success'">{{ isAdmin ? '管理员' : '普通用户' }}</el-tag>
          <p class="role-desc">
            {{ isAdmin ? '拥有系统最高权限，可管理用户和所有数据。' : '普通用户，可进行数据导入和定价决策。' }}
          </p>
        </div>
      </div>
      
      <el-divider />
      
      <el-descriptions title="详细信息" :column="1" border>
        <el-descriptions-item label="用户名">{{ username }}</el-descriptions-item>
        <el-descriptions-item label="当前状态">在线</el-descriptions-item>
        <el-descriptions-item label="权限等级">{{ isAdmin ? 'Level 1 (Admin)' : 'Level 2 (User)' }}</el-descriptions-item>
      </el-descriptions>

      <div class="actions" style="margin-top: 30px; text-align: center;">
        <el-button type="danger" @click="handleLogout">退出登录</el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const router = useRouter()
const username = ref(localStorage.getItem('username') || 'User')

const isAdmin = computed(() => {
  return username.value === 'admin'
})

const handleLogout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('username')
  ElMessage.success('已退出登录')
  router.push('/login')
}
</script>

<style scoped>
.personal-center-container {
  padding: 20px;
  max-width: 800px;
  margin: 0 auto;
}
.user-info {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
}
.info-content {
  margin-left: 30px;
}
.role-desc {
  margin-top: 10px;
  color: #909399;
  font-size: 14px;
}
</style>

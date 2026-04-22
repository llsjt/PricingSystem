<script setup lang="ts">
import { ArrowDown, Menu, UserFilled } from '@element-plus/icons-vue'

defineProps<{
  pageTitle: string
  username: string
  isAdmin: boolean
}>()

const emit = defineEmits<{
  command: [command: string]
  toggleSidebar: []
}>()
</script>

<template>
  <header class="topbar">
    <div class="topbar-left">
      <el-button class="menu-button" circle @click="emit('toggleSidebar')">
        <el-icon><Menu /></el-icon>
      </el-button>
      <div class="page-meta">
        <h1 class="page-title">{{ pageTitle }}</h1>
      </div>
    </div>

    <div class="topbar-right">
      <el-dropdown trigger="click" @command="(command: string) => emit('command', command)">
        <button type="button" class="user-entry">
          <el-avatar :size="38" :icon="UserFilled" />
          <div class="user-copy">
            <strong>{{ username }}</strong>
            <span>{{ isAdmin ? '管理员' : '普通用户' }}</span>
          </div>
          <el-icon><ArrowDown /></el-icon>
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">个人中心</el-dropdown-item>
            <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </header>
</template>

<style scoped>
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  min-height: 54px;
  padding: 0 18px;
}

.topbar-left,
.topbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.menu-button {
  border: 1px solid rgba(226, 232, 240, 0.8);
  background: rgba(255, 255, 255, 0.5);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
  transition: all 0.2s;
}

.menu-button:hover {
  background: #ffffff;
  border-color: #cbd5e1;
  transform: translateY(-1px);
}

.page-meta {
  display: flex;
  align-items: center;
  margin-left: 4px;
}

.page-title {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
  color: #0f172a;
  letter-spacing: 0.2px;
}

.user-entry {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid var(--line-soft);
  background: rgba(255, 255, 255, 0.85);
  cursor: pointer;
  color: #333639;
  transition: background 0.2s;
}

.user-entry:hover {
  background: #f0f2f5;
}

.user-copy {
  display: grid;
  gap: 2px;
  text-align: left;
}

.user-copy strong {
  font-size: 15px;
}

.user-copy span {
  font-size: 13px;
  color: var(--text-3);
}

@media (max-width: 960px) {
  .topbar {
    min-height: 52px;
    padding: 8px 12px;
  }
}

@media (max-width: 640px) {
  .topbar-left {
    min-width: 0;
  }

  .page-meta {
    min-width: 0;
  }

  .user-copy {
    display: none;
  }
}
</style>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowDown,
  Close,
  DataLine,
  Document,
  Files,
  Menu,
  User,
  UserFilled
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

interface NavItem {
  path: string
  title: string
  desc: string
  icon: any
  adminOnly?: boolean
}

const router = useRouter()
const route = useRoute()

const username = ref(localStorage.getItem('username') || 'User')
const isSidebarCollapsed = ref(false)
const mobileMenuVisible = ref(false)
const isMobile = ref(false)

const navItems: NavItem[] = [
  {
    path: '/import',
    title: '数据管理',
    desc: '商品管理与批量导入',
    icon: Document
  },
  {
    path: '/lab',
    title: '智能定价',
    desc: '任务配置与结果分析',
    icon: DataLine
  },
  {
    path: '/archive',
    title: '决策档案',
    desc: '任务记录与复盘报表',
    icon: Files
  },
  {
    path: '/profile',
    title: '个人中心',
    desc: '查看个人信息与账号状态',
    icon: UserFilled
  },
  {
    path: '/user',
    title: '用户管理',
    desc: '账号维护与权限管理',
    icon: User,
    adminOnly: true
  }
]

const isAdmin = computed(() => username.value === 'admin')
const visibleNavItems = computed(() => navItems.filter((item) => !item.adminOnly || isAdmin.value))
const currentNav = computed(() => visibleNavItems.value.find((item) => route.path.startsWith(item.path)))
const pageTitle = computed(() => currentNav.value?.title || String(route.meta.title || '智能定价系统'))
const pageDesc = computed(() => currentNav.value?.desc || '多 Agent 协同定价工作台')

const updateViewportState = () => {
  isMobile.value = window.innerWidth <= 960
  if (isMobile.value) {
    isSidebarCollapsed.value = false
  }
}

const navigateTo = (path: string) => {
  router.push(path)
  if (isMobile.value) {
    mobileMenuVisible.value = false
  }
}

const toggleSidebar = () => {
  if (isMobile.value) {
    mobileMenuVisible.value = !mobileMenuVisible.value
    return
  }
  isSidebarCollapsed.value = !isSidebarCollapsed.value
}

const handleCommand = (command: string) => {
  if (command === 'profile') {
    navigateTo('/profile')
    return
  }

  if (command === 'logout') {
    localStorage.removeItem('username')
    ElMessage.success('已退出登录')
    router.push('/login')
  }
}

watch(
  () => route.path,
  () => {
    if (isMobile.value) {
      mobileMenuVisible.value = false
    }
  }
)

onMounted(() => {
  updateViewportState()
  window.addEventListener('resize', updateViewportState)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateViewportState)
})
</script>

<template>
  <div class="layout-shell">
    <transition name="fade-mask">
      <div v-if="mobileMenuVisible && isMobile" class="mobile-mask" @click="mobileMenuVisible = false" />
    </transition>

    <aside
      class="sidebar"
      :class="{
        collapsed: isSidebarCollapsed && !isMobile,
        mobile: isMobile,
        visible: mobileMenuVisible && isMobile
      }"
    >
      <el-button
        v-if="isMobile"
        circle
        text
        class="mobile-close"
        @click="mobileMenuVisible = false"
      >
        <el-icon><Close /></el-icon>
      </el-button>

      <nav class="nav-list">
        <button
          v-for="item in visibleNavItems"
          :key="item.path"
          type="button"
          class="nav-item"
          :class="{ active: route.path.startsWith(item.path) }"
          @click="navigateTo(item.path)"
        >
          <span class="nav-icon">
            <el-icon><component :is="item.icon" /></el-icon>
          </span>
          <transition name="fade-slide">
            <span v-if="!isSidebarCollapsed || isMobile" class="nav-copy">
              <strong>{{ item.title }}</strong>
            </span>
          </transition>
        </button>
      </nav>
    </aside>

    <div class="main-shell">
      <header class="topbar">
        <div class="topbar-left">
          <el-button class="menu-button" circle @click="toggleSidebar">
            <el-icon><Menu /></el-icon>
          </el-button>
          <div class="page-meta">
            <div class="crumb-line">
              <span>首页</span>
              <span>/</span>
              <span>{{ pageTitle }}</span>
            </div>
            <h1>{{ pageTitle }}</h1>
            <p>{{ pageDesc }}</p>
          </div>
        </div>

        <div class="topbar-right">
          <el-dropdown trigger="click" @command="handleCommand">
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

      <main class="content-shell">
        <div class="content-inner">
          <router-view />
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout-shell {
  min-height: 100vh;
  display: flex;
  width: 100%;
  max-width: 100%;
  overflow: hidden;
  background: transparent;
}

.sidebar {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  gap: 20px;
  width: 260px;
  min-width: 260px;
  height: auto;
  min-height: 100vh;
  padding: 24px 18px 18px;
  background: linear-gradient(180deg, #2f5f93 0%, #3b72a7 52%, #4a82b0 100%);
  border-right: 1px solid rgba(255, 255, 255, 0.14);
  box-shadow: 20px 0 40px rgba(34, 70, 110, 0.14);
  transition: width 0.28s ease, min-width 0.28s ease, transform 0.28s ease;
  z-index: 20;
}

.sidebar.collapsed {
  width: 84px;
  min-width: 84px;
}

.mobile-close {
  margin-left: auto;
  color: #fff;
}

.nav-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.nav-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 14px;
  border: 0;
  border-radius: 20px;
  background: transparent;
  color: rgba(255, 255, 255, 0.84);
  cursor: pointer;
  transition: transform 0.18s ease, background 0.18s ease, color 0.18s ease;
  text-align: left;
}

.nav-item:hover {
  transform: translateX(2px);
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
}

.nav-item.active {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.26), rgba(105, 171, 227, 0.32));
  color: #fff;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.14);
}

.nav-icon {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.18);
  font-size: 18px;
  flex-shrink: 0;
}

.nav-copy {
  display: flex;
  overflow: hidden;
}

.nav-copy strong {
  font-size: 14px;
  font-weight: 700;
}

.main-shell {
  flex: 1;
  min-width: 0;
  max-width: 100%;
  display: flex;
  flex-direction: column;
  overflow-x: hidden;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  padding: 18px 28px;
  backdrop-filter: blur(14px);
  background: rgba(248, 251, 255, 0.86);
  border-bottom: 1px solid rgba(14, 30, 37, 0.07);
}

.topbar-left,
.topbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.menu-button {
  border: 0;
  background: var(--surface-1);
  box-shadow: var(--shadow-card);
}

.page-meta {
  display: grid;
  gap: 4px;
}

.crumb-line {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-3);
}

.page-meta h1 {
  margin: 0;
  font-size: 26px;
  line-height: 1.1;
}

.page-meta p {
  margin: 0;
  color: var(--text-2);
  font-size: 14px;
}

.user-entry {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px 8px 8px;
  border-radius: 999px;
  border: 1px solid var(--line-soft);
  background: var(--surface-1);
  box-shadow: var(--shadow-card);
  cursor: pointer;
  color: var(--text-1);
}

.user-copy {
  display: grid;
  gap: 2px;
  text-align: left;
}

.user-copy strong {
  font-size: 14px;
}

.user-copy span {
  font-size: 12px;
  color: var(--text-3);
}

.content-shell {
  padding: 22px 28px 34px;
  overflow-x: hidden;
}

.content-inner {
  width: min(100%, var(--content-width));
  max-width: 100%;
  min-width: 0;
  margin: 0 auto;
}

.mobile-mask {
  position: fixed;
  inset: 0;
  background: rgba(12, 24, 29, 0.42);
  z-index: 18;
}

.fade-mask-enter-active,
.fade-mask-leave-active,
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.24s ease;
}

.fade-mask-enter-from,
.fade-mask-leave-to {
  opacity: 0;
}

.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateX(-8px);
}

@media (max-width: 960px) {
  .sidebar {
    position: fixed;
    inset: 0 auto 0 0;
    transform: translateX(-100%);
    width: min(76vw, 288px);
    min-width: min(76vw, 288px);
    height: 100vh;
    min-height: 100vh;
  }

  .sidebar.visible {
    transform: translateX(0);
  }

  .topbar {
    padding: 16px 16px 18px;
  }

  .content-shell {
    padding: 14px 12px 22px;
  }

  .page-meta h1 {
    font-size: 22px;
  }

  .page-meta p {
    display: none;
  }

  .user-copy {
    display: none;
  }
}

@media (max-width: 640px) {
  .topbar-left {
    min-width: 0;
  }

  .page-meta {
    min-width: 0;
  }

  .crumb-line {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .page-meta h1 {
    font-size: 20px;
  }
}
</style>

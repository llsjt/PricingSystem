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
const appName = '智能定价平台'
const appSubtitle = '多 Agent 协同工作台'

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
    desc: '查看个人信息与账号管理',
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

      <div class="sidebar-brand">
        <transition name="fade-slide">
          <div v-if="!isSidebarCollapsed || isMobile" class="brand-copy">
            <strong>{{ appName }}</strong>
            <span>{{ appSubtitle }}</span>
          </div>
        </transition>
      </div>

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
  background: linear-gradient(180deg, #edf3fa 0%, #f6f9fd 100%);
}

.sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  display: flex;
  flex-direction: column;
  gap: 18px;
  width: 286px;
  min-width: 286px;
  height: 100vh;
  min-height: 100vh;
  padding: 18px 16px 16px;
  background:
    radial-gradient(circle at 18% 10%, rgba(109, 170, 238, 0.18), transparent 36%),
    linear-gradient(180deg, #162b45 0%, #1b3757 52%, #1f3f63 100%);
  border-right: 1px solid rgba(156, 197, 241, 0.22);
  box-shadow: 18px 0 40px rgba(11, 28, 47, 0.32);
  transition: width 0.2s ease-in-out, min-width 0.2s ease-in-out, transform 0.2s ease-in-out;
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

.sidebar-brand {
  display: block;
  padding: 8px 8px 18px;
  border-bottom: 1px solid rgba(198, 226, 255, 0.24);
}

.brand-copy {
  position: relative;
  display: grid;
  gap: 8px;
  padding: 16px 14px 14px;
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(88, 180, 255, 0.5), rgba(57, 124, 220, 0.4));
  border: 1px solid rgba(201, 234, 255, 0.56);
  backdrop-filter: blur(10px);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.5),
    inset 0 -1px 0 rgba(9, 40, 82, 0.2),
    0 14px 30px rgba(8, 32, 60, 0.28);
}

.brand-copy::after {
  content: "";
  position: absolute;
  left: 14px;
  right: 14px;
  top: 0;
  height: 45%;
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(235, 249, 255, 0.34), rgba(235, 249, 255, 0));
  filter: blur(0.2px);
  pointer-events: none;
}

.brand-copy strong {
  display: block;
  font-size: 34px;
  line-height: 1.02;
  color: #f6fcff;
  font-weight: 700;
  letter-spacing: 0.005em;
  text-shadow:
    0 2px 12px rgba(8, 30, 54, 0.3),
    0 0 0.8px rgba(228, 248, 255, 0.8);
  white-space: nowrap;
  overflow: visible;
  text-overflow: clip;
  position: relative;
  z-index: 1;
}

.brand-copy span {
  font-size: 13px;
  color: rgba(238, 249, 255, 0.94);
  font-weight: 600;
  letter-spacing: 0.02em;
  white-space: nowrap;
  overflow: visible;
  text-overflow: clip;
  position: relative;
  z-index: 1;
}

.sidebar.collapsed .sidebar-brand {
  justify-content: center;
  padding-left: 0;
  padding-right: 0;
}

.nav-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 2px;
}

.nav-item {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 0;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.05);
  color: rgba(238, 246, 255, 0.86);
  cursor: pointer;
  transition: transform 0.2s ease-in-out, background 0.2s ease-in-out, color 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
  text-align: left;
}

.nav-item:hover {
  transform: translateX(2px);
  background: linear-gradient(90deg, rgba(116, 184, 249, 0.36), rgba(83, 147, 226, 0.26));
  color: #fff;
  box-shadow: 0 8px 16px rgba(8, 30, 54, 0.24);
}

.nav-item.active {
  background: linear-gradient(90deg, rgba(160, 218, 255, 0.48), rgba(122, 183, 247, 0.34));
  color: #ffffff;
  box-shadow: inset 0 0 0 1px rgba(220, 242, 255, 0.58), 0 10px 18px rgba(8, 30, 54, 0.24);
}

.nav-icon {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.16);
  font-size: 17px;
  flex-shrink: 0;
  transition: transform 0.2s ease-in-out, background 0.2s ease-in-out;
}

.nav-item:hover .nav-icon,
.nav-item.active .nav-icon {
  transform: scale(1.03);
  background: rgba(226, 244, 255, 0.34);
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
  width: calc(100% - 286px);
  margin-left: 286px;
  border-left: 1px solid rgba(24, 42, 58, 0.08);
  background: rgba(255, 255, 255, 0.58);
  transition: margin-left 0.2s ease-in-out, width 0.2s ease-in-out;
}

.sidebar.collapsed ~ .main-shell {
  width: calc(100% - 84px);
  margin-left: 84px;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 16px 24px;
  backdrop-filter: blur(14px);
  background: linear-gradient(90deg, rgba(249, 252, 255, 0.9), rgba(246, 250, 255, 0.86));
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
  gap: 8px;
}

.page-meta h1 {
  margin: 0;
  font-size: 26px;
  line-height: 1.1;
}

.page-meta p {
  margin: 0;
  width: fit-content;
  max-width: 100%;
  padding: 4px 10px;
  border-radius: 8px;
  color: #35577c;
  background: rgba(31, 111, 235, 0.1);
  border: 1px solid rgba(31, 111, 235, 0.15);
  font-size: 14px;
  font-weight: 500;
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
  padding: 24px 24px 32px;
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
  transition: all 0.2s ease-in-out;
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
    width: min(82vw, 330px);
    min-width: min(82vw, 330px);
    height: 100vh;
    min-height: 100vh;
  }

  .sidebar.visible {
    transform: translateX(0);
  }

  .main-shell {
    width: 100%;
    margin-left: 0;
    border-left: 0;
    background: transparent;
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

  .page-meta h1 {
    font-size: 20px;
  }
}
</style>

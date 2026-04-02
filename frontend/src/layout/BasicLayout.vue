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

interface OpenTab {
  path: string
  title: string
  name?: string
}

const router = useRouter()
const route = useRoute()

const username = ref(localStorage.getItem('username') || 'User')
const isSidebarCollapsed = ref(false)
const mobileMenuVisible = ref(false)
const isMobile = ref(false)
const appSubtitle = 'Excel 导入与定价协作'
const appName = '智能定价平台'

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
const openTabs = ref<OpenTab[]>([])
const cacheNames = computed(() =>
  openTabs.value
    .map((tab) => tab.name)
    .filter((name): name is string => Boolean(name))
)

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

const upsertTab = (tab: OpenTab) => {
  const index = openTabs.value.findIndex((item) => item.path === tab.path)
  if (index >= 0) {
    openTabs.value[index] = { ...openTabs.value[index], ...tab }
    return
  }
  openTabs.value.push(tab)
}

const ensureCurrentTab = () => {
  if (route.path === '/login') return
  const title = currentNav.value?.title || String(route.meta.title || route.name || route.path)
  const name = typeof route.name === 'string' ? route.name : undefined
  upsertTab({
    path: route.path,
    title,
    name
  })
}

const openTab = (path: string) => {
  if (route.path === path) return
  navigateTo(path)
}

const closeTab = (path: string) => {
  if (openTabs.value.length <= 1) return
  const index = openTabs.value.findIndex((item) => item.path === path)
  if (index < 0) return

  const isActive = route.path === path
  openTabs.value.splice(index, 1)

  if (!isActive) return

  const fallback = openTabs.value[index] || openTabs.value[index - 1] || openTabs.value[0]
  if (fallback) {
    navigateTo(fallback.path)
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
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    localStorage.removeItem('isAdmin')
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
    ensureCurrentTab()
  }
)

watch(
  visibleNavItems,
  () => {
    const allowedPaths = visibleNavItems.value.map((item) => item.path)
    openTabs.value = openTabs.value.filter((tab) => allowedPaths.some((path) => tab.path.startsWith(path)))
    ensureCurrentTab()
  },
  { deep: true }
)

onMounted(() => {
  updateViewportState()
  window.addEventListener('resize', updateViewportState)
  ensureCurrentTab()
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
      <div class="header-wrapper">
        <header class="topbar">
          <div class="topbar-left">
            <el-button class="menu-button" circle @click="toggleSidebar">
              <el-icon><Menu /></el-icon>
            </el-button>
            <div class="page-meta">
              <el-breadcrumb separator="/">
                <el-breadcrumb-item :to="{ path: '/' }">{{ appName }}</el-breadcrumb-item>
                <el-breadcrumb-item>
                  <span class="page-title">{{ pageTitle }}</span>
                </el-breadcrumb-item>
              </el-breadcrumb>
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

        <div class="tabs-shell" v-if="openTabs.length">
          <div class="tabs-track">
            <button
              v-for="tab in openTabs"
              :key="tab.path"
              type="button"
              class="tab-item"
              :class="{ active: route.path === tab.path }"
              @click="openTab(tab.path)"
            >
              <span class="tab-title">{{ tab.title }}</span>
              <span
                v-if="openTabs.length > 1"
                class="tab-close"
                role="button"
                tabindex="0"
                @click.stop="closeTab(tab.path)"
                @keydown.enter.prevent="closeTab(tab.path)"
                @keydown.space.prevent="closeTab(tab.path)"
              >
                <el-icon><Close /></el-icon>
              </span>
            </button>
          </div>
        </div>
      </div>

      <main class="content-shell">
        <div class="content-inner">
          <router-view v-slot="{ Component, route: activeRoute }">
            <keep-alive :include="cacheNames">
              <component :is="Component" :key="activeRoute.path" />
            </keep-alive>
          </router-view>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout-shell {
  height: 100vh;
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
  height: 100vh;
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

.header-wrapper {
  position: sticky;
  top: 0;
  z-index: 20;
  flex-shrink: 0;
  background: #ffffff;
  box-shadow: 0 2px 8px rgba(0, 21, 41, 0.04);
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  height: 52px;
  padding: 0 16px;
  border-bottom: 1px solid rgba(220, 226, 232, 0.6);
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
  display: flex;
  align-items: center;
  margin-left: 8px;
}

.page-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #1f2d3d;
}

.user-entry {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid transparent;
  background: transparent;
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
  font-size: 14px;
}

.user-copy span {
  font-size: 12px;
  color: var(--text-3);
}

.content-shell {
  flex: 1;
  min-height: 0;
  padding: 24px 24px 32px;
  overflow-x: hidden;
  overflow-y: auto;
}

.tabs-shell {
  padding: 0 16px;
  background: #f4f7f9;
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.02);
  border-bottom: 1px solid #e1e4e8;
}

.tabs-track {
  display: flex;
  gap: 4px;
  overflow-x: auto;
  padding: 6px 0 0;
}

.tabs-track::-webkit-scrollbar {
  height: 0;
}

.tab-item {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 32px;
  max-width: 220px;
  padding: 0 16px;
  border: 1px solid transparent;
  border-bottom: none;
  border-radius: 6px 6px 0 0;
  background: #e2e8f0;
  color: #64748b;
  cursor: pointer;
  position: relative;
  transition: all 0.2s cubic-bezier(0.645, 0.045, 0.355, 1);
}

.tab-item:hover {
  background: #cbd5e1;
  color: #334155;
}

.tab-item.active {
  background: #ffffff;
  color: #1f6feb;
  border: 1px solid #e1e4e8;
  border-bottom: none;
}

.tab-item.active::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 2px;
  background: #ffffff;
}

.tab-title {
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tab-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  min-width: 18px;
  height: 18px;
  margin-left: 6px;
  border-radius: 50%;
  color: #516d89;
}

.tab-close:hover {
  color: #1f6feb;
  background: rgba(31, 111, 235, 0.1);
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
    padding: 8px 12px;
  }

  .content-shell {
    padding: 14px 12px 22px;
  }

  .tabs-shell {
    padding: 0 12px;
  }

  .page-title {
    font-size: 14px;
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
}
</style>

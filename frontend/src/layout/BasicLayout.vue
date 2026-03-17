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
  Setting,
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
    desc: '商品、导入和趋势分析',
    icon: Document
  },
  {
    path: '/lab',
    title: '智能定价',
    desc: '任务配置、执行和结果反馈',
    icon: DataLine
  },
  {
    path: '/archive',
    title: '决策档案',
    desc: '历史记录、复盘和报表',
    icon: Files
  },
  {
    path: '/user',
    title: '用户管理',
    desc: '账号维护与管理员操作',
    icon: User,
    adminOnly: true
  },
  {
    path: '/settings',
    title: '系统设置',
    desc: '模型与 API 配置',
    icon: Setting
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
  if (command === 'settings') {
    navigateTo('/settings')
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
      <div class="brand-block">
        <div class="brand-mark">{{ isSidebarCollapsed && !isMobile ? 'AI' : 'AI' }}</div>
        <transition name="fade-slide">
          <div v-if="!isSidebarCollapsed || isMobile" class="brand-copy">
            <strong>智能定价系统</strong>
            <span>商品管理与多 Agent 决策平台</span>
          </div>
        </transition>
        <el-button
          v-if="isMobile"
          circle
          text
          class="mobile-close"
          @click="mobileMenuVisible = false"
        >
          <el-icon><Close /></el-icon>
        </el-button>
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
              <small>{{ item.desc }}</small>
            </span>
          </transition>
        </button>
      </nav>

      <div class="sidebar-footer" v-if="!isSidebarCollapsed || isMobile">
        <div class="footer-tip">今日建议</div>
        <div class="footer-card">
          <strong>先导入数据，再配置任务</strong>
          <span>约束条件越明确，Agent 输出越稳定。</span>
        </div>
      </div>
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
          <div class="status-chip">
            <span class="status-dot"></span>
            <span>系统在线</span>
          </div>
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
                <el-dropdown-item command="settings">系统设置</el-dropdown-item>
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
  width: 296px;
  min-width: 296px;
  height: 100vh;
  padding: 24px 18px 18px;
  background: linear-gradient(180deg, #215dc6 0%, #287ec9 48%, #1d948c 100%);
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 24px 0 48px rgba(19, 52, 110, 0.12);
  transition: width 0.28s ease, min-width 0.28s ease, transform 0.28s ease;
  z-index: 20;
}

.sidebar.collapsed {
  width: 96px;
  min-width: 96px;
}

.brand-block {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.brand-mark {
  width: 50px;
  height: 50px;
  border-radius: 18px;
  display: grid;
  place-items: center;
  background: linear-gradient(145deg, #16a085, #0f7b6c);
  color: #fff;
  font-size: 18px;
  font-weight: 800;
  letter-spacing: 0.08em;
  box-shadow: 0 10px 20px rgba(10, 91, 80, 0.25);
}

.brand-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  color: rgba(255, 255, 255, 0.96);
}

.brand-copy strong {
  font-size: 18px;
}

.brand-copy span {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.66);
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
  padding: 14px 16px;
  border: 0;
  border-radius: 20px;
  background: transparent;
  color: rgba(255, 255, 255, 0.76);
  cursor: pointer;
  transition: transform 0.18s ease, background 0.18s ease, color 0.18s ease;
  text-align: left;
}

.nav-item:hover {
  transform: translateX(2px);
  background: rgba(255, 255, 255, 0.06);
  color: #fff;
}

.nav-item.active {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.16), rgba(22, 160, 133, 0.22));
  color: #fff;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08);
}

.nav-icon {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.08);
  font-size: 18px;
  flex-shrink: 0;
}

.nav-copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow: hidden;
}

.nav-copy strong {
  font-size: 15px;
  font-weight: 700;
}

.nav-copy small {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.60);
}

.sidebar-footer {
  margin-top: auto;
  display: grid;
  gap: 10px;
}

.footer-tip {
  color: rgba(255, 255, 255, 0.58);
  font-size: 12px;
  letter-spacing: 0.08em;
}

.footer-card {
  display: grid;
  gap: 6px;
  padding: 16px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.07);
  color: rgba(255, 255, 255, 0.92);
  line-height: 1.5;
}

.footer-card span {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.68);
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

.status-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 999px;
  background: var(--surface-1);
  border: 1px solid var(--line-soft);
  color: var(--text-2);
  box-shadow: var(--shadow-card);
  font-size: 13px;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #20c997;
  box-shadow: 0 0 0 6px rgba(32, 201, 151, 0.14);
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
    width: min(84vw, 320px);
    min-width: min(84vw, 320px);
    height: 100vh;
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

  .page-meta p,
  .status-chip {
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

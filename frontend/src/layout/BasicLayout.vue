<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowDown, Close, Menu, UserFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { APP_NAME, APP_NAV_ITEMS } from '../config/navigation'
import { useViewport } from '../composables/useViewport'
import { useUserStore } from '../stores/user'
import { useShopStore } from '../stores/shop'
import { createShop, type ShopCreateDTO } from '../api/shop'

interface OpenTab {
  path: string
  title: string
  name?: string
}

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const { width } = useViewport()

const appName = APP_NAME
const username = computed(() => userStore.username || 'User')
const isSidebarCollapsed = ref(false)
const mobileMenuVisible = ref(false)
const isMobile = computed(() => width.value <= 960)
const navItems = APP_NAV_ITEMS
const isAdmin = computed(() => userStore.isAdmin)
const visibleNavItems = computed(() => navItems.filter((item) => !item.adminOnly || isAdmin.value))
const currentNav = computed(() => visibleNavItems.value.find((item) => route.path.startsWith(item.path)))
const pageTitle = computed(() => currentNav.value?.title || String(route.meta.title || 'App'))
const openTabs = ref<OpenTab[]>([])
const cacheNames = computed(() =>
  openTabs.value
    .map((tab) => tab.name)
    .filter((name): name is string => Boolean(name))
)

const shopStore = useShopStore()
const showShopGuard = computed(
  () => shopStore.loadSucceeded && !shopStore.loading && shopStore.shops.length === 0 && route.path !== '/login'
)
const shopForm = ref<ShopCreateDTO>({ shopName: '', platform: '', sellerNick: '' })
const shopFormLoading = ref(false)

const handleCreateFirstShop = async () => {
  if (!shopForm.value.shopName.trim()) {
    ElMessage.warning('请输入店铺名称')
    return
  }
  if (!shopForm.value.platform) {
    ElMessage.warning('请选择电商平台')
    return
  }
  shopFormLoading.value = true
  try {
    const res: any = await createShop(shopForm.value)
    if (res.code === 200) {
      ElMessage.success('店铺创建成功')
      await shopStore.fetchShops(true)
    } else {
      ElMessage.error(res.message || '创建失败')
    }
  } catch {
    ElMessage.error('创建店铺失败')
  } finally {
    shopFormLoading.value = false
  }
}

const syncUserState = () => {
  userStore.syncFromSession()
}

const navigateTo = (path: string) => {
  router.push(path)
  if (isMobile.value) {
    mobileMenuVisible.value = false
  }
}

const isNavItemActive = (path: string) => route.path.startsWith(path)

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
    shopStore.resetState()
    userStore.clearSession()
    ElMessage.success('\u5df2\u9000\u51fa\u767b\u5f55')
    router.push('/login')
  }
}

watch(
  isMobile,
  (mobile) => {
    if (mobile) {
      isSidebarCollapsed.value = false
      mobileMenuVisible.value = false
    }
  },
  { immediate: true }
)

watch(
  () => route.path,
  () => {
    syncUserState()
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

watch(
  () => shopStore.loadError,
  (message) => {
    if (!message || route.path === '/login') {
      return
    }
    ElMessage.error(message)
  }
)

onMounted(() => {
  syncUserState()
  void shopStore.fetchShops()
  window.addEventListener('auth-session-changed', syncUserState)
  ensureCurrentTab()
})

onBeforeUnmount(() => {
  window.removeEventListener('auth-session-changed', syncUserState)
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
          </div>
        </transition>
      </div>

      <nav class="nav-list" aria-label="主导航">
        <button
          v-for="item in visibleNavItems"
          :key="item.path"
          type="button"
          class="nav-item"
          :class="{ active: isNavItemActive(item.path) }"
          :aria-current="isNavItemActive(item.path) ? 'page' : undefined"
          :aria-label="item.title"
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
              <h1 class="page-title">{{ pageTitle }}</h1>
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

    <el-dialog
      v-model="showShopGuard"
      title="欢迎！请先创建您的第一个店铺"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
      width="480px"
    >
      <el-form :model="shopForm" label-width="80px">
        <el-form-item label="店铺名称" required>
          <el-input v-model="shopForm.shopName" placeholder="如：我的淘宝店" />
        </el-form-item>
        <el-form-item label="电商平台" required>
          <el-select v-model="shopForm.platform" placeholder="请选择" style="width: 100%">
            <el-option v-for="p in ['淘宝', '天猫', '京东', '拼多多', '抖音']" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>
        <el-form-item label="卖家昵称">
          <el-input v-model="shopForm.sellerNick" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button type="primary" :loading="shopFormLoading" @click="handleCreateFirstShop">创建店铺</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.layout-shell {
  --sidebar-width: 236px;
  --sidebar-collapsed-width: 72px;
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
  gap: 12px;
  width: var(--sidebar-width);
  min-width: var(--sidebar-width);
  height: 100vh;
  min-height: 100vh;
  padding: 12px 10px 10px;
  background: #0f172a;
  border-right: 1px solid rgba(255, 255, 255, 0.05);
  box-shadow: 4px 0 20px rgba(0, 0, 0, 0.15);
  transition: width 0.2s ease-in-out, min-width 0.2s ease-in-out, transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 20;
}

.sidebar.collapsed {
  width: var(--sidebar-collapsed-width);
  min-width: var(--sidebar-collapsed-width);
}

.mobile-close {
  margin-left: auto;
  color: var(--text-2);
}

.sidebar-brand {
  display: block;
  padding: 2px 4px 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.brand-copy {
  display: flex;
  align-items: center;
  padding: 12px 12px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  transition: all 0.2s;
}

.brand-copy:hover {
  background: rgba(255, 255, 255, 0.06);
}

.brand-copy strong {
  display: block;
  font-size: 19px;
  line-height: 1.2;
  color: #f8fafc;
  font-weight: 700;
  letter-spacing: 0.5px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.sidebar.collapsed .sidebar-brand {
  justify-content: center;
  padding-left: 0;
  padding-right: 0;
}

.nav-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding-top: 4px;
  overflow-y: auto;
  padding-right: 2px;
}

.nav-item {
  width: 100%;
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 44px;
  padding: 8px 10px;
  border: 1px solid transparent;
  border-radius: 12px;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  text-align: left;
}

.nav-item::before {
  content: '';
  position: absolute;
  left: -2px;
  top: 10px;
  bottom: 10px;
  width: 4px;
  border-radius: 0 4px 4px 0;
  background: #3b82f6;
  opacity: 0;
  transition: all 0.2s;
  transform: scaleY(0);
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #f1f5f9;
}

.nav-item.active {
  background: rgba(59, 130, 246, 0.12);
  color: #60a5fa;
  border-color: rgba(59, 130, 246, 0.2);
}

.nav-item.active::before {
  opacity: 1;
  transform: scaleY(1);
}

.nav-icon {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.05);
  color: #94a3b8;
  font-size: 16px;
  flex-shrink: 0;
  transition: all 0.2s;
}

.nav-item:hover .nav-icon {
  background: rgba(255, 255, 255, 0.1);
  color: #e2e8f0;
}

.nav-item.active .nav-icon {
  background: #3b82f6;
  color: #ffffff;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

.nav-copy {
  display: flex;
  overflow: hidden;
  min-width: 0;
}

.nav-copy strong {
  font-size: 14px;
  line-height: 1.35;
  font-weight: 500;
  letter-spacing: 0.01em;
}

.sidebar.collapsed .nav-item {
  justify-content: center;
  padding-left: 0;
  padding-right: 0;
}

.sidebar.collapsed .nav-item::before {
  left: 6px;
}

.main-shell {
  flex: 1;
  min-width: 0;
  max-width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow-x: hidden;
  width: calc(100% - var(--sidebar-width));
  margin-left: var(--sidebar-width);
  background: #f8fafc;
  transition: margin-left 0.2s ease-in-out, width 0.2s ease-in-out;
}

.sidebar.collapsed ~ .main-shell {
  width: calc(100% - var(--sidebar-collapsed-width));
  margin-left: var(--sidebar-collapsed-width);
}

.header-wrapper {
  position: sticky;
  top: 0;
  z-index: 20;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(20px) saturate(180%);
  border-bottom: 1px solid rgba(226, 232, 240, 0.8);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.02);
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  min-height: 60px;
  padding: 0 20px;
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
  box-shadow: 0 2px 4px rgba(0,0,0,0.02);
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
  margin-left: 8px;
}

.page-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
  letter-spacing: 0.5px;
}

.user-entry {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 5px 10px;
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
  font-size: 14px;
}

.user-copy span {
  font-size: 12px;
  color: var(--text-3);
}

.content-shell {
  flex: 1;
  min-height: 0;
  padding: 14px 16px 20px;
  overflow-x: hidden;
  overflow-y: auto;
}

.tabs-shell {
  padding: 0 20px;
  background: transparent;
}

.tabs-track {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 8px 0 0;
}

.tabs-track::-webkit-scrollbar {
  height: 0;
}

.tab-item {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 38px;
  max-width: 200px;
  padding: 0 14px;
  border: 1px solid transparent;
  border-bottom: none;
  border-radius: 8px 8px 0 0;
  background: rgba(226, 232, 240, 0.4);
  color: #64748b;
  cursor: pointer;
  position: relative;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.tab-item:hover {
  background: rgba(226, 232, 240, 0.8);
  color: #334155;
}

.tab-item.active {
  background: #ffffff;
  color: #3b82f6;
  border: 1px solid rgba(226, 232, 240, 0.8);
  border-bottom: none;
  box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.02);
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
  font-size: 12px;
  font-weight: 600;
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
    border-right: 1px solid var(--line-soft);
    box-shadow: 12px 0 30px rgba(20, 40, 63, 0.12);
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
    padding: 10px 12px;
  }

  .content-shell {
    padding: 14px 12px 20px;
  }

  .tabs-shell {
    padding: 0 12px;
  }

  .page-title {
    font-size: 16px;
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

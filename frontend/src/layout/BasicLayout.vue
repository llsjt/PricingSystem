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
import { logout } from '../api/user'

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

const handleCommand = async (command: string) => {
  if (command === 'profile') {
    navigateTo('/profile')
    return
  }

  if (command === 'logout') {
    try {
      await logout()
    } catch {
      // fall through and clear local state regardless
    }
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
  gap: 10px;
  width: var(--sidebar-width);
  min-width: var(--sidebar-width);
  height: 100vh;
  min-height: 100vh;
  padding: 14px 12px 12px;
  overflow: hidden;
  background:
    linear-gradient(180deg, rgba(147, 197, 253, 0.14) 0%, rgba(147, 197, 253, 0) 20%),
    linear-gradient(180deg, #22334c 0%, #29405d 52%, #30486a 100%);
  border-right: 1px solid rgba(148, 163, 184, 0.22);
  box-shadow: 10px 0 26px rgba(2, 6, 23, 0.16);
  transition: width 0.2s ease-in-out, min-width 0.2s ease-in-out, transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 20;
}

.sidebar::before {
  content: '';
  position: absolute;
  inset: 0 0 auto 0;
  height: 96px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0));
  pointer-events: none;
}

.sidebar.collapsed {
  width: var(--sidebar-collapsed-width);
  min-width: var(--sidebar-collapsed-width);
}

.mobile-close {
  margin-left: auto;
  color: #cbd5e1;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.48);
  backdrop-filter: blur(10px);
}

.mobile-close:hover {
  color: #f8fafc;
  border-color: rgba(96, 165, 250, 0.28);
  background: rgba(30, 41, 59, 0.88);
}

.sidebar-brand {
  display: block;
  position: relative;
  padding: 4px 2px 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.brand-copy {
  display: flex;
  align-items: center;
  position: relative;
  overflow: hidden;
  padding: 14px 16px;
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.07), rgba(255, 255, 255, 0.03));
  border: 1px solid rgba(148, 163, 184, 0.16);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.07);
  transition: background-color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.brand-copy::before {
  content: '';
  position: absolute;
  inset: 0 0 auto 0;
  height: 1px;
  background: rgba(255, 255, 255, 0.18);
  opacity: 0.7;
}

.brand-copy:hover {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.09), rgba(255, 255, 255, 0.04));
  border-color: rgba(148, 163, 184, 0.22);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.09);
}

.brand-copy strong {
  display: block;
  font-size: 20px;
  line-height: 1.3;
  color: #f8fafc;
  font-weight: 650;
  letter-spacing: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.24);
}

.sidebar.collapsed .sidebar-brand {
  justify-content: center;
  padding-left: 0;
  padding-right: 0;
}

.nav-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-top: 6px;
  overflow-y: auto;
  padding-right: 4px;
  padding-bottom: 10px;
}

.nav-list::-webkit-scrollbar {
  width: 6px;
}

.nav-list::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.18);
}

.nav-list::-webkit-scrollbar-track {
  background: transparent;
}

.nav-item {
  width: 100%;
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 50px;
  padding: 9px 12px;
  border: 1px solid rgba(148, 163, 184, 0);
  border-radius: 8px;
  background: transparent;
  color: #8ea1b8;
  cursor: pointer;
  transition:
    background-color 0.2s ease,
    border-color 0.2s ease,
    color 0.2s ease,
    box-shadow 0.2s ease;
  text-align: left;
}

.nav-item::before {
  content: '';
  position: absolute;
  left: 7px;
  top: 9px;
  bottom: 9px;
  width: 3px;
  border-radius: 999px;
  background: linear-gradient(180deg, #60a5fa 0%, #3b82f6 100%);
  opacity: 0;
  transition: all 0.2s;
  transform: scaleY(0);
  transform-origin: center;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(148, 163, 184, 0.12);
  color: #e2e8f0;
}

.nav-item.active {
  background: linear-gradient(90deg, rgba(37, 99, 235, 0.18), rgba(15, 23, 42, 0.14));
  color: #f8fafc;
  border-color: rgba(96, 165, 250, 0.24);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.nav-item.active::before {
  opacity: 1;
  transform: scaleY(1);
}

.nav-item:focus-visible {
  outline: none;
  color: #f8fafc;
  border-color: rgba(96, 165, 250, 0.34);
  background: rgba(30, 64, 175, 0.18);
  box-shadow: 0 0 0 2px rgba(96, 165, 250, 0.18);
}

.nav-item:focus-visible::before {
  opacity: 1;
  transform: scaleY(1);
}

.nav-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  background: rgba(148, 163, 184, 0.08);
  border: 1px solid rgba(148, 163, 184, 0.1);
  color: #94a3b8;
  font-size: 15px;
  flex-shrink: 0;
  transition:
    background-color 0.2s ease,
    border-color 0.2s ease,
    color 0.2s ease,
    box-shadow 0.2s ease;
}

.nav-item:hover .nav-icon {
  background: rgba(148, 163, 184, 0.12);
  border-color: rgba(148, 163, 184, 0.16);
  color: #e2e8f0;
}

.nav-item.active .nav-icon {
  background: linear-gradient(180deg, #3b82f6 0%, #2563eb 100%);
  border-color: rgba(96, 165, 250, 0.28);
  color: #ffffff;
  box-shadow: 0 6px 14px rgba(37, 99, 235, 0.22), inset 0 1px 0 rgba(255, 255, 255, 0.16);
}

.nav-item:focus-visible .nav-icon {
  background: rgba(59, 130, 246, 0.16);
  border-color: rgba(96, 165, 250, 0.3);
  color: #dbeafe;
}

.nav-copy {
  display: flex;
  overflow: hidden;
  min-width: 0;
}

.nav-copy strong {
  font-size: 16px;
  line-height: 1.4;
  font-weight: 600;
  letter-spacing: 0;
}

.sidebar.collapsed .nav-item {
  justify-content: center;
  padding-left: 0;
  padding-right: 0;
}

.sidebar.collapsed .nav-item::before {
  left: 5px;
}

.sidebar.collapsed .nav-icon {
  width: 30px;
  height: 30px;
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
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(20px) saturate(180%);
  border-bottom: 1px solid rgba(226, 232, 240, 0.8);
  box-shadow: 0 2px 14px rgba(15, 23, 42, 0.04);
}

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

.content-shell {
  flex: 1;
  min-height: 0;
  padding: 12px 16px 18px;
  overflow-x: hidden;
  overflow-y: auto;
}

.tabs-shell {
  padding: 0 18px 8px;
  background: transparent;
}

.tabs-track {
  display: flex;
  gap: 8px;
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
  min-height: 34px;
  max-width: 200px;
  padding: 0 12px;
  border: 1px solid rgba(226, 232, 240, 0.82);
  border-radius: 999px;
  background: rgba(248, 250, 252, 0.95);
  color: #64748b;
  cursor: pointer;
  position: relative;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.tab-item:hover {
  background: #ffffff;
  border-color: rgba(191, 219, 254, 0.9);
  color: #334155;
}

.tab-item.active {
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.96), rgba(232, 244, 255, 0.88));
  color: #2563eb;
  border-color: rgba(147, 197, 253, 0.9);
  box-shadow: 0 1px 2px rgba(37, 99, 235, 0.08);
}

.tab-title {
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tab-close {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  min-width: 16px;
  height: 16px;
  margin-left: 4px;
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
  background: rgba(2, 6, 23, 0.48);
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
    border-right: 1px solid rgba(148, 163, 184, 0.16);
    box-shadow: 14px 0 34px rgba(2, 6, 23, 0.24);
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
    min-height: 52px;
    padding: 8px 12px;
  }

  .content-shell {
    padding: 12px 12px 18px;
  }

  .tabs-shell {
    padding: 0 12px 6px;
  }

  .page-title {
    font-size: 17px;
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

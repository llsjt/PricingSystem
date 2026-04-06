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
  background: linear-gradient(180deg, #dbe6f4 0%, #d2deef 100%);
  border-right: 1px solid rgba(98, 122, 154, 0.3);
  box-shadow: 6px 0 14px rgba(23, 47, 79, 0.12);
  transition: width 0.2s ease-in-out, min-width 0.2s ease-in-out, transform 0.2s ease-in-out;
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
  border-bottom: 1px solid var(--line-soft);
}

.brand-copy {
  display: grid;
  padding: 10px 12px;
  border-radius: 12px;
  background: rgba(241, 247, 255, 0.78);
  border: 1px solid rgba(118, 140, 171, 0.26);
}

.brand-copy strong {
  display: block;
  font-size: 18px;
  line-height: 1.2;
  color: var(--text-1);
  font-weight: 700;
  letter-spacing: 0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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
  color: #475b74;
  cursor: pointer;
  transition: background 0.18s ease-in-out, color 0.18s ease-in-out, border-color 0.18s ease-in-out;
  text-align: left;
}

.nav-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: 999px;
  background: var(--brand);
  opacity: 0;
}

.nav-item:hover {
  background: rgba(239, 246, 255, 0.88);
  color: #1f3653;
  border-color: rgba(112, 135, 165, 0.3);
}

.nav-item.active {
  background: rgba(225, 238, 255, 0.96);
  color: #114a95;
  border-color: rgba(31, 111, 235, 0.22);
}

.nav-item.active::before {
  opacity: 1;
}

.nav-icon {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  background: rgba(241, 247, 255, 0.92);
  color: #4e637f;
  font-size: 16px;
  flex-shrink: 0;
  transition: background 0.18s ease-in-out, color 0.18s ease-in-out;
}

.nav-item:hover .nav-icon,
.nav-item.active .nav-icon {
  background: rgba(31, 111, 235, 0.14);
  color: var(--brand);
}

.nav-copy {
  display: flex;
  overflow: hidden;
  min-width: 0;
}

.nav-copy strong {
  font-size: 13px;
  line-height: 1.35;
  font-weight: 600;
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
  border-left: 1px solid rgba(24, 42, 58, 0.05);
  background: rgba(255, 255, 255, 0.58);
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
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(10px);
  box-shadow: 0 2px 8px rgba(0, 21, 41, 0.03);
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  min-height: 54px;
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
  border: 1px solid var(--line-soft);
  background: var(--surface-1);
  box-shadow: none;
}

.page-meta {
  display: flex;
  align-items: center;
  margin-left: 4px;
}

.page-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #1f2d3d;
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
  padding: 0 16px;
  background: linear-gradient(180deg, rgba(243, 247, 252, 0.96), rgba(238, 244, 251, 0.92));
  border-bottom: 1px solid rgba(31, 46, 77, 0.08);
}

.tabs-track {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding: 4px 0 0;
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
  max-width: 220px;
  padding: 0 12px;
  border: 1px solid rgba(31, 46, 77, 0.06);
  border-bottom: none;
  border-radius: 10px 10px 0 0;
  background: rgba(214, 225, 240, 0.78);
  color: #60738b;
  cursor: pointer;
  position: relative;
  transition: all 0.2s cubic-bezier(0.645, 0.045, 0.355, 1);
}

.tab-item:hover {
  background: rgba(198, 213, 232, 0.92);
  color: #314a67;
}

.tab-item.active {
  background: #ffffff;
  color: #1f6feb;
  border: 1px solid rgba(31, 46, 77, 0.09);
  border-bottom: none;
  box-shadow: 0 8px 18px rgba(20, 44, 72, 0.06);
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

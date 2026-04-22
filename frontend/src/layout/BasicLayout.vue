<!-- 后台基础布局组件，负责导航、顶部栏和内容区域的统一壳层。 -->

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppSidebar from '../components/layout/AppSidebar.vue'
import FirstShopGuardDialog from '../components/layout/FirstShopGuardDialog.vue'
import LayoutTabsBar from '../components/layout/LayoutTabsBar.vue'
import LayoutTopbar from '../components/layout/LayoutTopbar.vue'
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
const pageTitle = computed(() => String(route.meta.title || currentNav.value?.title || 'App'))
const openTabs = ref<OpenTab[]>([])
const cacheNames = computed(() =>
  openTabs.value
    .map((tab) => tab.name)
    .filter((name): name is string => Boolean(name))
)

const shopStore = useShopStore()
// 如果用户还没有任何店铺，布局层直接弹出首店创建守卫，避免进入业务页后才发现无法操作。
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

// 标签页由布局统一维护，确保菜单点击、路由跳转和 keep-alive 缓存名称始终同步。
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
  const title = String(route.meta.title || currentNav.value?.title || route.name || route.path)
  const name = typeof route.name === 'string' ? route.name : undefined
  upsertTab({
    path: route.path,
    title,
    name
  })
}

// 关闭当前激活标签时，优先回退到相邻标签，保持后台多页签浏览的连续体验。
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
      // 即使后端注销接口失败，也要继续清理本地会话，避免页面残留旧登录态。
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

    <AppSidebar
      :app-name="appName"
      :current-path="route.path"
      :is-mobile="isMobile"
      :is-sidebar-collapsed="isSidebarCollapsed"
      :mobile-menu-visible="mobileMenuVisible"
      :visible-nav-items="visibleNavItems"
      @close-mobile="mobileMenuVisible = false"
      @navigate="navigateTo"
    />

    <div class="main-shell" :class="{ collapsed: isSidebarCollapsed && !isMobile }">
      <div class="header-wrapper">
        <LayoutTopbar
          :is-admin="isAdmin"
          :page-title="pageTitle"
          :username="username"
          @command="handleCommand"
          @toggle-sidebar="toggleSidebar"
        />

        <LayoutTabsBar
          :active-path="route.path"
          :open-tabs="openTabs"
          @close-tab="closeTab"
          @open-tab="openTab"
        />
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

    <FirstShopGuardDialog
      :loading="shopFormLoading"
      :model-value="showShopGuard"
      :shop-form="shopForm"
      @submit="handleCreateFirstShop"
    />
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

.main-shell.collapsed {
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

.content-shell {
  flex: 1;
  min-height: 0;
  padding: 12px 16px 18px;
  overflow-x: hidden;
  overflow-y: auto;
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
}
</style>

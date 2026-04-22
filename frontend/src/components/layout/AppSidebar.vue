<script setup lang="ts">
import { Close } from '@element-plus/icons-vue'

interface NavItem {
  path: string
  title: string
  icon?: unknown
}

const props = defineProps<{
  appName: string
  currentPath: string
  isSidebarCollapsed: boolean
  isMobile: boolean
  mobileMenuVisible: boolean
  visibleNavItems: NavItem[]
}>()

const emit = defineEmits<{
  closeMobile: []
  navigate: [path: string]
}>()

const isNavItemActive = (path: string) => props.currentPath.startsWith(path)
</script>

<template>
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
      @click="emit('closeMobile')"
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
        @click="emit('navigate', item.path)"
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
</template>

<style scoped>
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
  background: linear-gradient(180deg, #4b6887 0%, #3f5c7b 52%, #36506d 100%);
  border-right: 1px solid rgba(218, 234, 255, 0.22);
  box-shadow: 12px 0 34px rgba(22, 38, 58, 0.18);
  transition: width 0.2s ease-in-out, min-width 0.2s ease-in-out, transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 20;
}

.sidebar.collapsed {
  width: var(--sidebar-collapsed-width);
  min-width: var(--sidebar-collapsed-width);
}

.mobile-close {
  margin-left: auto;
  color: #eef6ff;
  border: 1px solid rgba(223, 238, 255, 0.2);
  background: rgba(255, 255, 255, 0.12);
  backdrop-filter: blur(14px);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.16);
}

.mobile-close:hover {
  color: #ffffff;
  border-color: rgba(193, 222, 255, 0.36);
  background: rgba(255, 255, 255, 0.2);
}

.sidebar-brand {
  display: flex;
  align-items: center;
  position: relative;
  min-height: 92px;
  padding: 6px 8px 18px;
  background: transparent;
  border-bottom: 1px solid rgba(223, 238, 255, 0.15);
}

.brand-copy {
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  width: 100%;
  min-height: 56px;
  padding: 12px 8px;
  text-align: center;
}

.brand-copy strong {
  display: block;
  font-family: Inter, "PingFang SC", "Microsoft YaHei", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
  font-size: 27px;
  line-height: 1.12;
  font-weight: 700;
  letter-spacing: 0.04em;
  white-space: nowrap;
  overflow: visible;
  text-overflow: clip;
  color: #edf5ff;
  -webkit-font-smoothing: antialiased;
  text-shadow: 0 6px 14px rgba(12, 30, 52, 0.2);
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
  padding-top: 8px;
  overflow-y: auto;
  padding-right: 4px;
  padding-bottom: 10px;
}

.nav-list::-webkit-scrollbar {
  width: 6px;
}

.nav-list::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(222, 236, 252, 0.28);
}

.nav-list::-webkit-scrollbar-track {
  background: transparent;
}

.nav-item {
  width: 100%;
  box-sizing: border-box;
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  height: 54px;
  min-height: 54px;
  padding: 10px 13px;
  border: 1px solid rgba(226, 240, 255, 0.1);
  border-radius: 16px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.075), rgba(255, 255, 255, 0.035));
  color: #c2d0df;
  cursor: pointer;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.08),
    inset 0 -1px 0 rgba(29, 55, 82, 0.12);
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
  left: 8px;
  top: 12px;
  bottom: 12px;
  width: 3px;
  border-radius: 999px;
  background: linear-gradient(180deg, #d6f0ff, #73b7ff);
  opacity: 0;
  transition: all 0.2s;
  transform: scaleY(0);
  transform-origin: center;
}

.nav-item:hover {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.12), rgba(240, 248, 255, 0.07));
  border-color: rgba(218, 236, 255, 0.22);
  color: #f6f9fd;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.13),
    inset 0 -1px 0 rgba(29, 55, 82, 0.1);
}

.nav-item.active {
  height: 54px;
  min-height: 54px;
  padding: 10px 13px;
  border-width: 1px;
  transform: none;
  background:
    linear-gradient(180deg, rgba(49, 81, 118, 0.88), rgba(35, 61, 92, 0.94)),
    linear-gradient(90deg, rgba(110, 178, 255, 0.14), rgba(22, 40, 63, 0.08));
  color: #f5f9ff;
  border-color: rgba(170, 208, 247, 0.28);
  box-shadow:
    0 0 0 1px rgba(170, 208, 247, 0.18),
    inset 0 1px 0 rgba(173, 214, 255, 0.12),
    inset 0 -1px 0 rgba(17, 31, 49, 0.4);
}

.nav-item.active::before {
  opacity: 1;
  transform: scaleY(1);
}

.nav-item:focus-visible {
  outline: none;
  color: #ffffff;
  border-color: rgba(204, 229, 255, 0.46);
  background: rgba(255, 255, 255, 0.13);
  box-shadow: 0 0 0 2px rgba(142, 199, 255, 0.22);
}

.nav-item:focus-visible::before {
  opacity: 1;
  transform: scaleY(1);
}

.nav-icon {
  width: 30px;
  height: 30px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: linear-gradient(180deg, rgba(245, 250, 255, 0.13), rgba(224, 239, 255, 0.07));
  border: 1px solid rgba(230, 242, 255, 0.16);
  color: #dbe8f6;
  font-size: 15px;
  flex-shrink: 0;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.12);
  transition:
    background-color 0.2s ease,
    border-color 0.2s ease,
    color 0.2s ease,
    box-shadow 0.2s ease;
}

.nav-item:hover .nav-icon {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.18), rgba(228, 242, 255, 0.1));
  border-color: rgba(228, 242, 255, 0.24);
  color: #ffffff;
}

.nav-item.active .nav-icon {
  width: 30px;
  height: 30px;
  transform: none;
  background: linear-gradient(180deg, rgba(105, 163, 232, 0.44), rgba(56, 106, 170, 0.62));
  border-color: rgba(182, 216, 250, 0.34);
  color: #ffffff;
  box-shadow:
    inset 0 1px 0 rgba(203, 231, 255, 0.16);
}

.nav-item:focus-visible .nav-icon {
  background: rgba(167, 211, 255, 0.26);
  border-color: rgba(221, 239, 255, 0.32);
  color: #ffffff;
}

.nav-copy {
  display: flex;
  overflow: hidden;
  min-width: 0;
}

.nav-copy strong {
  font-size: 15px;
  line-height: 1.4;
  font-weight: 600;
  letter-spacing: 0.025em;
}

.sidebar.collapsed .nav-item {
  justify-content: center;
  padding-left: 0;
  padding-right: 0;
}

.sidebar.collapsed .nav-item::before {
  left: 6px;
}

.sidebar.collapsed .nav-icon {
  width: 30px;
  height: 30px;
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
}
</style>

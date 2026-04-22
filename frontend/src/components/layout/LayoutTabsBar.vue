<script setup lang="ts">
interface OpenTab {
  path: string
  title: string
  name?: string
}

defineProps<{
  activePath: string
  openTabs: OpenTab[]
}>()

const emit = defineEmits<{
  closeTab: [path: string]
  openTab: [path: string]
}>()
</script>

<template>
  <div class="tabs-shell" v-if="openTabs.length">
    <div class="tabs-track">
      <button
        v-for="tab in openTabs"
        :key="tab.path"
        type="button"
        class="tab-item"
        :class="{ active: activePath === tab.path }"
        @click="emit('openTab', tab.path)"
      >
        <span class="tab-title">{{ tab.title }}</span>
        <span
          v-if="openTabs.length > 1"
          class="tab-close"
          role="button"
          tabindex="0"
          @click.stop="emit('closeTab', tab.path)"
          @keydown.enter.prevent="emit('closeTab', tab.path)"
          @keydown.space.prevent="emit('closeTab', tab.path)"
        >
          <el-icon><Close /></el-icon>
        </span>
      </button>
    </div>
  </div>
</template>

<script lang="ts">
import { Close } from '@element-plus/icons-vue'
export default {
  components: { Close }
}
</script>

<style scoped>
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

@media (max-width: 960px) {
  .tabs-shell {
    padding: 0 12px 6px;
  }
}
</style>

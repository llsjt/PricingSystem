<template>
  <span class="count-up" :class="{ 'count-up-animating': animating }">{{ display }}</span>
</template>

<script setup lang="ts">
// 数字滚动组件，用于把价格、销量和利润等指标以动画形式展示出来。

import { onBeforeUnmount, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  value: number | null | undefined
  duration?: number
  decimals?: number
  prefix?: string
  suffix?: string
}>(), { duration: 700, decimals: 2, prefix: '', suffix: '' })

const display = ref('')
const animating = ref(false)
let rafId = 0
let from = 0

const format = (n: number) => `${props.prefix}${n.toLocaleString('zh-CN', { minimumFractionDigits: props.decimals, maximumFractionDigits: props.decimals })}${props.suffix}`

const stop = () => { if (rafId) { cancelAnimationFrame(rafId); rafId = 0 } }

const run = (target: number | null | undefined) => {
  stop()
  if (target == null || !Number.isFinite(Number(target))) {
    display.value = '-'
    animating.value = false
    return
  }
  const to = Number(target)
  if (!Number.isFinite(from)) from = 0
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) {
    display.value = format(to)
    from = to
    return
  }
  const start = performance.now()
  const origin = from
  const diff = to - origin
  animating.value = true
  const tick = (t: number) => {
    const p = Math.min(1, (t - start) / props.duration)
    const eased = 1 - Math.pow(1 - p, 4)
    display.value = format(origin + diff * eased)
    if (p < 1) {
      rafId = requestAnimationFrame(tick)
    } else {
      animating.value = false
      from = to
      rafId = 0
    }
  }
  rafId = requestAnimationFrame(tick)
}

watch(() => props.value, run, { immediate: true })
onBeforeUnmount(stop)
</script>

<style scoped>
.count-up { font-variant-numeric: tabular-nums; transition: color .3s ease; }
.count-up-animating { color: var(--agent-color, #409eff); }
</style>

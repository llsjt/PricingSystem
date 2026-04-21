<template>
  <p class="typewriter-text" :class="{ 'typewriter-done': done }">{{ displayed }}</p>
</template>

<script setup lang="ts">
// 打字机文本组件，用于按字符渐进展示智能体输出内容。

import { onBeforeUnmount, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  text: string
  speed?: number
}>(), { speed: 45 })
const emit = defineEmits<{ (event: 'done'): void }>()

const displayed = ref('')
const done = ref(false)
let timer: ReturnType<typeof setInterval> | null = null
let index = 0

const stop = () => {
  if (!timer) return
  clearInterval(timer)
  timer = null
}

const finish = () => {
  if (done.value) return
  done.value = true
  emit('done')
}

const start = () => {
  stop()
  index = 0
  displayed.value = ''
  done.value = false
  if (!props.text) {
    finish()
    return
  }
  timer = setInterval(() => {
    if (index >= props.text.length) {
      finish()
      stop()
      return
    }
    const chunk = Math.min(1, props.text.length - index)
    displayed.value += props.text.slice(index, index + chunk)
    index += chunk
  }, props.speed)
}

watch(() => props.text, start, { immediate: true })
onBeforeUnmount(stop)
</script>

<style scoped>
.typewriter-text{margin:0;white-space:pre-wrap;line-height:1.8}
.typewriter-text:not(.typewriter-done)::after{content:'';display:inline-block;width:2px;height:1em;margin-left:3px;vertical-align:-2px;background:var(--agent-color,#409eff);border-radius:1px;animation:tw-blink 1s steps(1) infinite;box-shadow:0 0 6px var(--agent-color,#409eff)}
@keyframes tw-blink{50%{opacity:0}}
@media (prefers-reduced-motion: reduce){.typewriter-text:not(.typewriter-done)::after{animation:none}}
</style>

import { computed, onBeforeUnmount, onMounted, ref, type ComputedRef, type Ref } from 'vue'

export interface ViewportState {
  width: Ref<number>
  isMobile: ComputedRef<boolean>
}

export const useViewport = (mobileBreakpoint = 768): ViewportState => {
  const width = ref(typeof window !== 'undefined' ? window.innerWidth : 1440)

  const updateWidth = () => {
    if (typeof window !== 'undefined') {
      width.value = window.innerWidth
    }
  }

  onMounted(() => {
    updateWidth()
    if (typeof window !== 'undefined') {
      window.addEventListener('resize', updateWidth)
    }
  })

  onBeforeUnmount(() => {
    if (typeof window !== 'undefined') {
      window.removeEventListener('resize', updateWidth)
    }
  })

  return {
    width,
    isMobile: computed(() => width.value <= mobileBreakpoint)
  }
}

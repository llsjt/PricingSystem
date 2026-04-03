import { onBeforeUnmount, ref } from 'vue'
import * as echarts from 'echarts'

export const useEChart = () => {
  const chartRef = ref<HTMLElement | null>(null)
  let chartInstance: echarts.ECharts | null = null

  const disposeChart = () => {
    if (chartInstance) {
      chartInstance.dispose()
      chartInstance = null
    }
  }

  const setChartOption = (option: any) => {
    if (!chartRef.value) {
      return
    }

    disposeChart()
    chartInstance = echarts.init(chartRef.value)
    chartInstance.setOption(option)
  }

  const resizeChart = () => {
    chartInstance?.resize()
  }

  onBeforeUnmount(() => {
    disposeChart()
  })

  return {
    chartRef,
    setChartOption,
    resizeChart,
    disposeChart
  }
}

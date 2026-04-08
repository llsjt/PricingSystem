import { onBeforeUnmount, ref } from 'vue'
import { BarChart, LineChart } from 'echarts/charts'
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { use } from 'echarts/core'
import * as echarts from 'echarts/core'

use([
  BarChart,
  LineChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
  DataZoomComponent,
  CanvasRenderer
])

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

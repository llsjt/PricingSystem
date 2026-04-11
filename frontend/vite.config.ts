import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import ElementPlus from 'unplugin-element-plus/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import { createApiProxyConfig } from './dev/apiProxy.js'

const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || 'http://localhost:8080'
const apiProxyOrigin = process.env.VITE_API_PROXY_ORIGIN || 'http://localhost:5173'

export default defineConfig({
  plugins: [
    vue(),
    Components({
      dts: false,
      resolvers: [
        ElementPlusResolver({
          importStyle: 'css',
          directives: true
        })
      ]
    }),
    ElementPlus()
  ],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return
          }
          if (id.includes('node_modules/echarts')) {
            return 'echarts'
          }
          if (id.includes('node_modules/xlsx')) {
            return 'xlsx'
          }
          if (
            id.includes('node_modules/vue') ||
            id.includes('node_modules/pinia') ||
            id.includes('node_modules/vue-router') ||
            id.includes('node_modules/@vue')
          ) {
            return 'framework'
          }
          if (
            id.includes('node_modules/element-plus') ||
            id.includes('node_modules/@element-plus') ||
            id.includes('node_modules/@floating-ui')
          ) {
            if (
              id.includes('/table') ||
              id.includes('/pagination') ||
              id.includes('/drawer') ||
              id.includes('/dialog') ||
              id.includes('/descriptions') ||
              id.includes('/empty')
            ) {
              return 'ui-data'
            }
            if (
              id.includes('/form') ||
              id.includes('/input') ||
              id.includes('/select') ||
              id.includes('/option') ||
              id.includes('/radio') ||
              id.includes('/checkbox') ||
              id.includes('/upload') ||
              id.includes('/date-picker') ||
              id.includes('/input-number')
            ) {
              return 'ui-form'
            }
            if (
              id.includes('/message') ||
              id.includes('/message-box') ||
              id.includes('/notification') ||
              id.includes('/loading') ||
              id.includes('/progress') ||
              id.includes('/skeleton')
            ) {
              return 'ui-feedback'
            }
            return 'ui-base'
          }
          return 'vendor-misc'
        }
      }
    }
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 5173,
    proxy: {
      '/api': createApiProxyConfig(apiProxyTarget, apiProxyOrigin)
    }
  }
})

import test from 'node:test'
import assert from 'node:assert/strict'

import { createApiProxyConfig } from './apiProxy.js'

test('api proxy rewrites the browser origin header before forwarding', () => {
  const handlers = {}
  const config = createApiProxyConfig('http://localhost:8080', 'http://localhost:5173')

  config.configure({
    on(eventName, handler) {
      handlers[eventName] = handler
    }
  })

  const removedHeaders = []
  const setHeaders = []
  handlers.proxyReq({
    removeHeader(name) {
      removedHeaders.push(name)
    },
    setHeader(name, value) {
      setHeaders.push([name, value])
    }
  })

  assert.deepEqual(removedHeaders, ['origin'])
  assert.deepEqual(setHeaders, [['origin', 'http://localhost:5173']])
})

test('api proxy keeps the configured backend target', () => {
  const config = createApiProxyConfig('http://localhost:8080', 'http://localhost:5173')

  assert.equal(config.target, 'http://localhost:8080')
  assert.equal(config.changeOrigin, true)
})

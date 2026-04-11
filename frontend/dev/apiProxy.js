export const stripOriginHeader = (proxyReq) => {
  if (!proxyReq || typeof proxyReq.removeHeader !== 'function') {
    return
  }

  proxyReq.removeHeader('origin')
}

export const createApiProxyConfig = (target, forwardedOrigin) => ({
  target,
  changeOrigin: true,
  configure(proxy) {
    proxy.on('proxyReq', (proxyReq) => {
      stripOriginHeader(proxyReq)
      if (forwardedOrigin && typeof proxyReq.setHeader === 'function') {
        proxyReq.setHeader('origin', forwardedOrigin)
      }
    })
  }
})

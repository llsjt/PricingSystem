import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const requestSource = await readFile(join(root, 'src', 'api', 'request.ts'), 'utf8')
const loginSource = await readFile(join(root, 'src', 'views', 'Login.vue'), 'utf8')

assert.match(
  requestSource,
  /const shouldShowGlobalRequestError =[\s\S]*window\.location\.pathname !== '\/login'[\s\S]*!requestUrl\.includes\('\/user\/login'\)/,
  'suppresses global request error toasts while the login page owns feedback'
)

assert.match(
  requestSource,
  /if \(status === 403\) \{[\s\S]*showGlobalRequestError\(requestUrl,[\s\S]*'没有权限访问该资源'[\s\S]*\)/,
  'routes forbidden errors through the global feedback guard'
)

assert.match(
  loginSource,
  /onMounted\(\(\) => \{[\s\S]*ElMessage\.closeAll\(\)[\s\S]*shopStore\.resetState\(\)/,
  'clears stale route-level toasts and shop errors when entering the login page'
)

assert.match(
  loginSource,
  /const handleLogin = async \(\) => \{[\s\S]*ElMessage\.closeAll\(\)/,
  'clears stale feedback before submitting a fresh login attempt'
)

console.log('request feedback tests passed')

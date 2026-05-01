import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const productListSource = await readFile(join(root, 'src', 'views', 'ProductList.vue'), 'utf8')

assert.match(
  productListSource,
  /<el-button type="primary" :loading="batchStarting" :disabled="batchStarting" @click="submitBatchPricing">/,
  'disables the batch pricing submit button while a batch request is in flight'
)

assert.match(
  productListSource,
  /const submitBatchPricing = async \(\) => \{[\s\S]*if \(batchStarting\.value\) return/,
  'guards submitBatchPricing against duplicate clicks before async state changes settle'
)

assert.match(
  productListSource,
  /const productIds = \[\.\.\.new Set\(selectedIds\.value\)\]/,
  'freezes selected product ids before sending the batch pricing request'
)

assert.match(
  productListSource,
  /productIds,[\s\S]*strategyGoal: batchPricingForm\.strategyGoal,[\s\S]*constraints/,
  'sends the frozen product id snapshot instead of the reactive selection array'
)

console.log('product list batch pricing tests passed')

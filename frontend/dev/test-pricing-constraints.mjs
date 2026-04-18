import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
import { dirname, join } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { build } from 'esbuild'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const outdir = join(root, 'node_modules', '.cache', 'pricing-constraints-test')
const outfile = join(outdir, 'pricingConstraints.mjs')

await mkdir(outdir, { recursive: true })
await build({
  entryPoints: [join(root, 'src', 'utils', 'pricingConstraints.ts')],
  outfile,
  bundle: true,
  format: 'esm',
  platform: 'node',
  logLevel: 'silent'
})

const {
  createDefaultPricingConstraintForm,
  serializePricingConstraints,
  validatePricingConstraintForm
} = await import(`${pathToFileURL(outfile).href}?${Date.now()}`)

assert.deepEqual(
  JSON.parse(serializePricingConstraints(createDefaultPricingConstraintForm())),
  { min_profit_rate: 0.15 },
  'default form sends only the required minimum profit rate'
)

assert.deepEqual(
  JSON.parse(serializePricingConstraints({
    minProfitRatePercent: 18,
    minPrice: 50.125,
    maxPrice: 99.994,
    maxDiscountRatePercent: 10,
    forceManualReview: true
  })),
  {
    min_profit_rate: 0.18,
    min_price: 50.13,
    max_price: 99.99,
    max_discount_rate: 0.1,
    force_manual_review: true
  },
  'serializes structured controls to the existing backend JSON constraint keys'
)

assert.deepEqual(
  JSON.parse(serializePricingConstraints({
    minProfitRatePercent: 16.5,
    minPrice: null,
    maxPrice: undefined,
    maxDiscountRatePercent: null,
    forceManualReview: false
  })),
  { min_profit_rate: 0.165 },
  'omits optional constraints that the user did not set'
)

assert.match(
  validatePricingConstraintForm({
    minProfitRatePercent: 15,
    minPrice: 100,
    maxPrice: 80,
    maxDiscountRatePercent: null,
    forceManualReview: false
  }) || '',
  /最低售价不能高于最高售价/,
  'rejects inconsistent price bounds'
)

assert.match(
  validatePricingConstraintForm({
    minProfitRatePercent: 0,
    minPrice: null,
    maxPrice: null,
    maxDiscountRatePercent: null,
    forceManualReview: false
  }) || '',
  /最低利润率/,
  'requires a positive minimum profit rate'
)

assert.match(
  validatePricingConstraintForm({
    minProfitRatePercent: 100,
    minPrice: null,
    maxPrice: null,
    maxDiscountRatePercent: null,
    forceManualReview: false
  }) || '',
  /最低利润率/,
  'rejects a 100% minimum profit rate because backend risk control divides by 1 - rate'
)

console.log('pricing constraint tests passed')

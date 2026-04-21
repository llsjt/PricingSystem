/**
 * 定价约束表单工具，统一生成默认值、序列化结果和前置校验。
 */

export interface PricingConstraintForm {
  minProfitRatePercent: number | null
  minPrice?: number | null
  maxPrice?: number | null
  maxDiscountRatePercent?: number | null
  forceManualReview: boolean
}

type PricingConstraintPayload = {
  min_profit_rate: number
  min_price?: number
  max_price?: number
  max_discount_rate?: number
  force_manual_review?: boolean
}

export const createDefaultPricingConstraintForm = (): PricingConstraintForm => ({
  minProfitRatePercent: 15,
  minPrice: null,
  maxPrice: null,
  maxDiscountRatePercent: null,
  forceManualReview: false
})

const isBlank = (value: unknown) => value === null || value === undefined || value === ''

const toFiniteNumber = (value: unknown): number | null => {
  if (isBlank(value)) return null
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? numberValue : null
}

const roundTo = (value: number, precision: number) => Number(value.toFixed(precision))
const toRate = (percent: number) => roundTo(percent / 100, 6)
const toMoney = (amount: number) => roundTo(amount, 2)

export const validatePricingConstraintForm = (form: PricingConstraintForm): string | null => {
  const minProfitRate = toFiniteNumber(form.minProfitRatePercent)
  if (minProfitRate === null || minProfitRate <= 0 || minProfitRate >= 100) {
    return '最低利润率需大于 0 且小于 100%'
  }

  const minPrice = toFiniteNumber(form.minPrice)
  if (form.minPrice != null && minPrice === null) return '最低售价格式不正确'
  if (minPrice !== null && minPrice <= 0) return '最低售价需大于 0'

  const maxPrice = toFiniteNumber(form.maxPrice)
  if (form.maxPrice != null && maxPrice === null) return '最高售价格式不正确'
  if (maxPrice !== null && maxPrice <= 0) return '最高售价需大于 0'
  if (minPrice !== null && maxPrice !== null && minPrice > maxPrice) {
    return '最低售价不能高于最高售价'
  }

  const maxDiscountRate = toFiniteNumber(form.maxDiscountRatePercent)
  if (form.maxDiscountRatePercent != null && maxDiscountRate === null) return '最大降价幅度格式不正确'
  if (maxDiscountRate !== null && (maxDiscountRate <= 0 || maxDiscountRate > 100)) {
    return '最大降价幅度需大于 0 且不超过 100%'
  }

  return null
}

export const serializePricingConstraints = (form: PricingConstraintForm): string => {
  const error = validatePricingConstraintForm(form)
  if (error) throw new Error(error)

  const payload: PricingConstraintPayload = {
    min_profit_rate: toRate(Number(form.minProfitRatePercent))
  }

  const minPrice = toFiniteNumber(form.minPrice)
  if (minPrice !== null) payload.min_price = toMoney(minPrice)

  const maxPrice = toFiniteNumber(form.maxPrice)
  if (maxPrice !== null) payload.max_price = toMoney(maxPrice)

  const maxDiscountRate = toFiniteNumber(form.maxDiscountRatePercent)
  if (maxDiscountRate !== null) payload.max_discount_rate = toRate(maxDiscountRate)

  if (form.forceManualReview) payload.force_manual_review = true

  return JSON.stringify(payload)
}

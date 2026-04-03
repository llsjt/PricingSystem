export interface NumericFormatOptions {
  fractionDigits?: number
  fallbackText?: string
  defaultValue?: number
  locale?: string
}

export interface CurrencyFormatOptions extends NumericFormatOptions {
  symbol?: string
}

export interface PercentFormatOptions extends NumericFormatOptions {
  multiplier?: number
}

const DEFAULT_LOCALE = 'zh-CN'

export const toFiniteNumber = (value: unknown): number | null => {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

const resolveNumber = (value: unknown, options?: NumericFormatOptions) => {
  const numeric = toFiniteNumber(value)
  if (numeric != null) {
    return numeric
  }
  if (options?.fallbackText != null) {
    return null
  }
  return options?.defaultValue ?? 0
}

export const formatNumber = (value: unknown, options: NumericFormatOptions = {}) => {
  const numeric = resolveNumber(value, options)
  if (numeric == null) {
    return options.fallbackText ?? '-'
  }

  const fractionDigits = options.fractionDigits ?? 0
  return numeric.toLocaleString(options.locale || DEFAULT_LOCALE, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits
  })
}

export const formatCount = (value: unknown, options: NumericFormatOptions = {}) =>
  formatNumber(value, {
    defaultValue: 0,
    fractionDigits: 0,
    ...options
  })

export const formatCurrency = (value: unknown, options: CurrencyFormatOptions = {}) => {
  const symbol = options.symbol ?? '¥'
  const numeric = resolveNumber(value, options)
  if (numeric == null) {
    return options.fallbackText ?? '-'
  }

  return `${symbol}${formatNumber(numeric, {
    defaultValue: 0,
    fractionDigits: options.fractionDigits ?? 2,
    locale: options.locale
  })}`
}

export const formatSignedNumber = (value: unknown, options: NumericFormatOptions = {}) => {
  const numeric = resolveNumber(value, options)
  if (numeric == null) {
    return options.fallbackText ?? '-'
  }

  const sign = numeric >= 0 ? '+' : '-'
  return `${sign}${formatNumber(Math.abs(numeric), {
    defaultValue: 0,
    fractionDigits: options.fractionDigits ?? 0,
    locale: options.locale
  })}`
}

export const formatSignedCurrency = (value: unknown, options: CurrencyFormatOptions = {}) => {
  const numeric = resolveNumber(value, options)
  if (numeric == null) {
    return options.fallbackText ?? '-'
  }

  const sign = numeric >= 0 ? '+' : '-'
  return `${sign}${formatCurrency(Math.abs(numeric), {
    symbol: options.symbol,
    defaultValue: 0,
    fractionDigits: options.fractionDigits ?? 2,
    locale: options.locale
  })}`
}

export const formatPercent = (value: unknown, options: PercentFormatOptions = {}) => {
  const numeric = resolveNumber(value, options)
  if (numeric == null) {
    return options.fallbackText ?? '-'
  }

  const multiplier = options.multiplier ?? 100
  return `${(numeric * multiplier).toFixed(options.fractionDigits ?? 2)}%`
}

export const formatSignedPercent = (value: unknown, options: PercentFormatOptions = {}) => {
  const numeric = resolveNumber(value, options)
  if (numeric == null) {
    return options.fallbackText ?? '-'
  }

  const multiplier = options.multiplier ?? 100
  const scaled = numeric * multiplier
  return `${scaled >= 0 ? '+' : ''}${scaled.toFixed(options.fractionDigits ?? 2)}%`
}

export const formatDateTime = (
  value?: string | Date | null,
  options: {
    fallbackText?: string
    includeSeconds?: boolean
  } = {}
) => {
  if (!value) {
    return options.fallbackText ?? '-'
  }

  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) {
    return typeof value === 'string' ? value : options.fallbackText ?? '-'
  }

  const year = date.getFullYear()
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')
  const hour = `${date.getHours()}`.padStart(2, '0')
  const minute = `${date.getMinutes()}`.padStart(2, '0')
  const second = `${date.getSeconds()}`.padStart(2, '0')

  return options.includeSeconds
    ? `${year}-${month}-${day} ${hour}:${minute}:${second}`
    : `${year}-${month}-${day} ${hour}:${minute}`
}

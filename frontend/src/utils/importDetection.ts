import type { ImportDataType } from '../api/product'

export type SupportedImportType = Exclude<ImportDataType, 'AUTO'>

export interface ImportDetectionRule {
  code: SupportedImportType
  label: string
  targetTable: string
  order: number
  detectGroups: string[][]
}

const importDetectionRules: ImportDetectionRule[] = [
  {
    code: 'PRODUCT_BASE',
    label: '\u5546\u54c1\u57fa\u7840\u4fe1\u606f',
    targetTable: 'product',
    order: 1,
    detectGroups: [
      ['\u5546\u54c1ID', '\u5546\u54c1\u7f16\u53f7', '\u5b9d\u8d1dID', 'Item ID'],
      ['\u5546\u54c1\u6807\u9898', '\u5b9d\u8d1d\u6807\u9898', '\u5546\u54c1\u540d\u79f0', '\u6807\u9898'],
      ['\u5f53\u524d\u552e\u4ef7', '\u552e\u4ef7', '\u9500\u552e\u4ef7', '\u4e00\u53e3\u4ef7', '\u5546\u54c1\u4ef7\u683c'],
      ['\u5e93\u5b58', '\u53ef\u552e\u5e93\u5b58', '\u603b\u5e93\u5b58']
    ]
  },
  {
    code: 'PRODUCT_SKU',
    label: '\u5546\u54c1 SKU',
    targetTable: 'product_sku',
    order: 2,
    detectGroups: [
      ['\u5546\u54c1ID', '\u5546\u54c1\u7f16\u53f7', '\u5b9d\u8d1dID', 'Item ID'],
      ['SKU ID', 'SKU\u7f16\u53f7', '\u89c4\u683cID', '\u5b50\u5546\u54c1ID', 'sku_id'],
      ['SKU\u5c5e\u6027', '\u89c4\u683c', '\u89c4\u683c\u5c5e\u6027', '\u9500\u552e\u5c5e\u6027'],
      ['SKU\u552e\u4ef7', 'SKU\u4ef7\u683c', '\u9500\u552e\u4ef7', '\u5f53\u524d\u552e\u4ef7'],
      ['SKU\u5e93\u5b58', '\u5e93\u5b58', '\u53ef\u552e\u5e93\u5b58']
    ]
  },
  {
    code: 'PRODUCT_DAILY_METRIC',
    label: '\u5546\u54c1\u65e5\u6307\u6807',
    targetTable: 'product_daily_metric',
    order: 3,
    detectGroups: [
      ['\u7edf\u8ba1\u65e5\u671f', '\u65e5\u671f', '\u6570\u636e\u65e5\u671f'],
      ['\u5546\u54c1ID', '\u5546\u54c1\u7f16\u53f7', '\u5b9d\u8d1dID', 'Item ID'],
      ['\u8bbf\u5ba2\u6570', '\u8bbf\u5ba2\u4eba\u6570', 'UV', '\u6d4f\u89c8\u8bbf\u5ba2\u6570'],
      ['\u652f\u4ed8\u4ef6\u6570', '\u9500\u91cf', '\u652f\u4ed8\u5546\u54c1\u4ef6\u6570'],
      ['\u652f\u4ed8\u91d1\u989d', '\u6210\u4ea4\u91d1\u989d', 'GMV']
    ]
  },
  {
    code: 'TRAFFIC_PROMO_DAILY',
    label: '\u6d41\u91cf\u4e0e\u63a8\u5e7f\u65e5\u6307\u6807',
    targetTable: 'traffic_promo_daily',
    order: 4,
    detectGroups: [
      ['\u7edf\u8ba1\u65e5\u671f', '\u65e5\u671f', '\u6570\u636e\u65e5\u671f'],
      ['\u6d41\u91cf\u6765\u6e90', '\u6765\u6e90\u6e20\u9053', '\u63a8\u5e7f\u6e20\u9053', '\u6e20\u9053'],
      ['\u5c55\u73b0\u91cf', '\u66dd\u5149\u91cf', '\u5c55\u793a\u6b21\u6570'],
      ['\u70b9\u51fb\u91cf', '\u70b9\u51fb\u6b21\u6570'],
      ['\u82b1\u8d39', '\u6d88\u8017', '\u63a8\u5e7f\u82b1\u8d39']
    ]
  }
]

let xlsxModulePromise: Promise<typeof import('xlsx')> | null = null

const loadXlsxModule = () => {
  if (!xlsxModulePromise) {
    xlsxModulePromise = import('xlsx')
  }
  return xlsxModulePromise
}

export function getImportDetectionRule(code: SupportedImportType | null | undefined) {
  return importDetectionRules.find((rule) => rule.code === code) || null
}

export function normalizeImportHeader(value: string) {
  return value
    .trim()
    .toLowerCase()
    .replace(/\uff08/g, '(')
    .replace(/\uff09/g, ')')
    .replace(/\uff1a/g, '')
    .replace(/:/g, '')
    .replace(/ /g, '')
    .replace(/\u3000/g, '')
    .replace(/_/g, '')
    .replace(/-/g, '')
    .replace(/\//g, '')
    .replace(/\\/g, '')
}

export function detectImportTypeFromHeaders(headers: Iterable<string>): SupportedImportType | null {
  const normalizedHeaders = new Set(
    Array.from(headers)
      .map((header) => normalizeImportHeader(header))
      .filter(Boolean)
  )

  let bestScore = -1
  let bestRule: ImportDetectionRule | null = null

  for (const rule of importDetectionRules) {
    let score = 0
    for (const group of rule.detectGroups) {
      const matched = group
        .map((header) => normalizeImportHeader(header))
        .some((header) => normalizedHeaders.has(header))
      if (matched) {
        score += 1
      }
    }

    if (score > bestScore) {
      bestScore = score
      bestRule = rule
    }
  }

  if (!bestRule || bestScore < 3) {
    return null
  }

  return bestRule.code
}

export async function detectImportTypeFromFile(file: File): Promise<SupportedImportType | null> {
  const XLSX = await loadXlsxModule()
  const buffer = await file.arrayBuffer()
  const workbook = XLSX.read(buffer, { type: 'array' })
  const firstSheetName = workbook.SheetNames[0]
  if (!firstSheetName) {
    throw new Error('Excel \u4e2d\u6ca1\u6709\u53ef\u8bfb\u53d6\u7684\u5de5\u4f5c\u8868')
  }

  const firstSheet = workbook.Sheets[firstSheetName]
  const rows = XLSX.utils.sheet_to_json<(string | number | null)[]>(firstSheet, {
    header: 1,
    raw: false,
    defval: '',
    blankrows: false
  })

  const headerRow = rows.find((row) => row.filter((cell) => String(cell ?? '').trim()).length >= 2)
  if (!headerRow) {
    throw new Error('Excel \u672a\u8bc6\u522b\u5230\u8868\u5934\uff0c\u8bf7\u68c0\u67e5\u9996\u884c\u662f\u5426\u4e3a\u5b57\u6bb5\u540d')
  }

  return detectImportTypeFromHeaders(headerRow.map((cell) => String(cell ?? '').trim()))
}

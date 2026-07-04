// 同 sale_time 的卡片共用一個顏色（同時間會合併結帳）
const GROUP_COLORS = [
  '#2563eb',
  '#d97706',
  '#16a34a',
  '#db2777',
  '#7c3aed',
  '#0d9488',
]

const assigned = new Map<string, string>()

// 與後端 gid 的時間前綴同構："2026-03-06 12:00" → "2026-03-06_1200"、空字串 → "now"
export function saleTimeKey(saleTime: string): string {
  return saleTime ? saleTime.replace(/ /g, '_').replace(/:/g, '') : 'now'
}

export function groupColor(key: string): string {
  let color = assigned.get(key)
  if (!color) {
    color = GROUP_COLORS[assigned.size % GROUP_COLORS.length]
    assigned.set(key, color)
  }
  return color
}

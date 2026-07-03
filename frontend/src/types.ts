// 與後端 /api/state 及 SSE 事件對應的型別

export interface AuthStatus {
  has_auth_state: boolean
  session_valid: boolean | null
  checked_at: number | null
}

export interface Product {
  id: string
  sale_time: string
  state: string
  info: string
  gid: string | null
}

export interface Group {
  sale_time: string
  phase: string
  member_pids: string[]
  progress: string
  logs: string[]
}

export interface CartResult {
  pid: string
  ok: boolean
  sold_out: boolean
  stage: string
  prodcount: number | null
  prodtotal: number | null
  raw: unknown
  error: string
}

export interface Payinfo {
  url: string
  cvc_filled: boolean
  auto_pay_clicked: boolean
  items: { name: string; raw?: string }[]
  total: string
  raw_text: string
  error: string
}

export interface CheckoutRecord {
  id: string
  created_at: string
  gid: string
  sale_time: string
  status: string
  completed: boolean
  cart_results: CartResult[]
  payinfo: Payinfo | null
  log_tail: string[]
}

export interface Snapshot {
  auth: AuthStatus
  products: Product[]
  groups: Record<string, Group>
  checkouts: CheckoutRecord[]
}

export interface ImportResult {
  ok: boolean
  format: string
  cookie_count: number
  pchome_cookie_count: number
  warning: string
  error: string
}

export type SseEvent =
  | { type: 'log'; gid: string; msg: string }
  | { type: 'progress'; gid: string; msg: string }
  | { type: 'job'; pid: string; state: string; info: string; gid: string | null }
  | {
      type: 'group'
      gid: string
      phase: string
      sale_time?: string
      member_pids: string[]
      status?: string
    }
  | { type: 'checkout'; record: CheckoutRecord }

// job 狀態 → 顯示文字
export const STATE_LABEL: Record<string, string> = {
  idle: '待命',
  queued: '等待中',
  monitoring: '監控中',
  forsale: '開賣！',
  soldout: '售完',
  carted: '已加車',
  awaiting_payment: '等待付款',
  success: '完成',
  cart_failed: '加車失敗',
  failed: '錯誤',
  session_expired: 'session 過期',
  not_logged_in: '未登入',
}

// job 狀態 → 徽章色系 class
export const STATE_CLASS: Record<string, string> = {
  queued: 'warn',
  monitoring: 'warn',
  awaiting_payment: 'warn',
  forsale: 'ok',
  carted: 'ok',
  success: 'ok',
  soldout: 'err',
  failed: 'err',
  cart_failed: 'err',
  session_expired: 'err',
  not_logged_in: 'err',
}

// 這些狀態表示 job 執行中（卡片顯示「取消／結束」）
export const ACTIVE_STATES = new Set([
  'queued',
  'monitoring',
  'forsale',
  'carted',
  'awaiting_payment',
])

export const CHECKOUT_STATUS_LABEL: Record<string, string> = {
  awaiting_payment: '等待付款',
  auto_paid: '已自動付款',
  cart_failed: '加車失敗',
}

export const GROUP_PHASE_LABEL: Record<string, string> = {
  pending: '準備中',
  lead_wait: '等待啟動',
  checking_session: '檢查登入',
  monitoring: '監控中',
  carting: '加入購物車',
  checkout: '結帳中',
  holding: '等待付款',
}

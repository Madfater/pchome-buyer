import type { AuthStatus, ImportResult, Snapshot } from './types'

async function api<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const data = await res.json()
      if (data.detail) detail = String(data.detail)
    } catch {
      /* 非 JSON 錯誤內容，保留狀態碼訊息 */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const fetchState = () => api<Snapshot>('GET', '/api/state')

export const addProduct = (ref: string, saleTime: string) =>
  api<Snapshot>('POST', '/api/products', { ref, sale_time: saleTime })

export const removeProduct = (pid: string) =>
  api<Snapshot>('DELETE', `/api/products/${encodeURIComponent(pid)}`)

export const startJobs = (pids: string[]) =>
  api<Snapshot>('POST', '/api/jobs/start', { pids })

export const cancelJobs = (pids: string[]) =>
  api<Snapshot>('POST', '/api/jobs/cancel', { pids })

export const completeCheckout = (id: string) =>
  api<Snapshot>('POST', `/api/checkouts/${encodeURIComponent(id)}/complete`)

export const clearCompletedCheckouts = () =>
  api<Snapshot>('DELETE', '/api/checkouts/completed')

export const importAuth = (payload: string) =>
  api<ImportResult>('POST', '/api/auth/import', { payload })

export const fetchAuthStatus = (live: boolean) =>
  api<AuthStatus>('GET', `/api/auth/status?live=${live ? 'true' : 'false'}`)

import { useState } from 'react'
import { clearCompletedCheckouts } from '../api'
import { groupColor, saleTimeKey } from '../colors'
import { useAppState, useApplySnapshot } from '../state'
import { useToast } from '../toast'
import { CHECKOUT_STATUS_LABEL, type CheckoutRecord } from '../types'
import CheckoutDetailDialog from './CheckoutDetailDialog'

export default function CheckoutGrid() {
  const { checkouts } = useAppState()
  const applySnapshot = useApplySnapshot()
  const toast = useToast()
  const [openId, setOpenId] = useState<string | null>(null)

  // 以 id 從 state 取出，SSE 更新（如標記完成）時 dialog 內容同步刷新
  const openRecord = checkouts.find((r) => r.id === openId) ?? null
  const completedCount = checkouts.filter((r) => r.completed).length

  const clearCompleted = async () => {
    try {
      applySnapshot(await clearCompletedCheckouts())
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <section>
      <div className="section-head">
        <h2>結帳紀錄</h2>
        <button onClick={clearCompleted} disabled={!completedCount}>
          清除已完成（{completedCount}）
        </button>
      </div>
      {checkouts.length === 0 ? (
        <div className="empty">尚無結帳紀錄</div>
      ) : (
        <div className="grid">
          {checkouts.map((r) => (
            <CheckoutCard
              key={r.id}
              record={r}
              onOpen={() => setOpenId(r.id)}
            />
          ))}
        </div>
      )}
      <CheckoutDetailDialog
        record={openRecord}
        onClose={() => setOpenId(null)}
      />
    </section>
  )
}

function CheckoutCard({
  record,
  onOpen,
}: {
  record: CheckoutRecord
  onOpen: () => void
}) {
  const okCount = record.cart_results.filter((r) => r.ok).length
  const total = record.payinfo?.total || lastProdTotal(record)

  return (
    <div
      className="card"
      style={
        {
          '--gcolor': groupColor(saleTimeKey(record.sale_time)),
        } as React.CSSProperties
      }
    >
      <div className="top-row">
        <span className="pid">
          {record.sale_time || record.created_at.replace('T', ' ')}
        </span>
      </div>
      <div className="sale">{record.created_at.replace('T', ' ')}</div>
      <div className="row">
        <span
          className={`status ${record.status === 'cart_failed' ? 'err' : record.completed ? 'ok' : 'warn'}`}
        >
          {record.completed
            ? '已完成'
            : (CHECKOUT_STATUS_LABEL[record.status] ?? record.status)}
        </span>
        <span className="info">
          成功 {okCount}/{record.cart_results.length} 件
          {total ? `，$${total}` : ''}
        </span>
      </div>
      <div className="row">
        <button onClick={onOpen}>查看詳情</button>
      </div>
    </div>
  )
}

function lastProdTotal(record: CheckoutRecord): string {
  for (let i = record.cart_results.length - 1; i >= 0; i--) {
    const t = record.cart_results[i].prodtotal
    if (t !== null && t !== undefined) return String(t)
  }
  return ''
}

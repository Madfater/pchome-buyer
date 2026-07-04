import { completeCheckout } from '../api'
import { useApplySnapshot } from '../state'
import { useToast } from '../toast'
import { CHECKOUT_STATUS_LABEL, type CheckoutRecord } from '../types'
import Dialog from './Dialog'

interface Props {
  record: CheckoutRecord | null
  onClose: () => void
}

export default function CheckoutDetailDialog({ record, onClose }: Props) {
  const applySnapshot = useApplySnapshot()
  const toast = useToast()

  const markComplete = async () => {
    if (!record) return
    try {
      applySnapshot(await completeCheckout(record.id))
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <Dialog open={record !== null} onClose={onClose} wide>
      {record && (
        <>
          <h3>結帳詳情</h3>
          <dl className="kv">
            <dt>時間</dt>
            <dd>{record.created_at.replace('T', ' ')}</dd>
            <dt>開賣時間</dt>
            <dd>{record.sale_time || '（立即監控）'}</dd>
            <dt>狀態</dt>
            <dd>
              {CHECKOUT_STATUS_LABEL[record.status] ?? record.status}
              {record.completed ? '（已完成）' : ''}
            </dd>
            <dt>群組</dt>
            <dd>{record.gid}</dd>
          </dl>

          <h3>加入購物車結果</h3>
          <table className="cart-table">
            <thead>
              <tr>
                <th>商品</th>
                <th>結果</th>
                {/* PRODCOUNT / PRODTOTAL 是加車後整車的累計值，不是該商品的數量與單價 */}
                <th>加車後車內件數</th>
                <th>加車後車內總額</th>
              </tr>
            </thead>
            <tbody>
              {record.cart_results.map((r) => (
                <tr key={r.pid}>
                  <td>{r.pid}</td>
                  <td>{r.ok ? '成功' : r.sold_out ? '售完' : `失敗（${r.stage}）`}</td>
                  <td>{r.prodcount ?? '—'}</td>
                  <td>{r.prodtotal != null ? `$${r.prodtotal}` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {record.payinfo && (
            <>
              <h3>結帳頁資訊</h3>
              <dl className="kv">
                <dt>頁面</dt>
                <dd>{record.payinfo.url}</dd>
                <dt>CVC</dt>
                <dd>{record.payinfo.cvc_filled ? '已自動填入' : '未填入'}</dd>
                <dt>自動付款</dt>
                <dd>{record.payinfo.auto_pay_clicked ? '已點擊確認付款' : '未點擊'}</dd>
                {record.payinfo.total && (
                  <>
                    <dt>總金額</dt>
                    <dd>{record.payinfo.total}</dd>
                  </>
                )}
              </dl>
              {record.payinfo.items.length > 0 && (
                <ul style={{ margin: 0, paddingLeft: 20, fontSize: '13.5px' }}>
                  {record.payinfo.items.map((item, i) => (
                    <li key={i}>{item.name}</li>
                  ))}
                </ul>
              )}
              {record.payinfo.raw_text && (
                <details>
                  <summary className="hint">結帳頁原始文字</summary>
                  <pre className="raw">{record.payinfo.raw_text}</pre>
                </details>
              )}
            </>
          )}

          {record.log_tail.length > 0 && (
            <details>
              <summary className="hint">執行日誌（最後 {record.log_tail.length} 行）</summary>
              <pre className="raw">{record.log_tail.join('\n')}</pre>
            </details>
          )}

          <div className="dialog-actions">
            {!record.completed && (
              <button className="primary" onClick={markComplete}>
                標記完成
              </button>
            )}
            <button onClick={onClose}>關閉</button>
          </div>
        </>
      )}
    </Dialog>
  )
}

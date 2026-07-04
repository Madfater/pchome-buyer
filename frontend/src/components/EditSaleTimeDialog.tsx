import { useEffect, useState } from 'react'
import { updateSaleTime } from '../api'
import { useApplySnapshot } from '../state'
import { useToast } from '../toast'
import type { Product } from '../types'
import Dialog from './Dialog'

interface Props {
  open: boolean
  product: Product
  onClose: () => void
}

export default function EditSaleTimeDialog({ open, product, onClose }: Props) {
  const applySnapshot = useApplySnapshot()
  const toast = useToast()
  const [saleTime, setSaleTime] = useState('')
  const [busy, setBusy] = useState(false)

  // 每次開啟時以目前值預填（datetime-local 用 "T" 分隔）
  useEffect(() => {
    if (open) setSaleTime(product.sale_time.replace(' ', 'T'))
  }, [open, product.sale_time])

  const submit = async () => {
    setBusy(true)
    try {
      applySnapshot(
        await updateSaleTime(product.id, saleTime.replace('T', ' ')),
      )
      onClose()
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose}>
      <h3>修改開賣時間</h3>
      <span className="hint pid">{product.id}</span>
      <label>
        開始監測時間（留空表示立即監控）
        <input
          type="datetime-local"
          step={60}
          value={saleTime}
          onChange={(e) => setSaleTime(e.target.value)}
          autoFocus
        />
      </label>
      <span className="hint">修改後會併入對應時間的組。</span>
      <div className="dialog-actions">
        <button onClick={onClose}>取消</button>
        <button className="primary" onClick={submit} disabled={busy}>
          {busy ? '儲存中…' : '儲存'}
        </button>
      </div>
    </Dialog>
  )
}

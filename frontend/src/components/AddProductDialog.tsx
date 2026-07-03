import { useMemo, useState } from 'react'
import { addProduct } from '../api'
import { useApplySnapshot } from '../state'
import { useToast } from '../toast'
import Dialog from './Dialog'

// 與後端 services/product_id.py 相同規則，僅供輸入預覽
const ID_RE = /^[A-Za-z0-9]+-[A-Za-z0-9]+$/
const URL_RE = /\/prod\/([A-Za-z0-9]+-[A-Za-z0-9]+)/

function previewPid(ref: string): string | null {
  const s = ref.trim()
  if (!s) return null
  if (ID_RE.test(s)) return s.toUpperCase()
  const m = URL_RE.exec(s)
  return m ? m[1].toUpperCase() : null
}

interface Props {
  open: boolean
  onClose: () => void
}

export default function AddProductDialog({ open, onClose }: Props) {
  const applySnapshot = useApplySnapshot()
  const toast = useToast()
  const [ref, setRef] = useState('')
  const [saleTime, setSaleTime] = useState('')
  const [busy, setBusy] = useState(false)

  const pid = useMemo(() => previewPid(ref), [ref])

  const submit = async () => {
    setBusy(true)
    try {
      // datetime-local 的 "T" 換成後端接受的空白分隔
      applySnapshot(await addProduct(ref, saleTime.replace('T', ' ')))
      setRef('')
      setSaleTime('')
      onClose()
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose}>
      <h3>新增搶購任務</h3>
      <label>
        商品網址或編號
        <input
          value={ref}
          onChange={(e) => setRef(e.target.value)}
          placeholder="https://24h.pchome.com.tw/prod/DGCQ39-A900JESMM"
          autoFocus
        />
      </label>
      <span className="hint">
        {ref.trim()
          ? pid
            ? `商品編號：${pid}`
            : '無法解析商品編號'
          : '貼上 PChome 24h 商品頁網址，或直接輸入商品編號'}
      </span>
      <label>
        開始監測時間（留空表示立即監控）
        <input
          type="datetime-local"
          step={60}
          value={saleTime}
          onChange={(e) => setSaleTime(e.target.value)}
        />
      </label>
      <span className="hint">開賣時間相同的任務啟動後會合併為一組，一起加車結帳。</span>
      <div className="dialog-actions">
        <button onClick={onClose}>取消</button>
        <button className="primary" onClick={submit} disabled={busy || !pid}>
          {busy ? '新增中…' : '新增'}
        </button>
      </div>
    </Dialog>
  )
}

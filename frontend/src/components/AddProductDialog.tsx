import { useEffect, useMemo, useState } from 'react'
import { addProduct, previewProduct } from '../api'
import { useApplySnapshot } from '../state'
import { useToast } from '../toast'
import type { ProductPreview } from '../types'
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
  const [preview, setPreview] = useState<ProductPreview | null>(null)
  const [previewLoading, setPreviewLoading] = useState(false)

  const pid = useMemo(() => previewPid(ref), [ref])

  // 貼上網址/編號後 debounce 抓一次商品資訊，讓使用者在啟動監控前先確認貼對商品
  useEffect(() => {
    setPreview(null)
    if (!pid) return
    setPreviewLoading(true)
    const timer = setTimeout(() => {
      previewProduct(ref)
        .then(setPreview)
        .catch(() => setPreview(null))
        .finally(() => setPreviewLoading(false))
    }, 350)
    return () => {
      clearTimeout(timer)
      setPreviewLoading(false)
    }
  }, [pid, ref])

  const submit = async () => {
    setBusy(true)
    try {
      // datetime-local 的 "T" 換成後端接受的空白分隔
      applySnapshot(await addProduct(ref, saleTime.replace('T', ' ')))
      setRef('')
      setSaleTime('')
      setPreview(null)
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
      {pid && previewLoading && <span className="hint">查詢商品資訊中…</span>}
      {pid && !previewLoading && preview && (preview.name || preview.image) && (
        <div className="product-preview">
          {preview.image ? (
            <img className="thumb" src={preview.image} alt="" />
          ) : (
            <div className="thumb placeholder" aria-hidden="true" />
          )}
          <div className="title-block">
            <span className="name">{preview.name || pid}</span>
            {preview.price != null && (
              <span className="price">
                ${preview.price.toLocaleString()}
                {preview.orig_price != null &&
                  preview.orig_price > preview.price && (
                    <span className="orig-price">
                      ${preview.orig_price.toLocaleString()}
                    </span>
                  )}
              </span>
            )}
            {preview.is_spec && (
              <span
                className="badge warn"
                title="此商品有多種規格（顏色/尺寸等），本工具僅會加購預設款式，請先確認預設組合是否為你要的"
              >
                含規格選項
              </span>
            )}
          </div>
        </div>
      )}
      {pid && !previewLoading && preview && !preview.name && !preview.image && (
        <span className="hint">查無商品資訊，仍可新增</span>
      )}
      <label>
        開始監測時間（留空表示立即監控）
        <input
          type="datetime-local"
          step={60}
          value={saleTime}
          onChange={(e) => setSaleTime(e.target.value)}
        />
      </label>
      <span className="hint">
        開賣時間相同的任務啟動後會合併為一組，一起加車結帳。
      </span>
      <div className="dialog-actions">
        <button onClick={onClose}>取消</button>
        <button className="primary" onClick={submit} disabled={busy || !pid}>
          {busy ? '新增中…' : '新增'}
        </button>
      </div>
    </Dialog>
  )
}

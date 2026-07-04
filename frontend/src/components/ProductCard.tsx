import { useState } from 'react'
import { cancelJobs, removeProduct, startJobs } from '../api'
import { groupColor, saleTimeKey } from '../colors'
import { useAppState, useApplySnapshot } from '../state'
import { useToast } from '../toast'
import {
  ACTIVE_STATES,
  GROUP_PHASE_LABEL,
  STATE_CLASS,
  STATE_LABEL,
  type Product,
} from '../types'
import ConfirmDialog from './ConfirmDialog'
import EditSaleTimeDialog from './EditSaleTimeDialog'

interface Props {
  product: Product
  selected: boolean
  onToggle: () => void
}

export default function ProductCard({ product, selected, onToggle }: Props) {
  const { groups } = useAppState()
  const applySnapshot = useApplySnapshot()
  const toast = useToast()
  const [confirm, setConfirm] = useState<'remove' | 'release' | null>(null)
  const [editOpen, setEditOpen] = useState(false)

  const active = ACTIVE_STATES.has(product.state)
  const group = product.gid ? groups[product.gid] : undefined
  const holding = group?.phase === 'holding'

  const call = async (fn: () => ReturnType<typeof startJobs>) => {
    try {
      applySnapshot(await fn())
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div
      className={`card${selected ? ' selected' : ''}`}
      style={
        {
          '--gcolor': groupColor(saleTimeKey(product.sale_time)),
        } as React.CSSProperties
      }
    >
      <div className="top-row">
        <input
          type="checkbox"
          checked={selected}
          onChange={onToggle}
          aria-label="選取任務"
        />
        {product.image ? (
          <img className="thumb" src={product.image} alt="" />
        ) : (
          <div className="thumb placeholder" aria-hidden="true" />
        )}
        <div className="title-block">
          <span className="name" title={product.name || product.id}>
            {product.name || product.id}
          </span>
          {product.name && <span className="pid">{product.id}</span>}
        </div>
        <button
          className="edit"
          title="修改開賣時間"
          disabled={active}
          onClick={() => setEditOpen(true)}
        >
          ✎
        </button>
        <button
          className="remove"
          title="刪除任務"
          disabled={active}
          onClick={() => setConfirm('remove')}
        >
          ✕
        </button>
      </div>
      {(product.price != null ||
        product.is_spec ||
        product.is_eticket ||
        product.is_preorder) && (
        <div className="meta-row">
          {product.price != null && (
            <span className="price">
              ${product.price.toLocaleString()}
              {product.orig_price != null &&
                product.orig_price > product.price && (
                  <span className="orig-price">
                    ${product.orig_price.toLocaleString()}
                  </span>
                )}
            </span>
          )}
          {product.is_spec && (
            <span
              className="badge warn"
              title="此商品有多種規格（顏色/尺寸等），本工具僅會加購預設款式，請先確認預設組合是否為你要的"
            >
              含規格選項
            </span>
          )}
          {product.is_eticket && <span className="badge">電子票券</span>}
          {product.is_preorder && <span className="badge">預購</span>}
        </div>
      )}
      <div className="sale">
        {product.sale_time ? `開賣 ${product.sale_time}` : '立即監控'}
      </div>
      <div className="row">
        <span className={`status ${STATE_CLASS[product.state] ?? ''}`}>
          {STATE_LABEL[product.state] ?? product.state}
        </span>
        {product.info && <span className="info">{product.info}</span>}
        {active ? (
          holding ? (
            <button className="danger" onClick={() => setConfirm('release')}>
              結束（關閉瀏覽器）
            </button>
          ) : (
            <button
              className="danger"
              onClick={() => call(() => cancelJobs([product.id]))}
            >
              取消
            </button>
          )
        ) : (
          <button
            className="primary"
            onClick={() => call(() => startJobs([product.id]))}
          >
            開始
          </button>
        )}
      </div>
      {group && (
        <div className="progress">
          {GROUP_PHASE_LABEL[group.phase] ?? group.phase}
          {group.progress ? ` — ${group.progress}` : ''}
        </div>
      )}
      <EditSaleTimeDialog
        open={editOpen}
        product={product}
        onClose={() => setEditOpen(false)}
      />
      <ConfirmDialog
        open={confirm === 'remove'}
        title="刪除任務"
        message={`將刪除 ${product.id}，此操作無法復原。`}
        confirmLabel="刪除"
        onConfirm={() => {
          setConfirm(null)
          call(() => removeProduct(product.id))
        }}
        onClose={() => setConfirm(null)}
      />
      <ConfirmDialog
        open={confirm === 'release'}
        title="結束並關閉瀏覽器"
        message="這個組的所有任務共用同一個瀏覽器，結束後將關閉結帳頁面。請確認已完成付款。"
        confirmLabel="結束"
        onConfirm={() => {
          setConfirm(null)
          call(() => cancelJobs([product.id]))
        }}
        onClose={() => setConfirm(null)}
      />
    </div>
  )
}

import { cancelJobs, removeProduct, startJobs } from '../api'
import { groupColor, saleTimeKey } from '../colors'
import { useAppState, useApplySnapshot } from '../state'
import { useToast } from '../toast'
import { ACTIVE_STATES, GROUP_PHASE_LABEL, STATE_CLASS, STATE_LABEL, type Product } from '../types'

interface Props {
  product: Product
  selected: boolean
  onToggle: () => void
}

export default function ProductCard({ product, selected, onToggle }: Props) {
  const { groups } = useAppState()
  const applySnapshot = useApplySnapshot()
  const toast = useToast()

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
      style={{ '--gcolor': groupColor(saleTimeKey(product.sale_time)) } as React.CSSProperties}
    >
      <div className="top-row">
        <input type="checkbox" checked={selected} onChange={onToggle} aria-label="選取任務" />
        <span className="pid">{product.id}</span>
        <button
          className="remove"
          title="刪除任務"
          disabled={active}
          onClick={() => call(() => removeProduct(product.id))}
        >
          ✕
        </button>
      </div>
      <div className="sale">
        {product.sale_time ? `開賣 ${product.sale_time}` : '立即監控'}
      </div>
      <div className="row">
        <span className={`status ${STATE_CLASS[product.state] ?? ''}`}>
          {STATE_LABEL[product.state] ?? product.state}
        </span>
        {product.info && <span className="info">{product.info}</span>}
        {active ? (
          <button className="danger" onClick={() => call(() => cancelJobs([product.id]))}>
            {holding ? '結束（關閉瀏覽器）' : '取消'}
          </button>
        ) : (
          <button className="primary" onClick={() => call(() => startJobs([product.id]))}>
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
    </div>
  )
}

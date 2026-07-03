import { useMemo, useState } from 'react'
import { cancelJobs, startJobs } from '../api'
import { useAppState, useApplySnapshot } from '../state'
import { useToast } from '../toast'
import { ACTIVE_STATES } from '../types'
import AddProductDialog from './AddProductDialog'
import ProductCard from './ProductCard'

export default function ProductGrid() {
  const { products } = useAppState()
  const applySnapshot = useApplySnapshot()
  const toast = useToast()
  const [addOpen, setAddOpen] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())

  // 商品被刪除後，殘留的勾選一併忽略
  const selectedPids = useMemo(
    () => products.filter((p) => selected.has(p.id)).map((p) => p.id),
    [products, selected],
  )

  const toggle = (pid: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(pid)) next.delete(pid)
      else next.add(pid)
      return next
    })
  }

  const run = async (fn: (pids: string[]) => Promise<Parameters<typeof applySnapshot>[0]>, pids: string[]) => {
    try {
      applySnapshot(await fn(pids))
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e))
    }
  }

  const startable = selectedPids.filter(
    (pid) => !ACTIVE_STATES.has(products.find((p) => p.id === pid)?.state ?? ''),
  )
  const cancellable = selectedPids.filter((pid) =>
    ACTIVE_STATES.has(products.find((p) => p.id === pid)?.state ?? ''),
  )

  return (
    <section>
      <div className="section-head">
        <h2>搶購任務</h2>
        <span className="hint">開賣時間相同的任務會併入同一個瀏覽器一起結帳</span>
        <button className="primary" onClick={() => setAddOpen(true)}>
          ＋ 新增任務
        </button>
      </div>

      {selectedPids.length > 0 && (
        <div className="bulkbar">
          <span>已選 {selectedPids.length} 個</span>
          <button
            className="primary"
            disabled={!startable.length}
            onClick={() => run(startJobs, startable)}
          >
            啟動選取（{startable.length}）
          </button>
          <button
            className="danger"
            disabled={!cancellable.length}
            onClick={() => run(cancelJobs, cancellable)}
          >
            取消選取（{cancellable.length}）
          </button>
          <button onClick={() => setSelected(new Set(products.map((p) => p.id)))}>全選</button>
          <button onClick={() => setSelected(new Set())}>清除選取</button>
        </div>
      )}

      {products.length === 0 ? (
        <div className="empty">尚未新增任務，按「＋ 新增任務」貼上商品網址開始</div>
      ) : (
        <div className="grid">
          {products.map((p) => (
            <ProductCard
              key={p.id}
              product={p}
              selected={selected.has(p.id)}
              onToggle={() => toggle(p.id)}
            />
          ))}
        </div>
      )}

      <AddProductDialog open={addOpen} onClose={() => setAddOpen(false)} />
    </section>
  )
}

import { useEffect, useMemo, useRef, useState } from 'react'
import { cancelJobs, removeProducts, startJobs } from '../api'
import { groupColor, saleTimeKey } from '../colors'
import { useAppState, useApplySnapshot } from '../state'
import { useToast } from '../toast'
import { ACTIVE_STATES, type Product } from '../types'
import AddProductDialog from './AddProductDialog'
import ConfirmDialog from './ConfirmDialog'
import ProductCard from './ProductCard'

interface GroupSectionProps {
  saleTime: string
  items: Product[]
  selected: Set<string>
  onToggle: (pid: string) => void
  onToggleGroup: (pids: string[], selectAll: boolean) => void
}

function GroupSection({
  saleTime,
  items,
  selected,
  onToggle,
  onToggleGroup,
}: GroupSectionProps) {
  const headRef = useRef<HTMLInputElement>(null)
  const selectedCount = items.filter((p) => selected.has(p.id)).length
  const allSelected = selectedCount === items.length

  // indeterminate 沒有宣告式 prop，只能命令式設定
  useEffect(() => {
    if (headRef.current)
      headRef.current.indeterminate = selectedCount > 0 && !allSelected
  }, [selectedCount, allSelected])

  return (
    <section
      className="group-section"
      style={
        { '--gcolor': groupColor(saleTimeKey(saleTime)) } as React.CSSProperties
      }
    >
      <div className="group-head">
        <input
          ref={headRef}
          type="checkbox"
          checked={allSelected}
          onChange={() =>
            onToggleGroup(
              items.map((p) => p.id),
              !allSelected,
            )
          }
          aria-label="選取整組"
        />
        <span className="group-dot" />
        <span className="group-title">
          {saleTime ? `開賣 ${saleTime}` : '立即監控'}
        </span>
        <span className="hint">{items.length} 個任務</span>
      </div>
      <div className="grid">
        {items.map((p) => (
          <ProductCard
            key={p.id}
            product={p}
            selected={selected.has(p.id)}
            onToggle={() => onToggle(p.id)}
          />
        ))}
      </div>
    </section>
  )
}

export default function ProductGrid() {
  const { products } = useAppState()
  const applySnapshot = useApplySnapshot()
  const toast = useToast()
  const [addOpen, setAddOpen] = useState(false)
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set())

  // 商品被刪除後，同步修剪選取集（size 不變就回傳原 Set 避免多餘 render）
  useEffect(() => {
    setSelected((prev) => {
      const live = new Set(products.map((p) => p.id))
      const next = new Set([...prev].filter((pid) => live.has(pid)))
      return next.size === prev.size ? prev : next
    })
  }, [products])

  const selectedPids = useMemo(
    () => products.filter((p) => selected.has(p.id)).map((p) => p.id),
    [products, selected],
  )

  // 依 sale_time 分組：立即監控（空字串）最前，其後依時間遞增；組內保留清單順序
  const groups = useMemo(() => {
    const by = new Map<string, Product[]>()
    for (const p of products) {
      const list = by.get(p.sale_time) ?? []
      list.push(p)
      by.set(p.sale_time, list)
    }
    return [...by.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([saleTime, items]) => ({ saleTime, items }))
  }, [products])

  const toggle = (pid: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(pid)) next.delete(pid)
      else next.add(pid)
      return next
    })
  }

  const toggleGroup = (pids: string[], selectAll: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev)
      for (const pid of pids) {
        if (selectAll) next.add(pid)
        else next.delete(pid)
      }
      return next
    })
  }

  const run = async (
    fn: (pids: string[]) => Promise<Parameters<typeof applySnapshot>[0]>,
    pids: string[],
  ) => {
    try {
      applySnapshot(await fn(pids))
      // 批次成功後清除選取；失敗保留供重試
      setSelected(new Set())
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e))
    }
  }

  const startable = selectedPids.filter(
    (pid) =>
      !ACTIVE_STATES.has(products.find((p) => p.id === pid)?.state ?? ''),
  )
  const cancellable = selectedPids.filter((pid) =>
    ACTIVE_STATES.has(products.find((p) => p.id === pid)?.state ?? ''),
  )

  return (
    <section>
      <div className="section-head">
        <h2>搶購任務</h2>
        <span className="hint">
          開賣時間相同的任務會併入同一個瀏覽器一起結帳
        </span>
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
          <button
            className="danger"
            disabled={!startable.length}
            onClick={() => setBulkDeleteOpen(true)}
          >
            刪除選取（{startable.length}）
          </button>
          <button
            onClick={() => setSelected(new Set(products.map((p) => p.id)))}
          >
            全選
          </button>
          <button onClick={() => setSelected(new Set())}>清除選取</button>
        </div>
      )}

      {products.length === 0 ? (
        <div className="empty">
          尚未新增任務，按「＋ 新增任務」貼上商品網址開始
        </div>
      ) : (
        groups.map((g) => (
          <GroupSection
            key={saleTimeKey(g.saleTime)}
            saleTime={g.saleTime}
            items={g.items}
            selected={selected}
            onToggle={toggle}
            onToggleGroup={toggleGroup}
          />
        ))
      )}

      <AddProductDialog open={addOpen} onClose={() => setAddOpen(false)} />
      <ConfirmDialog
        open={bulkDeleteOpen}
        title="刪除任務"
        message={`將刪除 ${startable.length} 個未執行的任務，執行中的任務不受影響。此操作無法復原。`}
        confirmLabel="刪除"
        onConfirm={() => {
          setBulkDeleteOpen(false)
          run(removeProducts, startable)
        }}
        onClose={() => setBulkDeleteOpen(false)}
      />
    </section>
  )
}

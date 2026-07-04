import { useEffect, useMemo, useRef, useState } from 'react'
import { groupColor } from '../colors'
import { useAppDispatch, useAppState } from '../state'

// gid 形如 "2026-03-06_1200#1"，取 # 前的時間部分對應群組顏色
const gidKey = (gid: string) => gid.split('#')[0]

export default function LogPanel() {
  const { logs } = useAppState()
  const dispatch = useAppDispatch()
  const [filter, setFilter] = useState('')
  const panel = useRef<HTMLDivElement>(null)

  const gids = useMemo(() => [...new Set(logs.map((l) => l.gid))], [logs])
  const shown = filter ? logs.filter((l) => l.gid === filter) : logs

  useEffect(() => {
    const el = panel.current
    if (el) el.scrollTop = el.scrollHeight
  }, [shown.length])

  return (
    <section>
      <div className="section-head">
        <h2>日誌</h2>
        {gids.length > 1 && (
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="">全部群組</option>
            {gids.map((gid) => (
              <option key={gid} value={gid}>
                {gid}
              </option>
            ))}
          </select>
        )}
        <button
          disabled={!logs.length}
          onClick={() => {
            dispatch({ type: 'clear-logs' })
            setFilter('')
          }}
        >
          清除日誌
        </button>
      </div>
      <div className="log-panel" ref={panel}>
        {shown.length === 0 ? (
          <span className="hint">尚無日誌</span>
        ) : (
          shown.map((l, i) => (
            <div key={i}>
              <span
                className="gtag"
                style={{ color: groupColor(gidKey(l.gid)) }}
              >
                [{l.gid}]
              </span>{' '}
              {l.msg}
            </div>
          ))
        )}
      </div>
    </section>
  )
}

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useReducer,
  useRef,
  type Dispatch,
  type ReactNode,
} from 'react'
import { fetchState } from './api'
import type { AuthStatus, Snapshot, SseEvent } from './types'

const MAX_LOG_LINES = 500

export interface LogLine {
  gid: string
  msg: string
}

export interface AppState extends Snapshot {
  logs: LogLine[]
  connected: boolean
}

export type Action =
  | { type: 'snapshot'; snapshot: Snapshot }
  | { type: 'auth'; auth: AuthStatus }
  | { type: 'connected'; connected: boolean }
  | { type: 'clear-logs' }
  | { type: 'sse'; event: SseEvent }

export const initialState: AppState = {
  auth: { has_auth_state: false, session_valid: null, checked_at: null },
  products: [],
  groups: {},
  checkouts: [],
  logs: [],
  connected: false,
}

export function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case 'snapshot':
      return { ...state, ...action.snapshot }
    case 'auth':
      return { ...state, auth: action.auth }
    case 'connected':
      return { ...state, connected: action.connected }
    case 'clear-logs':
      return { ...state, logs: [] }
    case 'sse':
      return applySse(state, action.event)
  }
}

function applySse(state: AppState, ev: SseEvent): AppState {
  switch (ev.type) {
    case 'log':
      return {
        ...state,
        logs: [...state.logs.slice(-(MAX_LOG_LINES - 1)), { gid: ev.gid, msg: ev.msg }],
      }
    case 'progress': {
      const group = state.groups[ev.gid]
      if (!group) return state
      return {
        ...state,
        groups: { ...state.groups, [ev.gid]: { ...group, progress: ev.msg } },
      }
    }
    case 'job':
      return {
        ...state,
        products: state.products.map((p) =>
          p.id === ev.pid ? { ...p, state: ev.state, info: ev.info, gid: ev.gid } : p,
        ),
      }
    case 'group': {
      if (ev.phase === 'closed') {
        const groups = { ...state.groups }
        delete groups[ev.gid]
        return { ...state, groups }
      }
      const prev = state.groups[ev.gid]
      return {
        ...state,
        groups: {
          ...state.groups,
          [ev.gid]: {
            sale_time: ev.sale_time ?? prev?.sale_time ?? '',
            phase: ev.phase,
            member_pids: ev.member_pids,
            progress: prev?.progress ?? '',
            logs: prev?.logs ?? [],
          },
        },
      }
    }
    case 'checkout': {
      const rest = state.checkouts.filter((r) => r.id !== ev.record.id)
      const existed = state.checkouts.some((r) => r.id === ev.record.id)
      return {
        ...state,
        checkouts: existed
          ? state.checkouts.map((r) => (r.id === ev.record.id ? ev.record : r))
          : [ev.record, ...rest],
      }
    }
  }
}

const StateContext = createContext<AppState>(initialState)
const DispatchContext = createContext<Dispatch<Action>>(() => {})

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState)
  useSse(dispatch)
  return (
    <StateContext.Provider value={state}>
      <DispatchContext.Provider value={dispatch}>{children}</DispatchContext.Provider>
    </StateContext.Provider>
  )
}

export const useAppState = () => useContext(StateContext)
export const useAppDispatch = () => useContext(DispatchContext)

/** 對變更狀態的 API 呼叫套用回傳的完整快照 */
export function useApplySnapshot() {
  const dispatch = useAppDispatch()
  return useCallback(
    (snapshot: Snapshot) => dispatch({ type: 'snapshot', snapshot }),
    [dispatch],
  )
}

function useSse(dispatch: Dispatch<Action>) {
  const refreshing = useRef(false)

  useEffect(() => {
    const refresh = async () => {
      if (refreshing.current) return
      refreshing.current = true
      try {
        dispatch({ type: 'snapshot', snapshot: await fetchState() })
      } catch {
        /* 伺服器暫時不可達，SSE 重連後會再試 */
      } finally {
        refreshing.current = false
      }
    }

    const es = new EventSource('/api/events')
    es.onopen = () => {
      dispatch({ type: 'connected', connected: true })
      // 連線（重連）成功後重抓快照，補回斷線期間漏掉的事件
      void refresh()
    }
    es.onerror = () => dispatch({ type: 'connected', connected: false })
    es.onmessage = (e) => {
      try {
        dispatch({ type: 'sse', event: JSON.parse(e.data) as SseEvent })
      } catch {
        /* 忽略無法解析的事件 */
      }
    }
    return () => es.close()
  }, [dispatch])
}

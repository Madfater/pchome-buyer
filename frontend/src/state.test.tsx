import { describe, expect, it } from 'vitest'
import { initialState, reducer } from './state'
import type { CheckoutRecord, Product, Snapshot } from './types'

function product(overrides: Partial<Product> = {}): Product {
  return {
    id: 'A-1',
    sale_time: '',
    state: 'idle',
    info: '',
    gid: null,
    ...overrides,
  }
}

function checkout(overrides: Partial<CheckoutRecord> = {}): CheckoutRecord {
  return {
    id: 'c1',
    created_at: '2026-03-06T12:00:00',
    gid: '2026-03-06_1200#1',
    sale_time: '2026-03-06 12:00',
    status: 'awaiting_payment',
    completed: false,
    cart_results: [],
    payinfo: null,
    log_tail: [],
    ...overrides,
  }
}

describe('reducer / snapshot', () => {
  it('merges a snapshot over the existing state, keeping logs/connected untouched', () => {
    const snapshot: Snapshot = {
      auth: initialState.auth,
      products: [product()],
      groups: {},
      checkouts: [],
    }
    const state = {
      ...initialState,
      connected: true,
      logs: [{ gid: 'g', msg: 'hi' }],
    }

    const next = reducer(state, { type: 'snapshot', snapshot })

    expect(next.products).toEqual([product()])
    expect(next.connected).toBe(true)
    expect(next.logs).toEqual([{ gid: 'g', msg: 'hi' }])
  })
})

describe('reducer / auth', () => {
  it('replaces the auth slice', () => {
    const next = reducer(initialState, {
      type: 'auth',
      auth: { has_auth_state: true, session_valid: true, checked_at: 123 },
    })
    expect(next.auth).toEqual({
      has_auth_state: true,
      session_valid: true,
      checked_at: 123,
    })
  })
})

describe('reducer / connected', () => {
  it('toggles the connected flag', () => {
    expect(
      reducer(initialState, { type: 'connected', connected: true }).connected,
    ).toBe(true)
    const connected = reducer(initialState, {
      type: 'connected',
      connected: true,
    })
    expect(
      reducer(connected, { type: 'connected', connected: false }).connected,
    ).toBe(false)
  })
})

describe('reducer / clear-logs', () => {
  it('empties the log list', () => {
    const state = { ...initialState, logs: [{ gid: 'g', msg: 'hi' }] }
    expect(reducer(state, { type: 'clear-logs' }).logs).toEqual([])
  })
})

describe('reducer / sse log', () => {
  it('appends a log line', () => {
    const next = reducer(initialState, {
      type: 'sse',
      event: { type: 'log', gid: 'g1', msg: 'hello' },
    })
    expect(next.logs).toEqual([{ gid: 'g1', msg: 'hello' }])
  })

  it('caps the log buffer at 500 lines, dropping the oldest', () => {
    const logs = Array.from({ length: 500 }, (_, i) => ({
      gid: 'g',
      msg: `line-${i}`,
    }))
    const state = { ...initialState, logs }

    const next = reducer(state, {
      type: 'sse',
      event: { type: 'log', gid: 'g', msg: 'line-500' },
    })

    expect(next.logs).toHaveLength(500)
    expect(next.logs[0]).toEqual({ gid: 'g', msg: 'line-1' })
    expect(next.logs[499]).toEqual({ gid: 'g', msg: 'line-500' })
  })
})

describe('reducer / sse progress', () => {
  it('updates progress text for an existing group', () => {
    const state = {
      ...initialState,
      groups: {
        g1: {
          sale_time: '',
          phase: 'monitoring',
          member_pids: ['A-1'],
          progress: '',
          logs: [],
        },
      },
    }

    const next = reducer(state, {
      type: 'sse',
      event: { type: 'progress', gid: 'g1', msg: '3/10' },
    })

    expect(next.groups.g1.progress).toBe('3/10')
  })

  it('is a no-op when the group does not exist (out-of-order SSE delivery)', () => {
    const next = reducer(initialState, {
      type: 'sse',
      event: { type: 'progress', gid: 'missing', msg: 'x' },
    })
    expect(next).toBe(initialState)
  })
})

describe('reducer / sse job', () => {
  it('updates the matching product by pid and leaves others untouched', () => {
    const state = {
      ...initialState,
      products: [product({ id: 'A-1' }), product({ id: 'A-2' })],
    }

    const next = reducer(state, {
      type: 'sse',
      event: {
        type: 'job',
        pid: 'A-1',
        state: 'forsale',
        info: '開賣',
        gid: 'g1',
      },
    })

    expect(next.products[0]).toMatchObject({
      id: 'A-1',
      state: 'forsale',
      info: '開賣',
      gid: 'g1',
    })
    expect(next.products[1]).toMatchObject({ id: 'A-2', state: 'idle' })
  })
})

describe('reducer / sse group', () => {
  it('creates a new group entry, defaulting progress/logs', () => {
    const next = reducer(initialState, {
      type: 'sse',
      event: {
        type: 'group',
        gid: 'g1',
        phase: 'monitoring',
        sale_time: '2026-03-06 12:00',
        member_pids: ['A-1'],
      },
    })

    expect(next.groups.g1).toEqual({
      sale_time: '2026-03-06 12:00',
      phase: 'monitoring',
      member_pids: ['A-1'],
      progress: '',
      logs: [],
    })
  })

  it('preserves prior progress/sale_time when a later event omits sale_time', () => {
    const state = {
      ...initialState,
      groups: {
        g1: {
          sale_time: '2026-03-06 12:00',
          phase: 'monitoring',
          member_pids: ['A-1'],
          progress: '5/10',
          logs: [],
        },
      },
    }

    const next = reducer(state, {
      type: 'sse',
      event: {
        type: 'group',
        gid: 'g1',
        phase: 'carting',
        member_pids: ['A-1'],
      },
    })

    expect(next.groups.g1).toMatchObject({
      sale_time: '2026-03-06 12:00',
      phase: 'carting',
      progress: '5/10',
    })
  })

  it('deletes the group entry once phase is "closed"', () => {
    const state = {
      ...initialState,
      groups: {
        g1: {
          sale_time: '',
          phase: 'holding',
          member_pids: ['A-1'],
          progress: '',
          logs: [],
        },
      },
    }

    const next = reducer(state, {
      type: 'sse',
      event: { type: 'group', gid: 'g1', phase: 'closed', member_pids: [] },
    })

    expect(next.groups).toEqual({})
  })
})

describe('reducer / sse checkout', () => {
  it('prepends a new checkout record', () => {
    const state = { ...initialState, checkouts: [checkout({ id: 'old' })] }

    const next = reducer(state, {
      type: 'sse',
      event: { type: 'checkout', record: checkout({ id: 'new' }) },
    })

    expect(next.checkouts.map((r) => r.id)).toEqual(['new', 'old'])
  })

  it('replaces an existing record in place rather than duplicating it', () => {
    const state = {
      ...initialState,
      checkouts: [checkout({ id: 'c1', completed: false })],
    }

    const next = reducer(state, {
      type: 'sse',
      event: {
        type: 'checkout',
        record: checkout({ id: 'c1', completed: true }),
      },
    })

    expect(next.checkouts).toHaveLength(1)
    expect(next.checkouts[0].completed).toBe(true)
  })
})

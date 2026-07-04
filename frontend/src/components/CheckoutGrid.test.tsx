import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api'
import type { CheckoutRecord } from '../types'
import CheckoutGrid from './CheckoutGrid'

vi.mock('../api')

const toastSpy = vi.fn()
vi.mock('../toast', () => ({ useToast: () => toastSpy }))

let mockCheckouts: CheckoutRecord[] = []
const applySnapshotSpy = vi.fn()
vi.mock('../state', () => ({
  useAppState: () => ({ checkouts: mockCheckouts }),
  useApplySnapshot: () => applySnapshotSpy,
}))

function record(overrides: Partial<CheckoutRecord> = {}): CheckoutRecord {
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

describe('CheckoutGrid', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockCheckouts = []
  })

  it('shows an empty state with no checkout records', () => {
    render(<CheckoutGrid />)
    expect(screen.getByText('尚無結帳紀錄')).toBeInTheDocument()
  })

  it('shows the success ratio and total for a record', () => {
    mockCheckouts = [
      record({
        cart_results: [
          { pid: 'A-1', ok: true, sold_out: false, stage: '', prodcount: 2, prodtotal: 1980, raw: null, error: '' },
          { pid: 'A-2', ok: false, sold_out: true, stage: '', prodcount: null, prodtotal: null, raw: null, error: '' },
        ],
      }),
    ]
    render(<CheckoutGrid />)
    expect(screen.getByText('成功 1/2 件，$1980')).toBeInTheDocument()
  })

  it('disables 清除已完成 when nothing is completed, enables it otherwise', () => {
    mockCheckouts = [record({ completed: false })]
    const { rerender } = render(<CheckoutGrid />)
    expect(screen.getByRole('button', { name: '清除已完成（0）' })).toBeDisabled()

    mockCheckouts = [record({ completed: true })]
    rerender(<CheckoutGrid />)
    expect(screen.getByRole('button', { name: '清除已完成（1）' })).toBeEnabled()
  })

  it('calls clearCompletedCheckouts and applies the returned snapshot', async () => {
    mockCheckouts = [record({ completed: true })]
    vi.mocked(api.clearCompletedCheckouts).mockResolvedValue({
      auth: {},
      products: [],
      groups: {},
      checkouts: [],
    } as never)
    const user = userEvent.setup()
    render(<CheckoutGrid />)

    await user.click(screen.getByRole('button', { name: '清除已完成（1）' }))

    await waitFor(() => expect(applySnapshotSpy).toHaveBeenCalled())
  })

  it('opens the detail dialog for the clicked record', async () => {
    mockCheckouts = [record({ id: 'c1', sale_time: '2026-03-06 12:00' })]
    const user = userEvent.setup()
    render(<CheckoutGrid />)

    await user.click(screen.getByRole('button', { name: '查看詳情' }))

    expect(screen.getByRole('heading', { name: '結帳詳情' })).toBeInTheDocument()
  })
})

import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api'
import type { CheckoutRecord } from '../types'
import CheckoutDetailDialog from './CheckoutDetailDialog'

vi.mock('../api')

const toastSpy = vi.fn()
vi.mock('../toast', () => ({ useToast: () => toastSpy }))

const applySnapshotSpy = vi.fn()
vi.mock('../state', () => ({ useApplySnapshot: () => applySnapshotSpy }))

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

describe('CheckoutDetailDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders nothing when record is null', () => {
    render(<CheckoutDetailDialog record={null} onClose={vi.fn()} />)
    expect(
      screen.queryByRole('heading', { name: '結帳詳情' }),
    ).not.toBeInTheDocument()
  })

  it('shows cart_results rows, distinguishing success/sold-out/failure', () => {
    render(
      <CheckoutDetailDialog
        record={record({
          cart_results: [
            {
              pid: 'A-1',
              ok: true,
              sold_out: false,
              stage: '',
              prodcount: 2,
              prodtotal: 1980,
              raw: null,
              error: '',
            },
            {
              pid: 'A-2',
              ok: false,
              sold_out: true,
              stage: '',
              prodcount: null,
              prodtotal: null,
              raw: null,
              error: '',
            },
            {
              pid: 'A-3',
              ok: false,
              sold_out: false,
              stage: 'modify',
              prodcount: null,
              prodtotal: null,
              raw: null,
              error: 'x',
            },
          ],
        })}
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByText('成功')).toBeInTheDocument()
    expect(screen.getByText('售完')).toBeInTheDocument()
    expect(screen.getByText('失敗（modify）')).toBeInTheDocument()
  })

  it('shows the payinfo block, including CVC/auto-pay status, only when payinfo is present', () => {
    const { rerender } = render(
      <CheckoutDetailDialog
        record={record({ payinfo: null })}
        onClose={vi.fn()}
      />,
    )
    expect(screen.queryByText('結帳頁資訊')).not.toBeInTheDocument()

    rerender(
      <CheckoutDetailDialog
        record={record({
          payinfo: {
            url: 'https://ecssl.pchome.com.tw/fsrwd/cart/payinfo',
            cvc_filled: true,
            auto_pay_clicked: false,
            items: [{ name: '商品 A' }],
            total: '$1980',
            raw_text: '',
            error: '',
          },
        })}
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByText('結帳頁資訊')).toBeInTheDocument()
    expect(screen.getByText('已自動填入')).toBeInTheDocument()
    expect(screen.getByText('未點擊')).toBeInTheDocument()
    expect(screen.getByText('商品 A')).toBeInTheDocument()
  })

  it('shows a 標記完成 button only when the record is not yet completed', () => {
    const { rerender } = render(
      <CheckoutDetailDialog
        record={record({ completed: false })}
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByRole('button', { name: '標記完成' })).toBeInTheDocument()

    rerender(
      <CheckoutDetailDialog
        record={record({ completed: true })}
        onClose={vi.fn()}
      />,
    )
    expect(
      screen.queryByRole('button', { name: '標記完成' }),
    ).not.toBeInTheDocument()
  })

  it('marks the checkout complete and applies the returned snapshot', async () => {
    vi.mocked(api.completeCheckout).mockResolvedValue({
      auth: {},
      products: [],
      groups: {},
      checkouts: [],
    } as never)
    const user = userEvent.setup()
    render(
      <CheckoutDetailDialog
        record={record({ id: 'c1', completed: false })}
        onClose={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: '標記完成' }))

    await waitFor(() => expect(api.completeCheckout).toHaveBeenCalledWith('c1'))
    expect(applySnapshotSpy).toHaveBeenCalled()
  })

  it('shows a toast if marking complete fails', async () => {
    vi.mocked(api.completeCheckout).mockRejectedValue(
      new Error('找不到結帳紀錄'),
    )
    const user = userEvent.setup()
    render(
      <CheckoutDetailDialog
        record={record({ completed: false })}
        onClose={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: '標記完成' }))

    await waitFor(() => expect(toastSpy).toHaveBeenCalledWith('找不到結帳紀錄'))
  })
})

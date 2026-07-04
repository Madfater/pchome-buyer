import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api'
import type { Group, Product } from '../types'
import ProductCard from './ProductCard'

vi.mock('../api')

const toastSpy = vi.fn()
vi.mock('../toast', () => ({ useToast: () => toastSpy }))

let mockGroups: Record<string, Group> = {}
const applySnapshotSpy = vi.fn()
vi.mock('../state', () => ({
  useAppState: () => ({ groups: mockGroups }),
  useApplySnapshot: () => applySnapshotSpy,
}))

function product(overrides: Partial<Product> = {}): Product {
  return {
    id: 'DGCQ39-A900JESMM',
    sale_time: '',
    state: 'idle',
    info: '',
    gid: null,
    ...overrides,
  }
}

describe('ProductCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGroups = {}
  })

  it('shows the idle state label and a start button', () => {
    render(
      <ProductCard product={product()} selected={false} onToggle={vi.fn()} />,
    )
    expect(screen.getByText('待命')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '開始' })).toBeInTheDocument()
  })

  it('calls onToggle when the checkbox is clicked', async () => {
    const onToggle = vi.fn()
    const user = userEvent.setup()
    render(
      <ProductCard product={product()} selected={false} onToggle={onToggle} />,
    )

    await user.click(screen.getByRole('checkbox', { name: '選取任務' }))

    expect(onToggle).toHaveBeenCalledTimes(1)
  })

  it('starts the job and applies the returned snapshot', async () => {
    vi.mocked(api.startJobs).mockResolvedValue({
      auth: {},
      products: [],
      groups: {},
      checkouts: [],
    } as never)
    const user = userEvent.setup()
    render(
      <ProductCard product={product()} selected={false} onToggle={vi.fn()} />,
    )

    await user.click(screen.getByRole('button', { name: '開始' }))

    await waitFor(() => expect(applySnapshotSpy).toHaveBeenCalled())
    expect(api.startJobs).toHaveBeenCalledWith(['DGCQ39-A900JESMM'])
  })

  it('disables edit/remove while the job is active, and shows a cancel button instead of start', () => {
    render(
      <ProductCard
        product={product({ state: 'monitoring' })}
        selected={false}
        onToggle={vi.fn()}
      />,
    )
    expect(screen.getByTitle('修改開賣時間')).toBeDisabled()
    expect(screen.getByTitle('刪除任務')).toBeDisabled()
    expect(screen.getByRole('button', { name: '取消' })).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: '開始' }),
    ).not.toBeInTheDocument()
  })

  it('shows a "結束（關閉瀏覽器）" button instead of cancel when the group is holding', () => {
    mockGroups = {
      g1: {
        sale_time: '',
        phase: 'holding',
        member_pids: ['DGCQ39-A900JESMM'],
        progress: '',
        logs: [],
      },
    }
    render(
      <ProductCard
        product={product({ state: 'awaiting_payment', gid: 'g1' })}
        selected={false}
        onToggle={vi.fn()}
      />,
    )
    expect(
      screen.getByRole('button', { name: '結束（關閉瀏覽器）' }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: '取消' }),
    ).not.toBeInTheDocument()
  })

  it('shows group phase and progress text when a group is attached', () => {
    mockGroups = {
      g1: {
        sale_time: '',
        phase: 'monitoring',
        member_pids: ['DGCQ39-A900JESMM'],
        progress: '3/10',
        logs: [],
      },
    }
    render(
      <ProductCard
        product={product({ state: 'monitoring', gid: 'g1' })}
        selected={false}
        onToggle={vi.fn()}
      />,
    )
    expect(screen.getByText('監控中 — 3/10')).toBeInTheDocument()
  })

  it('asks for confirmation before removing, then calls the API', async () => {
    vi.mocked(api.removeProduct).mockResolvedValue({
      auth: {},
      products: [],
      groups: {},
      checkouts: [],
    } as never)
    const user = userEvent.setup()
    render(
      <ProductCard product={product()} selected={false} onToggle={vi.fn()} />,
    )

    await user.click(screen.getByTitle('刪除任務'))
    expect(
      screen.getByText('將刪除 DGCQ39-A900JESMM，此操作無法復原。'),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '刪除' }))

    await waitFor(() =>
      expect(api.removeProduct).toHaveBeenCalledWith('DGCQ39-A900JESMM'),
    )
  })

  it('shows a toast when the API call fails', async () => {
    vi.mocked(api.startJobs).mockRejectedValue(new Error('無法啟動'))
    const user = userEvent.setup()
    render(
      <ProductCard product={product()} selected={false} onToggle={vi.fn()} />,
    )

    await user.click(screen.getByRole('button', { name: '開始' }))

    await waitFor(() => expect(toastSpy).toHaveBeenCalledWith('無法啟動'))
  })

  it('falls back to showing the id when there is no name/image/price meta', () => {
    render(
      <ProductCard product={product()} selected={false} onToggle={vi.fn()} />,
    )
    expect(screen.getByText('DGCQ39-A900JESMM')).toBeInTheDocument()
    expect(document.querySelector('.thumb.placeholder')).toBeInTheDocument()
  })

  it('shows name, image, price and a strikethrough original price when meta is present', () => {
    render(
      <ProductCard
        product={product({
          name: '測試商品',
          image: 'https://img.pchome.com.tw/cs/items/x.jpg',
          price: 800,
          orig_price: 1000,
        })}
        selected={false}
        onToggle={vi.fn()}
      />,
    )
    expect(screen.getByText('測試商品')).toBeInTheDocument()
    // 有名稱時，商品編號改以次要文字顯示在旁邊
    expect(screen.getByText('DGCQ39-A900JESMM')).toBeInTheDocument()
    expect(screen.getByText('$800')).toBeInTheDocument()
    expect(screen.getByText('$1,000')).toBeInTheDocument()
    expect(document.querySelector('img.thumb')?.getAttribute('src')).toBe(
      'https://img.pchome.com.tw/cs/items/x.jpg',
    )
  })

  it('does not show a strikethrough price when orig_price equals price', () => {
    render(
      <ProductCard
        product={product({ name: '測試商品', price: 800, orig_price: 800 })}
        selected={false}
        onToggle={vi.fn()}
      />,
    )
    expect(screen.getByText('$800')).toBeInTheDocument()
    expect(screen.queryByText('$1,000')).not.toBeInTheDocument()
  })

  it('shows a spec warning badge for products with variants', () => {
    render(
      <ProductCard
        product={product({ name: '測試商品', is_spec: true })}
        selected={false}
        onToggle={vi.fn()}
      />,
    )
    expect(screen.getByText('含規格選項')).toBeInTheDocument()
  })

  it('shows e-ticket and pre-order badges when flagged', () => {
    render(
      <ProductCard
        product={product({
          name: '測試商品',
          is_eticket: true,
          is_preorder: true,
        })}
        selected={false}
        onToggle={vi.fn()}
      />,
    )
    expect(screen.getByText('電子票券')).toBeInTheDocument()
    expect(screen.getByText('預購')).toBeInTheDocument()
  })
})

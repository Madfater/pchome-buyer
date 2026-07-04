import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api'
import type { Product } from '../types'
import ProductGrid from './ProductGrid'

vi.mock('../api')

const toastSpy = vi.fn()
vi.mock('../toast', () => ({ useToast: () => toastSpy }))

let mockProducts: Product[] = []
const applySnapshotSpy = vi.fn()
vi.mock('../state', () => ({
  useAppState: () => ({ products: mockProducts, groups: {} }),
  useApplySnapshot: () => applySnapshotSpy,
}))

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

describe('ProductGrid', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockProducts = []
  })

  it('shows an empty state hint with no products', () => {
    render(<ProductGrid />)
    expect(
      screen.getByText('尚未新增任務，按「＋ 新增任務」貼上商品網址開始'),
    ).toBeInTheDocument()
  })

  it('groups products by sale_time, "立即監控" first, sorted after that', () => {
    mockProducts = [
      product({ id: 'B-1', sale_time: '2026-03-06 12:00' }),
      product({ id: 'A-1', sale_time: '' }),
      product({ id: 'C-1', sale_time: '2026-01-01 09:00' }),
    ]
    const { container } = render(<ProductGrid />)

    const headings = [...container.querySelectorAll('.group-title')]
    expect(headings.map((h) => h.textContent)).toEqual([
      '立即監控',
      '開賣 2026-01-01 09:00',
      '開賣 2026-03-06 12:00',
    ])
  })

  it('does not show the bulk action bar until something is selected', async () => {
    mockProducts = [product({ id: 'A-1' })]
    render(<ProductGrid />)
    expect(screen.queryByText(/已選/)).not.toBeInTheDocument()

    const user = userEvent.setup()
    await user.click(screen.getByRole('checkbox', { name: '選取任務' }))

    expect(screen.getByText('已選 1 個')).toBeInTheDocument()
  })

  it('group checkbox selects/deselects every card in that group', async () => {
    mockProducts = [product({ id: 'A-1' }), product({ id: 'A-2' })]
    const user = userEvent.setup()
    render(<ProductGrid />)

    await user.click(screen.getByRole('checkbox', { name: '選取整組' }))
    expect(screen.getByText('已選 2 個')).toBeInTheDocument()

    await user.click(screen.getByRole('checkbox', { name: '選取整組' }))
    expect(screen.queryByText(/已選/)).not.toBeInTheDocument()
  })

  it('only counts non-active jobs as startable and active jobs as cancellable', async () => {
    mockProducts = [
      product({ id: 'A-1', state: 'idle' }),
      product({ id: 'A-2', state: 'monitoring' }),
    ]
    const user = userEvent.setup()
    render(<ProductGrid />)

    await user.click(screen.getByRole('checkbox', { name: '選取整組' }))

    expect(
      screen.getByRole('button', { name: '啟動選取（1）' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: '取消選取（1）' }),
    ).toBeInTheDocument()
  })

  it('starts the selected startable jobs and clears selection on success', async () => {
    mockProducts = [product({ id: 'A-1' })]
    vi.mocked(api.startJobs).mockResolvedValue({
      auth: {},
      products: [],
      groups: {},
      checkouts: [],
    } as never)
    const user = userEvent.setup()
    render(<ProductGrid />)

    await user.click(screen.getByRole('checkbox', { name: '選取整組' }))
    await user.click(screen.getByRole('button', { name: '啟動選取（1）' }))

    await waitFor(() => expect(applySnapshotSpy).toHaveBeenCalled())
    expect(api.startJobs).toHaveBeenCalledWith(['A-1'])
    expect(screen.queryByText(/已選/)).not.toBeInTheDocument()
  })

  it('opens a confirm dialog before bulk-deleting, and calls removeProducts on confirm', async () => {
    mockProducts = [product({ id: 'A-1' }), product({ id: 'A-2' })]
    vi.mocked(api.removeProducts).mockResolvedValue({
      auth: {},
      products: [],
      groups: {},
      checkouts: [],
    } as never)
    const user = userEvent.setup()
    render(<ProductGrid />)

    await user.click(screen.getByRole('checkbox', { name: '選取整組' }))
    await user.click(screen.getByRole('button', { name: '刪除選取（2）' }))

    expect(
      screen.getByText(
        '將刪除 2 個未執行的任務，執行中的任務不受影響。此操作無法復原。',
      ),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '刪除' }))

    await waitFor(() =>
      expect(api.removeProducts).toHaveBeenCalledWith(['A-1', 'A-2']),
    )
  })

  it('全選 selects every product across groups, 清除選取 clears it', async () => {
    mockProducts = [
      product({ id: 'A-1' }),
      product({ id: 'B-1', sale_time: '2026-03-06 12:00' }),
    ]
    const user = userEvent.setup()
    render(<ProductGrid />)

    // 先選 1 個讓 bulkbar 出現，才能點到「全選」
    await user.click(screen.getAllByRole('checkbox', { name: '選取任務' })[0])
    await user.click(screen.getByRole('button', { name: '全選' }))
    expect(screen.getByText('已選 2 個')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '清除選取' }))
    expect(screen.queryByText(/已選/)).not.toBeInTheDocument()
  })

  it('opens the add-product dialog from the header button', async () => {
    const user = userEvent.setup()
    render(<ProductGrid />)

    await user.click(screen.getByRole('button', { name: '＋ 新增任務' }))

    expect(
      screen.getByRole('heading', { name: '新增搶購任務' }),
    ).toBeInTheDocument()
  })
})

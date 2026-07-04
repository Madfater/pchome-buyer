import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api'
import type { Product } from '../types'
import EditSaleTimeDialog from './EditSaleTimeDialog'

vi.mock('../api')

const toastSpy = vi.fn()
vi.mock('../toast', () => ({ useToast: () => toastSpy }))

function product(overrides: Partial<Product> = {}): Product {
  return { id: 'DGCQ39-A900JESMM', sale_time: '2026-03-06 12:00', state: 'idle', info: '', gid: null, ...overrides }
}

describe('EditSaleTimeDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('prefills the datetime-local input from product.sale_time on open', () => {
    render(<EditSaleTimeDialog open product={product()} onClose={vi.fn()} />)
    expect(screen.getByLabelText('開始監測時間（留空表示立即監控）')).toHaveValue('2026-03-06T12:00')
  })

  it('shows the product id', () => {
    render(<EditSaleTimeDialog open product={product()} onClose={vi.fn()} />)
    expect(screen.getByText('DGCQ39-A900JESMM')).toBeInTheDocument()
  })

  it('submits the edited time with "T" converted back to a space, then closes', async () => {
    const onClose = vi.fn()
    vi.mocked(api.updateSaleTime).mockResolvedValue({ auth: {}, products: [], groups: {}, checkouts: [] } as never)
    const user = userEvent.setup()
    render(<EditSaleTimeDialog open product={product()} onClose={onClose} />)

    const input = screen.getByLabelText('開始監測時間（留空表示立即監控）')
    await user.clear(input)
    await user.type(input, '2026-03-06T13:30')
    await user.click(screen.getByRole('button', { name: '儲存' }))

    await waitFor(() => expect(onClose).toHaveBeenCalled())
    expect(api.updateSaleTime).toHaveBeenCalledWith('DGCQ39-A900JESMM', '2026-03-06 13:30')
  })

  it('shows a toast and keeps the dialog open on failure', async () => {
    vi.mocked(api.updateSaleTime).mockRejectedValue(new Error('任務執行中無法修改'))
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<EditSaleTimeDialog open product={product()} onClose={onClose} />)

    await user.click(screen.getByRole('button', { name: '儲存' }))

    await waitFor(() => expect(toastSpy).toHaveBeenCalledWith('任務執行中無法修改'))
    expect(onClose).not.toHaveBeenCalled()
  })
})

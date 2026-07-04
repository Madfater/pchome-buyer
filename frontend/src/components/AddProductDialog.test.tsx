import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api'
import AddProductDialog from './AddProductDialog'

vi.mock('../api')

const toastSpy = vi.fn()
vi.mock('../toast', () => ({ useToast: () => toastSpy }))

describe('AddProductDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows a parse hint while empty and disables submit', () => {
    render(<AddProductDialog open onClose={vi.fn()} />)
    expect(
      screen.getByText('貼上 PChome 24h 商品頁網址，或直接輸入商品編號'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '新增' })).toBeDisabled()
  })

  it('previews the parsed product id from a bare id', async () => {
    const user = userEvent.setup()
    render(<AddProductDialog open onClose={vi.fn()} />)

    await user.type(screen.getByLabelText('商品網址或編號'), 'dgcq39-a900jesmm')

    expect(screen.getByText('商品編號：DGCQ39-A900JESMM')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '新增' })).toBeEnabled()
  })

  it('previews the parsed product id from a full product URL', async () => {
    const user = userEvent.setup()
    render(<AddProductDialog open onClose={vi.fn()} />)

    await user.type(
      screen.getByLabelText('商品網址或編號'),
      'https://24h.pchome.com.tw/prod/DGCQ39-A900JESMM',
    )

    expect(screen.getByText('商品編號：DGCQ39-A900JESMM')).toBeInTheDocument()
  })

  it('shows an error hint and keeps submit disabled for unparseable input', async () => {
    const user = userEvent.setup()
    render(<AddProductDialog open onClose={vi.fn()} />)

    await user.type(screen.getByLabelText('商品網址或編號'), 'not a valid ref')

    expect(screen.getByText('無法解析商品編號')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '新增' })).toBeDisabled()
  })

  it('submits, converts datetime-local "T" to a space, and closes on success', async () => {
    const onClose = vi.fn()
    const snapshot = { auth: {}, products: [], groups: {}, checkouts: [] }
    vi.mocked(api.addProduct).mockResolvedValue(snapshot as never)
    const user = userEvent.setup()
    render(<AddProductDialog open onClose={onClose} />)

    await user.type(screen.getByLabelText('商品網址或編號'), 'DGCQ39-A900JESMM')
    const timeInput = screen.getByLabelText('開始監測時間（留空表示立即監控）')
    await user.type(timeInput, '2026-03-06T12:00')
    await user.click(screen.getByRole('button', { name: '新增' }))

    await waitFor(() => expect(onClose).toHaveBeenCalled())
    expect(api.addProduct).toHaveBeenCalledWith(
      'DGCQ39-A900JESMM',
      '2026-03-06 12:00',
    )
  })

  it('shows a toast and keeps the dialog open when the API call fails', async () => {
    vi.mocked(api.addProduct).mockRejectedValue(new Error('商品編號重複'))
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<AddProductDialog open onClose={onClose} />)

    await user.type(screen.getByLabelText('商品網址或編號'), 'DGCQ39-A900JESMM')
    await user.click(screen.getByRole('button', { name: '新增' }))

    await waitFor(() => expect(toastSpy).toHaveBeenCalledWith('商品編號重複'))
    expect(onClose).not.toHaveBeenCalled()
  })
})

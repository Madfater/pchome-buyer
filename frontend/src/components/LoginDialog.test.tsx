import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api'
import LoginDialog from './LoginDialog'

vi.mock('../api')

const toastSpy = vi.fn()
vi.mock('../toast', () => ({ useToast: () => toastSpy }))

const dispatchSpy = vi.fn()
vi.mock('../state', () => ({ useAppDispatch: () => dispatchSpy }))

describe('LoginDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('disables the import button until there is payload text', () => {
    render(<LoginDialog open onClose={vi.fn()} />)

    expect(screen.getByRole('button', { name: '匯入' })).toBeDisabled()

    fireEvent.change(screen.getByLabelText('憑證內容（JSON）'), {
      target: { value: '{"cookies": []}' },
    })

    expect(screen.getByRole('button', { name: '匯入' })).toBeEnabled()
  })

  it('imports the payload, shows the result, and dispatches an optimistic auth update', async () => {
    vi.mocked(api.importAuth).mockResolvedValue({
      ok: true,
      format: 'storage_state',
      cookie_count: 3,
      pchome_cookie_count: 2,
      warning: '',
      error: '',
    })
    const user = userEvent.setup()
    render(<LoginDialog open onClose={vi.fn()} />)

    fireEvent.change(screen.getByLabelText('憑證內容（JSON）'), {
      target: { value: '{"cookies": []}' },
    })
    await user.click(screen.getByRole('button', { name: '匯入' }))

    const result = await screen.findByText(
      (_, el) => el?.className === 'ok-text',
    )
    expect(result.textContent?.replace(/\s+/g, ' ')).toBe(
      '匯入成功（storage state， 共 3 個 cookie，PChome 2 個）',
    )
    expect(dispatchSpy).toHaveBeenCalledWith({
      type: 'auth',
      auth: { has_auth_state: true, session_valid: null, checked_at: null },
    })
  })

  it('shows a warning line when the import result carries one', async () => {
    vi.mocked(api.importAuth).mockResolvedValue({
      ok: true,
      format: 'cookie_array',
      cookie_count: 5,
      pchome_cookie_count: 0,
      warning: '警告：找不到任何 pchome.com.tw 的 cookie，登入可能無效',
      error: '',
    })
    const user = userEvent.setup()
    render(<LoginDialog open onClose={vi.fn()} />)

    fireEvent.change(screen.getByLabelText('憑證內容（JSON）'), {
      target: { value: '[]' },
    })
    await user.click(screen.getByRole('button', { name: '匯入' }))

    expect(
      await screen.findByText(
        '警告：找不到任何 pchome.com.tw 的 cookie，登入可能無效',
      ),
    ).toBeInTheDocument()
  })

  it('shows a toast on import failure without touching auth state', async () => {
    vi.mocked(api.importAuth).mockRejectedValue(new Error('JSON 解析失敗'))
    const user = userEvent.setup()
    render(<LoginDialog open onClose={vi.fn()} />)

    await user.type(screen.getByLabelText('憑證內容（JSON）'), 'not json')
    await user.click(screen.getByRole('button', { name: '匯入' }))

    await waitFor(() => expect(toastSpy).toHaveBeenCalledWith('JSON 解析失敗'))
    expect(dispatchSpy).not.toHaveBeenCalled()
  })

  it('checks session status live and shows the resulting message', async () => {
    vi.mocked(api.fetchAuthStatus).mockResolvedValue({
      has_auth_state: true,
      session_valid: true,
      checked_at: 123,
    })
    const user = userEvent.setup()
    render(<LoginDialog open onClose={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: '檢查 session' }))

    expect(
      await screen.findByText('session 有效，可以開始搶購'),
    ).toBeInTheDocument()
    expect(api.fetchAuthStatus).toHaveBeenCalledWith(true)
    expect(dispatchSpy).toHaveBeenCalledWith({
      type: 'auth',
      auth: { has_auth_state: true, session_valid: true, checked_at: 123 },
    })
  })

  it('shows the expired-session message when the live check finds an invalid session', async () => {
    vi.mocked(api.fetchAuthStatus).mockResolvedValue({
      has_auth_state: true,
      session_valid: false,
      checked_at: 123,
    })
    const user = userEvent.setup()
    render(<LoginDialog open onClose={vi.fn()} />)

    await user.click(screen.getByRole('button', { name: '檢查 session' }))

    expect(
      await screen.findByText('session 無效或已過期，請重新匯入'),
    ).toBeInTheDocument()
  })

  it('reads payload from a selected file', async () => {
    const user = userEvent.setup()
    render(<LoginDialog open onClose={vi.fn()} />)

    const file = new File(['{"cookies": [{"name": "a"}]}'], 'auth_state.json', {
      type: 'application/json',
    })
    const input = screen.getByLabelText('或選擇檔案')
    await user.upload(input, file)

    await waitFor(() =>
      expect(screen.getByLabelText('憑證內容（JSON）')).toHaveValue(
        '{"cookies": [{"name": "a"}]}',
      ),
    )
  })
})

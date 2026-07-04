import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { AuthStatus } from '../types'
import TopBar from './TopBar'

vi.mock('../api')
vi.mock('../toast', () => ({ useToast: () => vi.fn() }))

let mockAuth: AuthStatus = {
  has_auth_state: false,
  session_valid: null,
  checked_at: null,
}
let mockConnected = true
vi.mock('../state', () => ({
  useAppState: () => ({ auth: mockAuth, connected: mockConnected }),
  useAppDispatch: () => vi.fn(),
}))

describe('TopBar', () => {
  it('shows "未登入" when there is no auth state', () => {
    mockAuth = { has_auth_state: false, session_valid: null, checked_at: null }
    render(<TopBar />)
    expect(screen.getByText('未登入')).toBeInTheDocument()
  })

  it('shows "已登入" when auth state exists and session is not known-bad', () => {
    mockAuth = { has_auth_state: true, session_valid: null, checked_at: null }
    render(<TopBar />)
    expect(screen.getByText('已登入')).toBeInTheDocument()
  })

  it('shows "session 過期" when the live check found an invalid session', () => {
    mockAuth = { has_auth_state: true, session_valid: false, checked_at: 123 }
    render(<TopBar />)
    expect(screen.getByText('session 過期')).toBeInTheDocument()
  })

  it('shows a "連線中斷" badge when SSE is disconnected', () => {
    mockConnected = false
    render(<TopBar />)
    expect(screen.getByText('連線中斷')).toBeInTheDocument()
    mockConnected = true
  })

  it('does not show the disconnected badge while connected', () => {
    mockConnected = true
    render(<TopBar />)
    expect(screen.queryByText('連線中斷')).not.toBeInTheDocument()
  })

  it('opens the login dialog when the 登入 button is clicked', async () => {
    const user = userEvent.setup()
    render(<TopBar />)

    await user.click(screen.getByRole('button', { name: '登入' }))

    expect(
      screen.getByRole('heading', { name: '匯入登入憑證' }),
    ).toBeInTheDocument()
  })
})

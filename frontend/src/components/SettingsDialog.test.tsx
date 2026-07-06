import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as api from '../api'
import SettingsDialog from './SettingsDialog'

vi.mock('../api')

const toastSpy = vi.fn()
vi.mock('../toast', () => ({ useToast: () => toastSpy }))

const dispatchSpy = vi.fn()
vi.mock('../state', () => ({ useAppDispatch: () => dispatchSpy }))

const defaultSettings = {
  cvc: '',
  auto_pay: false,
  default_interval_secs: 0.5,
  default_lead_secs: 300,
  fast_poll_window_secs: 15,
  slow_poll_factor: 4,
  resync_secs: 60,
  max_retries: 3,
  retry_delay_secs: 0.3,
}

describe('SettingsDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(api.fetchSettings).mockResolvedValue({ ...defaultSettings })
  })

  it('fetches settings when opened and renders all sections', async () => {
    render(<SettingsDialog open onClose={vi.fn()} />)

    expect(await screen.findByText('登入')).toBeInTheDocument()
    expect(screen.getByText('付款')).toBeInTheDocument()
    expect(screen.getByText('搶購時機')).toBeInTheDocument()
    expect(screen.getByText('進階')).toBeInTheDocument()
    expect(api.fetchSettings).toHaveBeenCalledTimes(1)
  })

  it('does not fetch settings while closed', () => {
    render(<SettingsDialog open={false} onClose={vi.fn()} />)
    expect(api.fetchSettings).not.toHaveBeenCalled()
  })

  it('saving payment section only sends cvc/auto_pay fields', async () => {
    vi.mocked(api.updateSettings).mockResolvedValue({
      ...defaultSettings,
      cvc: '123',
    })
    const user = userEvent.setup()
    render(<SettingsDialog open onClose={vi.fn()} />)

    const cvcInput = await screen.findByLabelText('信用卡安全碼（CVC）')
    await user.type(cvcInput, '123')
    await user.click(screen.getByRole('button', { name: '儲存付款設定' }))

    await waitFor(() =>
      expect(api.updateSettings).toHaveBeenCalledWith({
        cvc: '123',
        auto_pay: false,
      }),
    )
  })

  it('saving timing section only sends timing fields', async () => {
    vi.mocked(api.updateSettings).mockResolvedValue({ ...defaultSettings })
    const user = userEvent.setup()
    render(<SettingsDialog open onClose={vi.fn()} />)

    await screen.findByText('搶購時機')
    await user.click(screen.getByRole('button', { name: '儲存搶購時機設定' }))

    await waitFor(() =>
      expect(api.updateSettings).toHaveBeenCalledWith({
        default_interval_secs: 0.5,
        default_lead_secs: 300,
        fast_poll_window_secs: 15,
        slow_poll_factor: 4,
        resync_secs: 60,
      }),
    )
  })

  it('saving advanced section only sends max_retries/retry_delay_secs', async () => {
    vi.mocked(api.updateSettings).mockResolvedValue({ ...defaultSettings })
    const user = userEvent.setup()
    render(<SettingsDialog open onClose={vi.fn()} />)

    await screen.findByText('進階')
    await user.click(screen.getByRole('button', { name: '儲存進階設定' }))

    await waitFor(() =>
      expect(api.updateSettings).toHaveBeenCalledWith({
        max_retries: 3,
        retry_delay_secs: 0.3,
      }),
    )
  })

  it('shows a toast when saving fails validation', async () => {
    vi.mocked(api.updateSettings).mockRejectedValue(
      new Error('max_retries 必須介於 1 到 10 之間'),
    )
    const user = userEvent.setup()
    render(<SettingsDialog open onClose={vi.fn()} />)

    await screen.findByText('進階')
    await user.click(screen.getByRole('button', { name: '儲存進階設定' }))

    await waitFor(() =>
      expect(toastSpy).toHaveBeenCalledWith(
        'max_retries 必須介於 1 到 10 之間',
      ),
    )
  })
})

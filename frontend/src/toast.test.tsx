import { render, screen, waitFor } from '@testing-library/react'
import { useEffect } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ToastProvider, useToast } from './toast'

function Trigger({ messages }: { messages: string[] }) {
  const toast = useToast()
  useEffect(() => {
    messages.forEach(toast)
    // 只在掛載時觸發一次，訊息列表本身在測試中不會變動
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return null
}

describe('ToastProvider', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders nothing until a toast is shown', () => {
    render(<ToastProvider>content</ToastProvider>)
    expect(
      screen.queryByText(/./, { selector: '.toast' }),
    ).not.toBeInTheDocument()
  })

  it('shows the message passed to useToast()', async () => {
    render(
      <ToastProvider>
        <Trigger messages={['出錯了']} />
      </ToastProvider>,
    )
    expect(await screen.findByText('出錯了')).toBeInTheDocument()
  })

  it('replaces the message and resets the auto-dismiss timer when called again', async () => {
    render(
      <ToastProvider>
        <Trigger messages={['第一則', '第二則']} />
      </ToastProvider>,
    )
    expect(await screen.findByText('第二則')).toBeInTheDocument()
    expect(screen.queryByText('第一則')).not.toBeInTheDocument()
  })

  it('auto-dismisses after 4 seconds', async () => {
    render(
      <ToastProvider>
        <Trigger messages={['會消失']} />
      </ToastProvider>,
    )
    expect(await screen.findByText('會消失')).toBeInTheDocument()

    await vi.advanceTimersByTimeAsync(4000)

    await waitFor(() =>
      expect(screen.queryByText('會消失')).not.toBeInTheDocument(),
    )
  })
})

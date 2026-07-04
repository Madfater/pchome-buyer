import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import Dialog from './Dialog'

describe('Dialog', () => {
  it('renders children only when open', () => {
    const { rerender } = render(
      <Dialog open={false} onClose={vi.fn()}>
        內容
      </Dialog>,
    )
    expect(screen.queryByText('內容')).not.toBeInTheDocument()

    rerender(
      <Dialog open onClose={vi.fn()}>
        內容
      </Dialog>,
    )
    expect(screen.getByText('內容')).toBeInTheDocument()
  })

  it('calls onClose when the native close event fires (e.g. Esc key)', async () => {
    const onClose = vi.fn()
    render(
      <Dialog open onClose={onClose}>
        內容
      </Dialog>,
    )

    screen.getByText('內容').closest('dialog')!.dispatchEvent(new Event('close'))

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('calls onClose when clicking the backdrop (the <dialog> element itself)', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(
      <Dialog open onClose={onClose}>
        內容
      </Dialog>,
    )

    const dialogEl = screen.getByText('內容').closest('dialog')!
    await user.click(dialogEl)

    expect(onClose).toHaveBeenCalled()
  })

  it('does not call onClose when clicking inside the dialog body', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(
      <Dialog open onClose={onClose}>
        內容
      </Dialog>,
    )

    await user.click(screen.getByText('內容'))

    expect(onClose).not.toHaveBeenCalled()
  })

  it('applies the wide class when wide is set', () => {
    render(
      <Dialog open onClose={vi.fn()} wide>
        內容
      </Dialog>,
    )
    expect(screen.getByText('內容').closest('dialog')).toHaveClass('dialog-wide')
  })
})

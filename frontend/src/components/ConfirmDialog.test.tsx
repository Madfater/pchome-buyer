import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import ConfirmDialog from './ConfirmDialog'

describe('ConfirmDialog', () => {
  it('renders title, message and confirm label when open', () => {
    render(
      <ConfirmDialog
        open
        title="刪除任務"
        message="將刪除 1 個任務"
        confirmLabel="刪除"
        onConfirm={vi.fn()}
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByText('刪除任務')).toBeInTheDocument()
    expect(screen.getByText('將刪除 1 個任務')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '刪除' })).toBeInTheDocument()
  })

  it('calls onConfirm when the danger button is clicked', async () => {
    const onConfirm = vi.fn()
    const user = userEvent.setup()
    render(
      <ConfirmDialog
        open
        title="t"
        message="m"
        confirmLabel="刪除"
        onConfirm={onConfirm}
        onClose={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: '刪除' }))

    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('calls onClose when the cancel button is clicked', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(
      <ConfirmDialog
        open
        title="t"
        message="m"
        confirmLabel="刪除"
        onConfirm={vi.fn()}
        onClose={onClose}
      />,
    )

    await user.click(screen.getByRole('button', { name: '取消' }))

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('disables the confirm button while busy', () => {
    render(
      <ConfirmDialog
        open
        title="t"
        message="m"
        confirmLabel="刪除"
        busy
        onConfirm={vi.fn()}
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByRole('button', { name: '刪除' })).toBeDisabled()
  })
})

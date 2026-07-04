import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { LogLine } from '../state'
import LogPanel from './LogPanel'

let mockLogs: LogLine[] = []
const dispatchSpy = vi.fn()
vi.mock('../state', () => ({
  useAppState: () => ({ logs: mockLogs }),
  useAppDispatch: () => dispatchSpy,
}))

describe('LogPanel', () => {
  it('shows a placeholder when there are no logs', () => {
    mockLogs = []
    render(<LogPanel />)
    expect(screen.getByText('尚無日誌')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '清除日誌' })).toBeDisabled()
  })

  it('renders each log line tagged with its gid', () => {
    mockLogs = [
      { gid: '2026-03-06_1200#1', msg: '開始監控' },
      { gid: '2026-03-06_1200#1', msg: '偵測到開賣' },
    ]
    render(<LogPanel />)
    expect(screen.getByText('開始監控')).toBeInTheDocument()
    expect(screen.getByText('偵測到開賣')).toBeInTheDocument()
    expect(screen.getAllByText('[2026-03-06_1200#1]')).toHaveLength(2)
  })

  it('does not show the group filter dropdown with only one gid', () => {
    mockLogs = [{ gid: 'g1', msg: 'x' }]
    render(<LogPanel />)
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  })

  it('shows a group filter dropdown once logs span multiple gids, and filters when used', async () => {
    mockLogs = [
      { gid: 'g1', msg: '來自 g1' },
      { gid: 'g2', msg: '來自 g2' },
    ]
    const user = userEvent.setup()
    render(<LogPanel />)

    expect(screen.getByText('來自 g1')).toBeInTheDocument()
    expect(screen.getByText('來自 g2')).toBeInTheDocument()

    await user.selectOptions(screen.getByRole('combobox'), 'g1')

    expect(screen.getByText('來自 g1')).toBeInTheDocument()
    expect(screen.queryByText('來自 g2')).not.toBeInTheDocument()
  })

  it('dispatches clear-logs and resets the filter when 清除日誌 is clicked', async () => {
    mockLogs = [{ gid: 'g1', msg: 'x' }]
    const user = userEvent.setup()
    render(<LogPanel />)

    await user.click(screen.getByRole('button', { name: '清除日誌' }))

    expect(dispatchSpy).toHaveBeenCalledWith({ type: 'clear-logs' })
  })
})

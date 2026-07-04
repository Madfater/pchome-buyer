import type { ReactNode } from 'react'
import Dialog from './Dialog'

interface Props {
  open: boolean
  title: string
  message: ReactNode
  confirmLabel: string
  busy?: boolean
  onConfirm: () => void
  onClose: () => void
}

/** 破壞性操作的確認框：取消 + 紅色確認鈕 */
export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  busy,
  onConfirm,
  onClose,
}: Props) {
  return (
    <Dialog open={open} onClose={onClose}>
      <h3>{title}</h3>
      <span className="hint">{message}</span>
      <div className="dialog-actions">
        <button onClick={onClose}>取消</button>
        <button className="danger" onClick={onConfirm} disabled={busy}>
          {confirmLabel}
        </button>
      </div>
    </Dialog>
  )
}

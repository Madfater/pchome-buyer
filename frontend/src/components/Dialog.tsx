import { useEffect, useRef, type ReactNode } from 'react'

interface Props {
  open: boolean
  onClose: () => void
  wide?: boolean
  children: ReactNode
}

/** 原生 <dialog> 包裝：open 屬性控制 showModal/close，點背景或 Esc 關閉 */
export default function Dialog({ open, onClose, wide, children }: Props) {
  const ref = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (open && !el.open) el.showModal()
    if (!open && el.open) el.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      className={wide ? 'dialog-wide' : undefined}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose()
      }}
    >
      {open && <div className="dialog-body">{children}</div>}
    </dialog>
  )
}

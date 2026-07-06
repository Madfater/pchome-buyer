import { useState } from 'react'
import { useAppState } from '../state'
import SettingsDialog from './SettingsDialog'

export default function TopBar() {
  const { auth, connected } = useAppState()
  const [settingsOpen, setSettingsOpen] = useState(false)

  const loggedIn = auth.has_auth_state
  const sessionBad = auth.session_valid === false

  return (
    <header>
      <h1>PChome 搶購控制台</h1>
      {!connected && <span className="badge err">連線中斷</span>}
      <span className={`badge ${loggedIn && !sessionBad ? 'ok' : 'err'}`}>
        {!loggedIn ? '未登入' : sessionBad ? 'session 過期' : '已登入'}
      </span>
      <button
        className="icon-btn"
        aria-label="設定"
        title="設定"
        onClick={() => setSettingsOpen(true)}
      >
        ⚙
      </button>
      <SettingsDialog
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />
    </header>
  )
}

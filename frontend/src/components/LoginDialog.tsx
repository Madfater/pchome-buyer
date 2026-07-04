import { useState, type ChangeEvent } from 'react'
import { fetchAuthStatus, importAuth } from '../api'
import { useAppDispatch } from '../state'
import { useToast } from '../toast'
import type { ImportResult } from '../types'
import Dialog from './Dialog'

interface Props {
  open: boolean
  onClose: () => void
}

export default function LoginDialog({ open, onClose }: Props) {
  const dispatch = useAppDispatch()
  const toast = useToast()
  const [payload, setPayload] = useState('')
  const [result, setResult] = useState<ImportResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [checking, setChecking] = useState(false)
  const [checkMsg, setCheckMsg] = useState('')

  const onFile = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) setPayload(await file.text())
    e.target.value = ''
  }

  const doImport = async () => {
    if (!payload.trim()) return
    setBusy(true)
    try {
      const res = await importAuth(payload)
      setResult(res)
      setCheckMsg('')
      dispatch({
        type: 'auth',
        auth: { has_auth_state: true, session_valid: null, checked_at: null },
      })
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const doCheck = async () => {
    setChecking(true)
    setCheckMsg('')
    try {
      const auth = await fetchAuthStatus(true)
      dispatch({ type: 'auth', auth })
      setCheckMsg(
        auth.session_valid === true
          ? 'session 有效，可以開始搶購'
          : auth.session_valid === false
            ? 'session 無效或已過期，請重新匯入'
            : '尚未匯入登入憑證',
      )
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e))
    } finally {
      setChecking(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose}>
      <h3>匯入登入憑證</h3>
      <p className="hint" style={{ margin: 0 }}>
        在本機執行 <code>python main.py login</code> 後貼上 auth_state.json
        的內容， 或貼上瀏覽器擴充功能（Cookie-Editor 等）匯出的 cookie JSON。
      </p>
      <label>
        憑證內容（JSON）
        <textarea
          value={payload}
          onChange={(e) => setPayload(e.target.value)}
          placeholder='{"cookies": [...]} 或 [{"name": "...", ...}]'
        />
      </label>
      <label>
        或選擇檔案
        <input type="file" accept=".json,application/json" onChange={onFile} />
      </label>
      {result && (
        <div className="import-result">
          <span className="ok-text">
            匯入成功（
            {result.format === 'storage_state'
              ? 'storage state'
              : 'cookie 陣列'}
            ， 共 {result.cookie_count} 個 cookie，PChome{' '}
            {result.pchome_cookie_count} 個）
          </span>
          {result.warning && <div className="warn-text">{result.warning}</div>}
        </div>
      )}
      {checkMsg && <div className="import-result">{checkMsg}</div>}
      <div className="dialog-actions">
        <button onClick={doCheck} disabled={checking}>
          {checking ? '檢查中…' : '檢查 session'}
        </button>
        <button onClick={onClose}>關閉</button>
        <button
          className="primary"
          onClick={doImport}
          disabled={busy || !payload.trim()}
        >
          {busy ? '匯入中…' : '匯入'}
        </button>
      </div>
    </Dialog>
  )
}

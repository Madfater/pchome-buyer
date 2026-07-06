import { useEffect, useState } from 'react'
import { fetchSettings, updateSettings } from '../api'
import { useToast } from '../toast'
import type { Settings } from '../types'
import Dialog from './Dialog'
import LoginSettingsSection from './LoginSettingsSection'

interface Props {
  open: boolean
  onClose: () => void
}

type PaymentForm = Pick<Settings, 'cvc' | 'auto_pay'>
type TimingForm = Pick<
  Settings,
  | 'default_interval_secs'
  | 'default_lead_secs'
  | 'fast_poll_window_secs'
  | 'slow_poll_factor'
  | 'resync_secs'
>
type AdvancedForm = Pick<Settings, 'max_retries' | 'retry_delay_secs'>

export default function SettingsDialog({ open, onClose }: Props) {
  const toast = useToast()
  const [loading, setLoading] = useState(true)
  const [payment, setPayment] = useState<PaymentForm | null>(null)
  const [timing, setTiming] = useState<TimingForm | null>(null)
  const [advanced, setAdvanced] = useState<AdvancedForm | null>(null)

  useEffect(() => {
    if (!open) return
    setLoading(true)
    fetchSettings()
      .then((s) => {
        setPayment({ cvc: s.cvc, auto_pay: s.auto_pay })
        setTiming({
          default_interval_secs: s.default_interval_secs,
          default_lead_secs: s.default_lead_secs,
          fast_poll_window_secs: s.fast_poll_window_secs,
          slow_poll_factor: s.slow_poll_factor,
          resync_secs: s.resync_secs,
        })
        setAdvanced({
          max_retries: s.max_retries,
          retry_delay_secs: s.retry_delay_secs,
        })
      })
      .catch((e) => toast(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false))
  }, [open, toast])

  const savePayment = async () => {
    if (!payment) return
    try {
      const s = await updateSettings(payment)
      setPayment({ cvc: s.cvc, auto_pay: s.auto_pay })
      toast('付款設定已儲存')
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e))
    }
  }

  const saveTiming = async () => {
    if (!timing) return
    try {
      const s = await updateSettings(timing)
      setTiming({
        default_interval_secs: s.default_interval_secs,
        default_lead_secs: s.default_lead_secs,
        fast_poll_window_secs: s.fast_poll_window_secs,
        slow_poll_factor: s.slow_poll_factor,
        resync_secs: s.resync_secs,
      })
      toast('搶購時機設定已儲存')
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e))
    }
  }

  const saveAdvanced = async () => {
    if (!advanced) return
    try {
      const s = await updateSettings(advanced)
      setAdvanced({
        max_retries: s.max_retries,
        retry_delay_secs: s.retry_delay_secs,
      })
      toast('進階設定已儲存')
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <Dialog open={open} onClose={onClose} wide>
      <h3>設定</h3>
      {loading && <p className="hint">載入中…</p>}
      {!loading && (
        <>
          <section className="settings-section">
            <h4>登入</h4>
            <LoginSettingsSection />
          </section>

          {payment && (
            <section className="settings-section">
              <h4>付款</h4>
              <p className="hint" style={{ margin: 0 }}>
                AUTO_PAY
                啟用後會自動點擊「確認付款」，請務必先確認商品與數量正確——會花真錢。
              </p>
              <label>
                信用卡安全碼（CVC）
                <input
                  type="password"
                  value={payment.cvc}
                  onChange={(e) =>
                    setPayment({ ...payment, cvc: e.target.value })
                  }
                />
              </label>
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={payment.auto_pay}
                  onChange={(e) =>
                    setPayment({ ...payment, auto_pay: e.target.checked })
                  }
                />
                自動確認付款（AUTO_PAY）
              </label>
              <div className="dialog-actions">
                <button className="primary" onClick={savePayment}>
                  儲存付款設定
                </button>
              </div>
            </section>
          )}

          {timing && (
            <section className="settings-section">
              <h4>搶購時機</h4>
              <label>
                預設輪詢間隔（秒）
                <input
                  type="number"
                  step="0.05"
                  min="0.05"
                  max="10"
                  value={timing.default_interval_secs}
                  onChange={(e) =>
                    setTiming({
                      ...timing,
                      default_interval_secs: Number(e.target.value),
                    })
                  }
                />
              </label>
              <label>
                預設提前啟動秒數
                <input
                  type="number"
                  min="0"
                  max="3600"
                  value={timing.default_lead_secs}
                  onChange={(e) =>
                    setTiming({
                      ...timing,
                      default_lead_secs: Number(e.target.value),
                    })
                  }
                />
              </label>
              <label>
                開賣前全速輪詢窗口（秒）
                <input
                  type="number"
                  min="0"
                  max="120"
                  value={timing.fast_poll_window_secs}
                  onChange={(e) =>
                    setTiming({
                      ...timing,
                      fast_poll_window_secs: Number(e.target.value),
                    })
                  }
                />
              </label>
              <label>
                慢速輪詢倍率
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={timing.slow_poll_factor}
                  onChange={(e) =>
                    setTiming({
                      ...timing,
                      slow_poll_factor: Number(e.target.value),
                    })
                  }
                />
              </label>
              <label>
                時間校正週期（秒）
                <input
                  type="number"
                  min="1"
                  max="600"
                  value={timing.resync_secs}
                  onChange={(e) =>
                    setTiming({
                      ...timing,
                      resync_secs: Number(e.target.value),
                    })
                  }
                />
              </label>
              <div className="dialog-actions">
                <button className="primary" onClick={saveTiming}>
                  儲存搶購時機設定
                </button>
              </div>
            </section>
          )}

          {advanced && (
            <section className="settings-section">
              <h4>進階</h4>
              <label>
                加入購物車失敗重試次數
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={advanced.max_retries}
                  onChange={(e) =>
                    setAdvanced({
                      ...advanced,
                      max_retries: Number(e.target.value),
                    })
                  }
                />
              </label>
              <label>
                重試間隔（秒）
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="5"
                  value={advanced.retry_delay_secs}
                  onChange={(e) =>
                    setAdvanced({
                      ...advanced,
                      retry_delay_secs: Number(e.target.value),
                    })
                  }
                />
              </label>
              <div className="dialog-actions">
                <button className="primary" onClick={saveAdvanced}>
                  儲存進階設定
                </button>
              </div>
            </section>
          )}
        </>
      )}
      <div className="dialog-actions">
        <button onClick={onClose}>關閉</button>
      </div>
    </Dialog>
  )
}

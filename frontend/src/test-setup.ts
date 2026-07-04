import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

// 沒有啟用 vitest 的 `globals: true`（刻意用明確 import 避免與 ambient 型別衝突），
// @testing-library/react 的自動 cleanup 依賴 global afterEach 才會註冊，這裡手動接上，
// 否則每個 it() render 出的 DOM 會累積到下一個測試，導致「找到多個相同節點」的假錯誤。
afterEach(() => cleanup())

// jsdom 未實作 <dialog> 的 showModal/close（只有 open 屬性），
// Dialog.tsx 依賴這兩個方法與 close 事件，測試環境補上最小可用的行為。
if (!HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.setAttribute('open', '')
  }
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    const wasOpen = this.open
    this.removeAttribute('open')
    if (wasOpen) this.dispatchEvent(new Event('close'))
  }
}
